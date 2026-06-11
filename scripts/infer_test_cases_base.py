"""
Run inference on eval/test_cases.json using the BASE Llama-3-Taiwan-8B-Instruct
(no LoRA). Results are written to base_model_output fields for comparison.
"""

import json
import re
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

BASE_MODEL  = "/mnt/8tb_hdd/under115b/traffic_legal_lm/models/Llama-3-Taiwan-8B-Instruct"
TEST_FILE   = "/workspace/eval/test_cases.json"
INSTRUCTION = "請判斷以下車禍情境的核心爭議、責任類型與適用法條"

def build_prompt(tokenizer, user_text: str) -> str:
    messages = [{"role": "user", "content": f"{INSTRUCTION}\n\n{user_text}"}]
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

    print("Loading base model (no LoRA)...")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    model.eval()

    with open(TEST_FILE, encoding="utf-8") as f:
        cases = json.load(f)

    for case in cases:
        tc_id = case["id"]
        print(f"\n{'='*50}")
        print(f"Running {tc_id}: {case['scenario']}")

        prompt = build_prompt(tokenizer, case["input"])
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=False,
                temperature=1.0,
                repetition_penalty=1.1,
            )

        new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
        raw_output = tokenizer.decode(new_tokens, skip_special_tokens=True)
        print(f"Raw output:\n{raw_output}")

        case["base_model_output"] = parse_output(raw_output)

    with open(TEST_FILE, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Results written to {TEST_FILE}")

if __name__ == "__main__":
    main()
