import torch

print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU count: {torch.cuda.device_count()}")
for i in range(torch.cuda.device_count()):
    print(f"  GPU {i}: {torch.cuda.get_device_name(i)}")

import llamafactory
from transformers import AutoModelForCausalLM
from peft import LoraConfig
from trl import SFTTrainer

print("LLaMA-Factory: OK")
print("transformers, peft, trl: OK")
print("Environment setup complete!")
