from datasets import load_dataset

ds = load_dataset("lianghsun/tw-processed-judgments", split="train", token=True)
print(f"總筆數: {len(ds)}")
print(f"欄位: {ds.column_names}")
print(f"\n--- 第一筆範例 ---")
for k, v in ds[0].items():
    val_str = str(v)
    print(f"{k}: {val_str[:200]}")
