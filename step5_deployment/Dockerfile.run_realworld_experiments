# Dockerfile for Step 3: SLM Inference (Modelling)
FROM nvidia/cuda:12.1.1-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# --- PREVENTION FOR FREEZES ---
# Disables Infiniband/P2P which often causes hangs on consumer cloud GPUs
ENV NCCL_P2P_DISABLE=1
ENV NCCL_IB_DISABLE=1
# Helps prevent Ray/Multiprocessing deadlocks
ENV VLLM_WORKER_MULTIPROC_METHOD=spawn

# Set HF_HOME to the persistent RunPod volume
ENV HF_HOME=/workspace/huggingface_cache

# Install core system packages AND DEBUGGING TOOLS
# Added: htop, vim, strace, nvtop, procps
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    python3.10 \
    python3-pip \
    python3-dev \
    htop \
    vim \
    strace \
    nvtop \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Create symlink for python
RUN ln -s /usr/bin/python3 /usr/bin/python

# --- Project Setup ---
# KEEPING /app is excellent practice for RunPod
WORKDIR /app

COPY requirements.txt .

# Workaround: PyPI hash mismatch for cupy-cuda12x 13.6.0 (vllm -> ray[cgraph] dep).
# Download the wheel directly (bypassing pip's hash check) and pre-install it.
RUN python3 -c "import urllib.request; urllib.request.urlretrieve( \
    'https://files.pythonhosted.org/packages/53/2b/8064d94a6ab6b5c4e643d8535ab6af6cabe5455765540931f0ef60a0bc3b/cupy_cuda12x-13.6.0-cp310-cp310-manylinux2014_x86_64.whl', \
    '/tmp/cupy_cuda12x-13.6.0-cp310-cp310-manylinux2014_x86_64.whl')" && \
    pip install --default-timeout=100000 --no-cache-dir /tmp/cupy_cuda12x-13.6.0-cp310-cp310-manylinux2014_x86_64.whl && \
    rm /tmp/cupy_cuda12x-13.6.0-cp310-cp310-manylinux2014_x86_64.whl

RUN pip install --default-timeout=100000 --no-cache-dir -r requirements.txt

COPY . .

# Create the directory for predictions
RUN mkdir -p /workspace/predictions

# Execution
# Using sleep infinity allows you to debug if the script crashes/hangs
CMD ["sh", "-c", "python step3_modelling/run_real_world_experiments_inference.py && echo 'DONE' && sleep infinity"]