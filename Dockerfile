FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV CUDA_HOME=/usr/local/cuda

RUN apt-get update && apt-get install -y \
    python3.11 python3.11-dev python3.11-distutils \
    python3-pip git curl \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && python -m pip install --upgrade pip

# torch 2.5.1+cu121: latest stable CUDA 12.1 wheel.
# LLaMA-Factory requires torch>=1.13.1, so 2.5.1 satisfies it with no version conflicts.
RUN pip install \
    torch==2.5.1 torchvision==0.20.1 \
    --index-url https://download.pytorch.org/whl/cu121

# LLaMA-Factory pulls in transformers, peft, trl, datasets, etc.
# bitsandbytes is optional in llamafactory (only for 4-bit quantization), so install explicitly.
RUN pip install llamafactory bitsandbytes

WORKDIR /workspace
