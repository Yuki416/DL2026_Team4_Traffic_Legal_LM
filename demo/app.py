import time
import gradio as gr
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

BASE_MODEL_PATH  = "/mnt/8tb_hdd/under115b/traffic_legal_lm/models/Llama-3-Taiwan-8B-Instruct"
GPT_LORA_PATH    = "/workspace/models/round2_gpt4o_baseline_lora"
SONNET_LORA_PATH = "/workspace/models/round2_sonnet46_lora"

DEFAULT_SYSTEM_PROMPT = """你是一位專精於台灣交通事故法律的助理。請根據使用者描述的車禍情境，分析並以 JSON 格式回答以下三項：
1. 核心爭議（從以下選 1-3 個）：轉彎車未讓直行車、支線道未讓幹線道、閃紅燈未讓閃黃燈、左方車未讓右方車、紅燈右轉、與有過失、過失傷害成立、過失致死致重傷、民事損害賠償
2. 責任類型（從以下選 1-3 個）：刑事、民事、行政
3. 適用法條（只列實際相關的法條）"""

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
)

print("載入 tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH)


def load_model(name, lora_path=None):
    print(f"載入 {name}...")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        quantization_config=bnb_config,
        device_map="auto",
    )
    if lora_path:
        model = PeftModel.from_pretrained(model, lora_path)
    model.eval()
    print(f"{name} 載入完成")
    return model


base_model   = load_model("Base Model")
gpt_model    = load_model("GPT-4o LoRA",   GPT_LORA_PATH)
sonnet_model = load_model("Sonnet LoRA",   SONNET_LORA_PATH)

print("全部模型載入完成")


def get_device(model):
    return next(model.parameters()).device


def generate(model, system_prompt, user_input, max_new_tokens=2048):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_input},
    ]
    device = get_device(model)
    inputs = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True,
    ).to(device)

    with torch.no_grad():
        output_ids = model.generate(
            inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    new_tokens = output_ids[0][inputs["input_ids"].shape[-1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True)


def run_inference(system_prompt, user_input):
    if not user_input.strip():
        yield "請輸入事故描述", "請輸入事故描述", "請輸入事故描述", "等待中", "等待中", "等待中"
        return

    start = time.time()
    base_out, gpt_out, sonnet_out = "⏳ 推論中...", "⏳ 推論中...", "⏳ 推論中..."
    base_elapsed = gpt_elapsed = sonnet_elapsed = None
    yield base_out, gpt_out, sonnet_out, "⏱ 0.0s", "⏱ 0.0s", "⏱ 0.0s"

    with ThreadPoolExecutor(max_workers=3) as executor:
        future_base   = executor.submit(generate, base_model,   system_prompt, user_input)
        future_gpt    = executor.submit(generate, gpt_model,    system_prompt, user_input)
        future_sonnet = executor.submit(generate, sonnet_model, system_prompt, user_input)
        pending = {future_base, future_gpt, future_sonnet}

        while pending:
            done, pending = wait(pending, timeout=0.5, return_when=FIRST_COMPLETED)
            now = time.time() - start
            for future in done:
                result = future.result()
                if future is future_base:
                    base_out, base_elapsed = result, now
                elif future is future_gpt:
                    gpt_out, gpt_elapsed = result, now
                else:
                    sonnet_out, sonnet_elapsed = result, now

            def fmt(elapsed, now):
                return f"⏱ {elapsed:.1f}s（完成）" if elapsed else f"⏱ {now:.1f}s"

            yield base_out, gpt_out, sonnet_out, fmt(base_elapsed, now), fmt(gpt_elapsed, now), fmt(sonnet_elapsed, now)


with gr.Blocks(title="交通法律 LLM 測試介面") as demo:
    gr.Markdown("# 交通事故法律分析 — Base vs GPT-4o vs Sonnet 4.6 對照")

    system_prompt_box = gr.Textbox(
        label="System Prompt（可編輯）",
        value=DEFAULT_SYSTEM_PROMPT,
        lines=6,
    )
    user_input_box = gr.Textbox(
        label="事故描述（白話文）",
        placeholder="例：我騎機車綠燈直行，對面轎車突然左轉撞上我，腳骨折，對方說是我的錯，請問怎麼辦？",
        lines=4,
    )
    submit_btn = gr.Button("送出", variant="primary")

    with gr.Row():
        with gr.Column():
            base_output = gr.Textbox(label="Base Model（原版）", lines=12, interactive=False)
            base_timer  = gr.Textbox(label="推論時間", value="等待中", interactive=False, lines=1)
        with gr.Column():
            gpt_output = gr.Textbox(label="Fine-tuned（GPT-4o 資料集）", lines=12, interactive=False)
            gpt_timer  = gr.Textbox(label="推論時間", value="等待中", interactive=False, lines=1)
        with gr.Column():
            sonnet_output = gr.Textbox(label="Fine-tuned（Sonnet 4.6 資料集）", lines=12, interactive=False)
            sonnet_timer  = gr.Textbox(label="推論時間", value="等待中", interactive=False, lines=1)

    submit_btn.click(
        fn=run_inference,
        inputs=[system_prompt_box, user_input_box],
        outputs=[base_output, gpt_output, sonnet_output, base_timer, gpt_timer, sonnet_timer],
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=True)
