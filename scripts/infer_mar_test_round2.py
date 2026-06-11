"""
Run inference on data/mar_test.json using Round 2 GPT-4o baseline LoRA model.
Saves results to models/round2_infer_mar_test.json
"""

import json
import re
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

BASE_MODEL = "/mnt/8tb_hdd/under115b/traffic_legal_lm/models/Llama-3-Taiwan-8B-Instruct"
LORA_PATH  = "/workspace/models/round2_gpt4o_baseline_lora"
TEST_FILE  = "/workspace/data/mar_test.json"
OUTPUT_FILE = "/workspace/models/round2_infer_mar_test.json"


def build_prompt(tokenizer, instruction: str, user_text: str) -> str:
    messages = [{"role": "user", "content": f"{instruction}\n\n{user_text}"}]
    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )


def parse_output(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {"核心爭議": [], "責任類型": [], "適用法條": [], "raw": raw.strip()}


def main():
    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    print("Loading base model...")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )

    print("Loading Round 2 LoRA adapter...")
    model = PeftModel.from_pretrained(model, LORA_PATH)
    model.eval()

    with open(TEST_FILE, encoding="utf-8") as f:
        cases = json.load(f)

    results = []
    for i, case in enumerate(cases):
        jid = case["jid"]
        print(f"\n[{i+1:02d}/30] {jid}")

        prompt = build_prompt(tokenizer, case["instruction"], case["input"])
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=False,
                temperature=1.0,
                pad_token_id=tokenizer.eos_token_id,
            )

        generated = tokenizer.decode(
            output_ids[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True,
        )

        parsed = parse_output(generated)
        print(f"  raw: {generated[:120].replace(chr(10), ' ')}")

        results.append({
            "jid": jid,
            "instruction": case["instruction"],
            "input": case["input"],
            "ground_truth": json.loads(case["output"]) if isinstance(case["output"], str) else case["output"],
            "model_output_raw": generated.strip(),
            "model_output_parsed": parsed,
        })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Results saved to {OUTPUT_FILE}")

    # Quick format check
    ok = sum(1 for r in results if "核心爭議" in r["model_output_parsed"])
    print(f"Format success: {ok}/30")


if __name__ == "__main__":
    main()
