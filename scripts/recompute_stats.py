import json
from collections import Counter

data = json.load(open('/workspace/data/extracted/structured_cases.json'))
total = len(data)
crim = [d for d in data if d['_source'] == 'criminal']
civil = [d for d in data if d['_source'] == 'civil']

pure_crim = sum(1 for d in crim if d['责任类型'] == ['刑事']) if False else sum(1 for d in crim if d.get('責任類型') == ['刑事'])
both = sum(1 for d in crim if '民事' in d.get('責任類型', []))
pure_civil = len(civil)

print(f"total={total}, crim={len(crim)}, civil={len(civil)}")
print(f"pure_crim={pure_crim} {pure_crim/total*100:.1f}%, both={both} {both/total*100:.1f}%, pure_civil={pure_civil} {pure_civil/total*100:.1f}%")

ep = sum(1 for d in data if d.get('事故摘要','').strip()[-1:] in '。！？')
print(f"end_punct={ep}/{total}={ep/total*100:.1f}%")

tag_c = Counter(len(d.get('核心爭議',[])) for d in data)
for k in [3,2,1]:
    print(f"dispute_{k}={tag_c[k]} {tag_c[k]/total*100:.1f}%")

law_tot = sum(len(d.get('適用法條',[])) for d in data)
law6 = sum(1 for d in data if len(d.get('適用法條',[])) >= 6)
one_law = sum(1 for d in data if len(d.get('適用法條',[])) == 1)
print(f"law_avg={law_tot/total:.2f}, law6={law6} {law6/total*100:.1f}%, one_law={one_law} {one_law/total*100:.1f}%")

no_end = sum(1 for d in data if d.get('事故摘要','').strip()[-1:] not in '。！？；')
short = sum(1 for d in data if 50 <= len(d.get('事故摘要','').replace(' ','')) <= 99)
one_d = tag_c[1]
print(f"no_end={no_end} {no_end/total*100:.1f}%, short={short} {short/total*100:.1f}%, one_dispute={one_d} {one_d/total*100:.1f}%")

perfect = sum(1 for d in data if
    len(d.get('事故摘要','').replace(' ','')) >= 100 and
    d.get('事故摘要','').strip()[-1:] in '。！？' and
    len(d.get('核心爭議',[])) >= 2 and
    len(d.get('適用法條',[])) >= 2)
print(f"perfect={perfect} {perfect/total*100:.1f}%, defect={total-perfect} {(total-perfect)/total*100:.1f}%")

# 中位數
lengths = sorted(len(d.get('事故摘要','').replace(' ','')) for d in data)
median = lengths[len(lengths)//2]
print(f"median_len={median}")
