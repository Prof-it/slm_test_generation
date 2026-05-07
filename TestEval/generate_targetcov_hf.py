import os
import textwrap
import time
import json
import torch
from transformers import AutoTokenizer
from typing import Tuple
from argparse import ArgumentParser, Namespace
from tqdm import tqdm
import random
import numpy as np
from vllm import LLM, SamplingParams
from dotenv import load_dotenv

load_dotenv()

from data_utils import read_jsonl, add_lineno

def parse_args() -> Namespace:
    parser = ArgumentParser()
    parser.add_argument("--dataset", type=str, default='leetcode')
    parser.add_argument("--lang", type=str, default='python', choices=['python', 'java', 'c++'])
    parser.add_argument("--dtype", type=str, default='float16')
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--covmode", type=str, default='line', choices=['line', 'branch'])
    parser.add_argument("--max-tokens", type=int, default=4096, help="Max tokens for generation (SamplingParams)")
    parser.add_argument("--max-model-len", type=int, default=8192, help="Max model context length (vLLM engine)")
    parser.add_argument("--temperature", type=float, required=True)
    parser.add_argument("--output-file", type=str, required=True, help="Path for the output predictions file.")
    parser.add_argument(
        "--quick-test",
        action="store_true",
        help="If set, only process the first problem in the dataset and then exit."
    )
    parser.add_argument("--dataset-path", type=str, default="data/leetcode-py.jsonl", help="Path to input dataset")
    parser.add_argument("--system-prompt", type=str, default="prompt/system.txt", help="Path to system prompt file")
    return parser.parse_args()

def generate_with_timeout(llm_engine, prompts, sampling_params, time_limit: int=120) -> Tuple[list, bool]:
    """
    Generates text but forcefully stops after 'time_limit' seconds.
    Returns: (results, is_timed_out_boolean)
    """
    
    # Add all prompts to the engine
    batch_id = str(time.time()).replace('.', '')
    request_ids = []
    
    for i, prompt in enumerate(prompts):
        req_id = f"seq_{batch_id}_{i}" 
        request_ids.append(req_id)
        llm_engine.add_request(req_id, prompt, sampling_params)

    start_time = time.time()
    current_outputs = []
    timed_out = False

    # Run the generation loop
    while llm_engine.has_unfinished_requests():
        # Check time
        if time.time() - start_time > time_limit:
            print(f"\n!!!!!! TIMEOUT REACHED ({time_limit}s) - Saving partial output !!!!!!")
            timed_out = True
            # Stop everything
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
    
    # Return BOTH the results and the timeout flag
    return valid_results, timed_out


if __name__=='__main__':
    args=parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    model_abbrv=args.model.split('/')[-1]
    print('Model:', model_abbrv)
    print('Task:', args.covmode)
    
    prompt_template=open('prompt/template_line.txt').read()
    prompt_template_branch=open('prompt/template_branch.txt').read()
    system_template=open(args.system_prompt).read()
    system_message=system_template.format(lang='python')

    models_nosys=['google/gemma-1.1-7b-it', 'bigcode/starcoder2-15b-instruct-v0.1', 'mistralai/Mistral-7B-Instruct-v0.3']

    dataset=read_jsonl(args.dataset_path)
    
    print(f"Loading model: {args.model}")
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
    # Ministral/Mistral models need this flag to fix regex pattern warnings/errors in transformers >= 4.46
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

    # Initializing vLLM
    llm = LLM(
        model=args.model, 
        trust_remote_code=True,
        tensor_parallel_size=torch.cuda.device_count(), 
        dtype=args.dtype,
        quantization=quantization_config,
        max_model_len=args.max_model_len,
        gpu_memory_utilization=0.9,
        enforce_eager=False,
        max_num_seqs=8,
        seed=args.seed,
    )
    # vllm does not get access token as parameter instead look for a loaded HF_TOKEN env var
    
    # Non stopping inference outputs are tried to fix by given all possible stop tokens
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
        top_k=-1, # Default value to not use top K
        repetition_penalty=1.05, # Small models might stuck selecting the same token for temperatures close to zero
        stop=ALL_STOP_TOKENS,
        seed=args.seed,
    )
    print("Model loaded successfully.")

    # Since experiments with SLMs take days (such as 2 models per day) we need to continue not from
    # the last file but from the last question
    completed_ids = set()
    if os.path.exists(args.output_file) and os.path.getsize(args.output_file) > 0:
        print(f"Output file found. Resuming from {args.output_file}")
        with open(args.output_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if 'task_num' in data:
                        completed_ids.add(data['task_num'])
                except json.JSONDecodeError:
                    print(f"Warning: Could not decode line in existing file: {line.strip()}")
        print(f"Found {len(completed_ids)} completed tasks. Skipping them.")

    with open(args.output_file, 'a', encoding='utf-8') as f:
        for data in tqdm(dataset, desc=f"Processing {os.path.basename(args.output_file)}"):
            problem_id = data['task_num']
            if problem_id in completed_ids: continue
            print(f"--- Starting Task ID: {problem_id} ---")

            func_name=data['func_name']
            desc=data['description']
            code=data['python_solution']
            code_withlineno=add_lineno(code)
            
            testing_data = data.copy()
            testing_data['model'] = args.model
            testing_data['temperature'] = args.temperature

            # We worked on only the line mode
            if args.covmode=='line':
                prompts_for_batch = []
                linenos_for_this_task = []
                target_lines = data['target_lines']

                for lineno in target_lines:
                    target_line_withlineno=f'{lineno}: {code.split(chr(10))[lineno-1]}'
                    user_prompt=prompt_template.format(lang='python', program=code_withlineno, description=desc, func_name=func_name, lineno=target_line_withlineno)
                    
                    if tokenizer and tokenizer.chat_template:
                        if args.model in models_nosys:
                            messages = [{"role": "user", "content": system_message + "\n\n" + user_prompt}]
                        else:
                            messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_prompt}]
                        full_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                        prompts_for_batch.append(full_prompt)
                    else:
                        full_prompt_string = f"{system_message}\n\nUser: {user_prompt}\n\nAssistant:"
                        prompts_for_batch.append(full_prompt_string)

                    linenos_for_this_task.append(lineno)
                try:
                    start_time = time.time()
                    
                    # Use the Safe Stepper instead of llm.generate
                    outputs, is_timeout = generate_with_timeout(llm.llm_engine, prompts_for_batch, sampling_params, time_limit=120)
                    
                    end_time = time.time()
                    
                    duration = end_time - start_time
                    tests={}
                    total_new_tokens = 0
                    
                    # Parsing vLLM Output objects
                    # Zip guarantees we align output to input, even if partial results returned
                    for output, lineno in zip(outputs, linenos_for_this_task):
                        generated_test = output.outputs[0].text
                        new_tokens = len(output.outputs[0].token_ids)
                        
                        total_new_tokens += new_tokens
                        tests[lineno] = {"test_code": textwrap.dedent(generated_test), "generated_tokens": new_tokens}

                    tokens_per_sec = total_new_tokens / duration if duration > 0 else 0
                    
                    status_str = "TIMEOUT" if is_timeout else "DONE"
                    print(f"Task {problem_id}: {status_str} | TPS: {tokens_per_sec:.2f} | Tokens: {total_new_tokens} | Time: {duration:.2f}s")

                    testing_data['tests'] = tests
                    testing_data['performance_batch'] = {
                        "duration_seconds": round(duration, 4),
                        "total_generated_tokens": total_new_tokens,
                        "tokens_per_second": round(tokens_per_sec, 2)
                    }
                    
                    f.write(json.dumps(testing_data) + '\n')
                    f.flush()
                    
                    if args.quick_test:
                        print(f"\n--- Quick test complete for {os.path.basename(args.output_file)}. Halting processing for this file. ---")
                        break

                except Exception as e:
                    # Catch general errors (context overflow, etc) and log them so we don't crash
                    error_message = f"ERROR: An unexpected error occurred on problem_id {problem_id}: {str(e)}"
                    print(f"\n!!!!!! {error_message} !!!!!!")
                    testing_data['error'] = error_message
                    testing_data['tests'] = {} 
                    f.write(json.dumps(testing_data) + '\n')
                    f.flush()
                    continue

    print("All tasks processed.")