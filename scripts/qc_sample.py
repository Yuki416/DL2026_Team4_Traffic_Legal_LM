import json
import random

random.seed(42)

with open("/workspace/data/filtered/traffic_cases.json") as f:
    crim = json.load(f)
with open("/workspace/data/filtered/traffic_cases_civil.json") as f:
    civil = json.load(f)

crim_sample  = random.sample(crim, 15)
civil_sample = random.sample(civil, 15)

print("=" * 70)
print("【刑事判決 15 筆】")
print("=" * 70)
for i, d in enumerate(crim_sample, 1):
    preview = d.get("JFULL", "")[:300].replace("\n", " ")
    jid     = d.get("JID", "")
    jcase   = d.get("JCASE", "")
    jtitle  = d.get("JTITLE", "")
    print(f"\n[C{i:02d}] {jid}")
    print(f"     案類: {jcase}  案由: {jtitle}")
    print(f"     {preview}")

print("\n" + "=" * 70)
print("【民事判決 15 筆】")
print("=" * 70)
for i, d in enumerate(civil_sample, 1):
    preview = d.get("JFULL", "")[:300].replace("\n", " ")
    jid     = d.get("JID", "")
    jcase   = d.get("JCASE", "")
    jtitle  = d.get("JTITLE", "")
    print(f"\n[M{i:02d}] {jid}")
    print(f"     案類: {jcase}  案由: {jtitle}")
    print(f"     {preview}")
