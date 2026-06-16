import os
import textwrap
import time
import json
import torch
from transformers import AutoTokenizer
from argparse import ArgumentParser
from tqdm import tqdm
from vllm import LLM, SamplingParams
import numpy as np
import random
from dotenv import load_dotenv

load_dotenv()

from data_utils import read_jsonl, add_lineno_comment

def parse_args():
    parser = ArgumentParser()
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--dtype", type=str, default='float16')
    parser.add_argument("--max-tokens", type=int, default=4096, help="Max tokens for generation (SamplingParams)")
    parser.add_argument("--max-model-len", type=int, default=8192, help="Max model context length (vLLM engine)")
    parser.add_argument("--max-num-seqs", type=int, default=8, help="Max concurrent sequences (vLLM batch size)")
    parser.add_argument("--gen-timeout", type=int, default=120, help="Wall-clock seconds allowed per task batch before forcing partial output. Must scale with --max-tokens.")
    parser.add_argument("--repetition-penalty", type=float, default=1.05, help="vLLM repetition_penalty for SamplingParams.")
    parser.add_argument("--temperature", type=float, required=True)
    parser.add_argument("--output-file", type=str, required=True)
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument(
        "--quick-test",
        action="store_true",
        help="If set, only process the first problem in the dataset and then exit."
    )
    parser.add_argument("--dataset-path", type=str, default="data/leetcode-py-all.jsonl", help="Path to input dataset")
    parser.add_argument("--system-prompt", type=str, default="prompt/system_exec.txt", help="Path to system prompt file")
    parser.add_argument(
        "--disable-thinking",
        action="store_true",
        help="Pass enable_thinking=False to the chat template (for models that default to reasoning/thinking mode)."
    )
    return parser.parse_args()

def generate_with_timeout(llm_engine, prompts, sampling_params, time_limit=120):
    """
    Generates text but forcefully stops after 'time_limit' seconds.
    Returns: (results, is_timed_out_boolean)
    """
    import time
    
    # 1. Add all prompts to the engine
    batch_id = str(time.time()).replace('.', '')
    request_ids = []
    
    for i, prompt in enumerate(prompts):
        req_id = f"seq_{batch_id}_{i}" 
        request_ids.append(req_id)
        llm_engine.add_request(req_id, prompt, sampling_params)

    start_time = time.time()
    current_outputs = []
    timed_out = False 

    # 2. Run the generation loop
    while llm_engine.has_unfinished_requests():
        # Check time
        if time.time() - start_time > time_limit:
            print(f"\n!!!!!! TIMEOUT REACHED ({time_limit}s) - Saving partial output !!!!!!")
            timed_out = True 
            for req_id in request_ids:
                try:
                    llm_engine.abort_request(req_id)
                except:
                    pass
            break

        # Generate one step (one token per request)
        step_outputs = llm_engine.step()
        if step_outputs:
            current_outputs = step_outputs

    # 3. Sort results
    final_results = [None] * len(prompts)
    req_id_to_index = {rid: i for i, rid in enumerate(request_ids)}
    
    for output in current_outputs:
        if output.request_id in req_id_to_index:
            idx = req_id_to_index[output.request_id]
            final_results[idx] = output

    valid_results = [res for res in final_results if res is not None]
    
    return valid_results, timed_out

if __name__=='__main__':
    args=parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    
    print('Model:', args.model)
    print('Task:', "Line Coverage (2-Step CoT)")

    prompt_template_cond=open('prompt/line_oneshot_gencond.txt').read()
    prompt_template_test=open('prompt/line_oneshot_gentest.txt').read()
    system_template=open(args.system_prompt).read()
    system_message=system_template
    dataset=read_jsonl(args.dataset_path)
    
    print(f"Loading model: {args.model} with vLLM")
    access_token=os.getenv("HF_TOKEN")

    if access_token is None or len(access_token) < 5:
        print("Access token is too short to be successfully loaded.")
    else:
        os.environ["HF_TOKEN"] = access_token
        print("Set HF_TOKEN environment variable for vLLM.")

    tokenizer_kwargs = {
        "token": access_token,
        "trust_remote_code": True
    }
    if "mistral" in args.model.lower() or "ministral" in args.model.lower():
        tokenizer_kwargs["fix_mistral_regex"] = True
        print("Applied fix_mistral_regex=True for Tokenizer")
    
    tokenizer = None
    try:
        tokenizer = AutoTokenizer.from_pretrained(args.model, **tokenizer_kwargs)
        print("Tokenizer loaded successfully via Transformers.")
    except Exception as e:
        print(f"WARNING: AutoTokenizer failed to load ({str(e)}). Proceeding with vLLM internal tokenizer.")


    quantization_config = None    
    # Check if user passed an AWQ model
    if "AWQ" in args.model.upper():
        # EXCEPTION: Ministral/Mistral usually use 'compressed-tensors' config, not 'awq'
        # Forcing 'awq' here causes a ValidationError.
        if "ministral" in args.model.lower() or "mistral" in args.model.lower():
            print(f"Model {args.model} detected as Mistral/Ministral AWQ. Using Auto-detection (likely compressed-tensors).")
            quantization_config = None
        else:
            # For standard AWQ models (Llama, Qwen, etc.), explicit is better
            print(f"Model {args.model} detected as Standard AWQ. Forcing quantization='awq'.")
            quantization_config = "awq"
    elif "GPTQ" in args.model.upper():
        quantization_config = "gptq"

    llm = LLM(
        model=args.model, 
        trust_remote_code=True,
        tensor_parallel_size=torch.cuda.device_count(), 
        dtype=args.dtype,
        quantization=quantization_config,
        max_model_len=args.max_model_len,
        gpu_memory_utilization=0.9,
        enforce_eager=False,
        max_num_seqs=args.max_num_seqs,
        seed=args.seed,
    )

    ALL_STOP_TOKENS = [
        # Primary EOS / EOT Tokens
        "<|im_end|>",          # Qwen / ChatML / Hermes
        "<|endoftext|>",       # GPT / Qwen / Phi
        "<|end_of_text|>",     # Llama 3 Base
        "<|eot_id|>",          # Llama 3 Instruct
        "<|end|>",             # Phi-3
        "<|EOT|>",             # DeepSeek
        "<eos>",               # Gemma / General
        "<end_of_turn>",       # Gemma
        "</s>",                # Llama 2 / Mistral
        "<|END_OF_TURN_TOKEN|>", # Command R / R+

        # Safety Stops (Prevent Hallucinating New Turns)
        # If the model misses an EOS, it will try to start a new role. Stop it there.
        "<|user|>", 
        "<|model|>", 
        "<|assistant|>", 
        "<|system|>", 
        "<|start_header_id|>", # Llama 3 internal header start
        "<|im_start|>",        # ChatML start
        "[INST]",              # Mistral / Llama 2 user start
        
        # Llama 3 specific infinite loop artifacts
        "```\n\n\n", 
        "```\n\n\n\n\n",

        # --- Generic / Legacy / Niche ---
        "<|end_of_prompt|>",
        "<|end_code|>",        # DeepSeek Coder
        "<|stop|>",
        "<|eom|>",
    ]

    sampling_params = SamplingParams(
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        top_p=0.95,
        top_k=-1,
        repetition_penalty=args.repetition_penalty,
        stop=ALL_STOP_TOKENS,
        seed=args.seed,
    )

    print("Model and tokenizer loaded successfully.")
    
    models_nosys=['TheBloke/deepseek-coder-6.7B-instruct-AWQ','WeiboAI/VibeThinker-1.5B', 'google/gemma-1.1-7b-it', 'bigcode/starcoder2-15b-instruct-v0.1', 'mistralai/Mistral-7B-Instruct-v0.3']

    completed_ids = set()
    if os.path.exists(args.output_file) and os.path.getsize(args.output_file) > 0:
        print(f"Output file found. Resuming from {args.output_file}")
        with open(args.output_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if 'task_num' in data: completed_ids.add(data['task_num'])
                except json.JSONDecodeError: continue
        print(f"Found {len(completed_ids)} completed tasks. Skipping them.")

    with open(args.output_file, 'a', encoding='utf-8') as f:
        for data in tqdm(dataset, desc=f"Processing {os.path.basename(args.output_file)}"):
            problem_id = data['task_num']
            if problem_id in completed_ids: continue
            print(f"--- Starting Task ID: {problem_id} ---")
            
            testing_data = data.copy()
            testing_data.update({'model': args.model, 'temperature': args.temperature})

            try:
                func_name=data['func_name']
                code=data['python_solution']
                code_withlineno=add_lineno_comment(code) 
                target_lines=data['target_lines']
                
                # STEP 1: Generating all conditions
                cond_prompts_batch = []
                linenos_for_task = []
                for lineno in target_lines:
                    user_prompt_cond=prompt_template_cond.format(program=code_withlineno, targetline=lineno)
                    
                    if tokenizer and tokenizer.chat_template:
                        if args.model in models_nosys:
                            messages=[{"role": "user", "content": system_message + "\n\n" + user_prompt_cond}]
                        else:
                            messages=[{"role": "system", "content": system_message}, {"role": "user", "content": user_prompt_cond}]
                        chat_template_kwargs = {"enable_thinking": False} if args.disable_thinking else {}
                        full_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, **chat_template_kwargs)
                        cond_prompts_batch.append(full_prompt)
                    else:
                        full_prompt_string = f"{system_message}\n\nUser: {user_prompt_cond}\n\nAssistant:"
                        cond_prompts_batch.append(full_prompt_string)

                    linenos_for_task.append(lineno)

                start_time_cond = time.time()
                cond_outputs, cond_timeout = generate_with_timeout(llm.llm_engine, cond_prompts_batch, sampling_params, time_limit=args.gen_timeout)
                end_time_cond = time.time()
                
                # Generating all tests based on conditions
                test_prompts_batch = []
                generated_conditions_map = {}
                
                # Iterate through results
                for output, lineno in zip(cond_outputs, linenos_for_task):
                    generated_cond = output.outputs[0].text
                    generated_cond_tokens = len(output.outputs[0].token_ids)
                    
                    generated_conditions_map[lineno] = {"text": generated_cond, "tokens": generated_cond_tokens}
                    
                    user_prompt_test=prompt_template_test.format(func_name=func_name, program=code_withlineno, conditions=generated_cond)
                    
                    if tokenizer and tokenizer.chat_template:
                        if args.model in models_nosys:
                            messages=[{"role": "user", "content": system_message + "\n\n" + user_prompt_test}]
                        else:
                            messages=[{"role": "system", "content": system_message}, {"role": "user", "content": user_prompt_test}]
                        chat_template_kwargs = {"enable_thinking": False} if args.disable_thinking else {}
                        full_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, **chat_template_kwargs)
                        test_prompts_batch.append(full_prompt)
                    else:
                        full_prompt_string = f"{system_message}\n\nUser: {user_prompt_test}\n\nAssistant:"
                        test_prompts_batch.append(full_prompt_string)

                start_time_test = time.time()
                if test_prompts_batch:
                    test_outputs, test_timeout = generate_with_timeout(llm.llm_engine, test_prompts_batch, sampling_params, time_limit=args.gen_timeout)
                else:
                    test_outputs = []
                    test_timeout = False
                end_time_test = time.time()

                # Assembling results
                conditions_results, tests_results = {}, {}
                total_cond_tokens, total_test_tokens = 0, 0

                # Use valid results
                valid_linenos = linenos_for_task[:len(test_outputs)]

                for output, lineno in zip(test_outputs, valid_linenos):
                    generated_test = output.outputs[0].text
                    test_tokens = len(output.outputs[0].token_ids)
                    
                    total_test_tokens += test_tokens
                    
                    cond_info = generated_conditions_map[lineno]
                    total_cond_tokens += cond_info["tokens"]
                    
                    conditions_results[lineno] = {"condition_text": textwrap.dedent(cond_info["text"]), "generated_tokens": cond_info["tokens"]}
                    tests_results[lineno] = {"test_code": textwrap.dedent(generated_test), "generated_tokens": test_tokens}

                # Calculate Total Stats
                total_duration = (end_time_cond - start_time_cond) + (end_time_test - start_time_test)
                total_tokens = total_cond_tokens + total_test_tokens
                overall_tps = total_tokens / total_duration if total_duration > 0 else 0
                
                # Did ANY step timeout?
                overall_timeout = cond_timeout or test_timeout
                
                status_str = "TIMEOUT" if overall_timeout else "DONE"
                print(f"Task {problem_id}: {status_str} | TPS: {overall_tps:.2f} | Tokens: {total_tokens} | Time: {total_duration:.2f}s")
                
                testing_data.update({
                    'tests': tests_results, 
                    'conditions': conditions_results,
                    'timed_out': overall_timeout,
                    'performance_batch': {
                        'duration_conditions_sec': round(end_time_cond - start_time_cond, 4), 
                        'duration_tests_sec': round(end_time_test - start_time_test, 4), 
                        'total_tokens_conditions': total_cond_tokens, 
                        'total_tokens_tests': total_test_tokens,
                        'overall_tps': round(overall_tps, 2)
                    }
                })
                
                f.write(json.dumps(testing_data) + '\n')

            except Exception as e:
                error_message = f"ERROR: An unexpected error occurred on problem_id {problem_id}: {str(e)}"
                print(f"\n!!!!!! {error_message} !!!!!!")
                testing_data['error'] = error_message
                f.write(json.dumps(testing_data) + '\n') 
            
            f.flush()
            if args.quick_test:
                print(f"\n--- Quick test complete for {os.path.basename(args.output_file)}. Halting processing for this file. ---")
                break  
    print("All tasks processed.")