import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import prepare_model_for_kbit_training, get_peft_model, LoraConfig
from trl import SFTTrainer, SFTConfig
from datasets import Dataset

MODEL = "yentinglin/Llama-3-Taiwan-8B-Instruct"

DUMMY_DATA = [
    {"text": "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n甲闖紅燈撞傷乙，責任歸屬為何？<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n依道路交通管理處罰條例，甲違反交通號誌，應負主要過失責任。<|eot_id|>"},
    {"text": "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n追撞事故中，後車是否一定有責任？<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n原則上後車應保持安全車距，但若前車無故急煞，法院可能認定雙方均有過失。<|eot_id|>"},
    {"text": "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n車禍造成對方受傷，賠償項目有哪些？<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n依民法第193條，賠償項目包含醫療費用、喪失勞動能力損失、看護費及精神慰撫金。<|eot_id|>"},
]

print("=" * 60)
print("LoRA 訓練流程測試（假資料，僅跑 2 steps）")
print("=" * 60)

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
)
model = AutoModelForCausalLM.from_pretrained(
    MODEL,
    quantization_config=bnb_config,
    device_map="auto",
)
tokenizer = AutoTokenizer.from_pretrained(MODEL)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = prepare_model_for_kbit_training(model)
lora_config = LoraConfig(
    r=16,
    lora_alpha=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_dropout=0,
    bias="none",
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, lora_config)
dataset = Dataset.from_list(DUMMY_DATA)

training_args = SFTConfig(
    output_dir="/workspace/models/lora_dummy_test",
    max_steps=2,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    bf16=torch.cuda.is_bf16_supported(),
    fp16=not torch.cuda.is_bf16_supported(),
    logging_steps=1,
    save_steps=0,
    report_to="none",
    max_length=512,
    dataset_text_field="text",
)

trainer = SFTTrainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
    processing_class=tokenizer,
)

print("\n開始訓練...")
result = trainer.train()

print(f"\n訓練結果：")
print(f"  Steps:       {result.global_step}")
print(f"  Final loss:  {result.training_loss:.4f}")
print(f"  Loss 有下降：{'是' if result.training_loss < 10 else '請檢查'}")
print("\nLoRA 訓練流程測試完成。")
