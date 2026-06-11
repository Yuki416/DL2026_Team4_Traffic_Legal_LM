import json

with open("/workspace/data/extracted/structured_cases.json") as f:
    data = json.load(f)

crim = next(d for d in data if d.get("_source") == "criminal")
civil = next(d for d in data if d.get("_source") == "civil")

print("=== 刑事樣本 ===")
print(f"JID: {crim['JID']}")
print(f"核心爭議: {crim['核心爭議']}")
print(f"責任類型: {crim['責任類型']}")
print(f"適用法條: {crim['適用法條']}")
print(f"事故摘要 (前150字): {crim['事故摘要'][:150]}")

print("\n=== 民事樣本 ===")
print(f"JID: {civil['JID']}")
print(f"核心爭議: {civil['核心爭議']}")
print(f"責任類型: {civil['責任類型']}")
print(f"適用法條: {civil['適用法條']}")
print(f"事故摘要 (前150字): {civil['事故摘要'][:150]}")
