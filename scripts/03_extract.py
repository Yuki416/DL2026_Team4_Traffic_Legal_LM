#!/usr/bin/env python3
"""
Step 3: 結構化抽取
從 traffic_cases_merged.json 的 JFULL 全文中，用規則/正規表達式抽取結構化 JSON。
"""

import json
import re
import sys
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# 設定
# ──────────────────────────────────────────────────────────────────────────────
INPUT_PATH  = "/workspace/data/filtered/traffic_cases_merged.json"
OUTPUT_PATH = "/workspace/data/extracted/structured_cases.json"

# ──────────────────────────────────────────────────────────────────────────────
# 核心爭議對應規則（從固定清單選，不自由生成）
# ──────────────────────────────────────────────────────────────────────────────
DISPUTE_RULES = {
    "支線道未讓幹線道": ["支線道", "幹線道"],
    "閃紅燈未停讓":    ["閃紅燈"],
    "閃黃燈未減速":    ["閃黃燈"],
    "左方車未讓右方車": ["左方車未讓", ("左方", "右方")],
    "轉彎車未讓直行車": ["轉彎車未讓", ("轉彎", "直行"), ("左轉", "未讓"), ("右轉", "未讓")],
    "變換車道未讓直行車": ["變換車道", ("變換", "直行")],
    "未注意車前狀況":   ["未注意車前狀況", "未保持安全距離", "車前狀況"],
    "違反號誌":        ["闖紅燈", ("紅燈", "號誌"), "闖越紅燈"],
    "與有過失":        ["與有過失", "過失比例", ("被害人", "過失"), "過失相抵", ("訴外人", "過失")],
    "過失致死致重傷":  ["過失致死", "過失致重傷", "死亡"],
    "過失傷害成立":    ["過失傷害"],
    "民事損害賠償":    ["損害賠償", ("賠償", "民事")],
}

# 比對順序：由具體到抽象（前面的優先）
DISPUTE_ORDER = [
    "支線道未讓幹線道",
    "閃紅燈未停讓",
    "閃黃燈未減速",
    "左方車未讓右方車",
    "轉彎車未讓直行車",
    "變換車道未讓直行車",
    "未注意車前狀況",
    "違反號誌",
    "與有過失",
    "過失致死致重傷",
    "過失傷害成立",
    "民事損害賠償",
]

# ──────────────────────────────────────────────────────────────────────────────
# 法條正規表達式（精確抽取，不截斷到款）
# ──────────────────────────────────────────────────────────────────────────────

# 阿拉伯數字版法條（支援數字與「條」之間有空格，如「第284 條」）
ARTICLE_SUFFIX_ARABIC = r"第(\d+(?:-\d+)?\s*條(?:第\d+項)?(?:第\d+款)?(?:前段|後段|但書)?)"

# 中文數字版法條（用於部份判決書）
CN_NUM = r"[零一二三四五六七八九十百千]+"
ARTICLE_SUFFIX_CHINESE = r"第(" + CN_NUM + r"條(?:第" + CN_NUM + r"項)?(?:第" + CN_NUM + r"款)?(?:前段|後段|但書)?)"

# 已知台灣常見法律名稱（從長到短排序，確保先比對長名稱）
KNOWN_LAW_NAMES = [
    "道路交通安全規則",
    "道路交通管理處罰條例",
    "兒童及少年福利與權益保障法",
    "強制汽車責任保險法",
    "犯罪被害人保護法",
    "道路交通事故處理辦法",
    "汽車運輸業管理規則",
    "中華民國刑法",  # 有些判決書用全稱
    "刑事訴訟法",
    "民事訴訟法",
    "行政訴訟法",
    "強制執行法",
    "行政罰法",
    "保險法",
    "刑法",
    "民法",
]
KNOWN_LAW_NAMES.sort(key=len, reverse=True)

# 建立阿拉伯數字版與中文數字版 regex（每個法律名稱一個 pattern）
_LAW_PATTERNS_ARABIC = [
    (name, re.compile(re.escape(name) + r"\s*" + ARTICLE_SUFFIX_ARABIC))
    for name in KNOWN_LAW_NAMES
]
_LAW_PATTERNS_CHINESE = [
    (name, re.compile(re.escape(name) + r"\s*" + ARTICLE_SUFFIX_CHINESE))
    for name in KNOWN_LAW_NAMES
]

# 通用 fallback regex（含前文清理）
LAW_PATTERN_FALLBACK = re.compile(
    r"([^\s，、。（）()「」【】第]{2,15}(?:法|規則|條例|辦法|細則))"
    r"\s*第(\d+(?:-\d+)?\s*條(?:第\d+項)?(?:第\d+款)?(?:前段|後段|但書)?)"
)

# 中文數字法條 → 標準化名稱 mapping
LAW_NAME_NORMALIZE = {
    "中華民國刑法": "刑法",
}

# 程序性法律（不列入適用法條，對交通法律 QA 無訓練價值）
PROCEDURAL_LAWS = ["刑事訴訟法", "民事訴訟法", "行政訴訟法", "強制執行法"]

# 事故事實段落的標題關鍵字（優先順序）
FACT_HEADERS_CRIMINAL = [
    "犯罪事實\n",
    "犯　罪　事　實",
    "犯 罪 事 實",
    "犯罪事實：",
    "犯罪事實:",
    "犯罪事實",
    "　　事　實\n",   # 部分交訴/交簡案件使用縮排形式
    "事　實\n",
    "事 實\n",
]

FACT_HEADERS_CIVIL = [
    # 帶冒號的版本排在無冒號之前，確保 start 不會停在「：」上
    "一、原告起訴主張：",
    "一、原告起訴主張:",
    "一、原告起訴主張",
    "一、原告主張：",
    "一、原告主張:",
    "一、原告主張",
    "原告起訴主張：",
    "原告起訴主張:",
    "原告主張：",
    "原告主張:",
    # 上訴審：原告改稱「被上訴人」或「上訴人」
    "一、被上訴人主張：",
    "一、被上訴人主張:",
    "一、被上訴人主張",
    "被上訴人主張：",
    "被上訴人主張:",
    "一、上訴人主張：",
    "一、上訴人主張:",
    "一、上訴人主張",
    "上訴人主張：",
    "上訴人主張:",
]

# 事故相關的時間地點描述 pattern
ACCIDENT_PATTERN = re.compile(
    r"(?:於(?:民國)?\d{2,4}年)\d+月\d+日.{0,50}(?:駕駛|騎乘|行駛).{5,200}(?:碰撞|撞擊|擦撞|追撞|肇事|發生車禍|交通事故|受傷|死亡)",
    re.DOTALL
)

ACCIDENT_PATTERN_LOOSE = re.compile(
    r"(?:駕駛|騎乘).{5,300}(?:碰撞|撞擊|擦撞|追撞|肇事|車禍|交通事故|受傷)",
    re.DOTALL
)

# 事故摘要後驗：若摘要命中這些詞，代表抓到了非事故描述的文字
# 只比對「臺灣XX地方/高等法院」開頭，不用城市名（城市名本身就會出現在有效的事故地點描述中）
COURT_HEADER_RE = re.compile(r"^臺灣.{2,8}(地方|高等)法院")
SUMMARY_NOISE_PHRASES = (
    "合法通知", "欄一倒數", "更正補充", "原判決", "原審",
    "得加重其刑至二分之一",   # 量刑修正條文逐款列舉
    "量刑輕重，係屬",         # 量刑討論段
    "認定犯罪事實所憑之證據",  # 抓到「事實認定理由」段而非事故事實
)


# ──────────────────────────────────────────────────────────────────────────────
# 輔助函數
# ──────────────────────────────────────────────────────────────────────────────

def clean_whitespace(text: str) -> str:
    """清理全形空白、多餘換行、縮排"""
    text = text.replace("　", " ")
    text = re.sub(r"\n\s+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def truncate_at_sentence(text: str, max_chars: int = 400) -> str:
    """截到 max_chars 以內的最後一個完整句子（以。或；結尾），找不到則硬截"""
    if len(text) <= max_chars:
        return text
    window = text[:max_chars]
    last_end = max(window.rfind("。"), window.rfind("；"))
    if last_end > 50:
        return text[:last_end + 1]
    return window


def extend_match_to_sentence(text: str, m, max_extend: int = 400) -> str:
    """
    將 ACCIDENT_PATTERN match 延伸到原文中下一個句末（。或；），最多延伸 max_extend 字。
    ACCIDENT_PATTERN 的結尾錨是「碰撞/撞擊/受傷」等詞，通常落在句子中間；
    延伸到句末確保傷亡結果不被截斷。
    優先找「。」，若「。」太遠則退而找「；」，都找不到就原樣回傳。
    """
    end = m.end()
    next_period = text.find("。", end)
    next_semi = text.find("；", end)

    # 找出在 max_extend 範圍內最近的句末標點
    candidates = [
        pos + 1 for pos in (next_period, next_semi)
        if pos > 0 and pos - end <= max_extend
    ]
    if candidates:
        end = min(candidates)
    return text[m.start():end]


def extract_fact_section_criminal(jfull: str) -> str:
    """
    從刑事判決書抽取事故事實段。
    策略：
    1. 先找「附件」後的犯罪事實段（聲請簡易判決書）
    2. 再找正文中的「犯罪事實」段
    3. 找含時間地點的段落
    4. 備用：取 JFULL 前 500 字
    """
    jfull = jfull.replace("\r\n", "\n")
    # 策略1：附件中的犯罪事實（最完整）
    # 只對文末的附件有效，忽略句中「依附件XXX」的用法（通常在前半段）
    attach_idx = jfull.find("附件")
    if attach_idx > len(jfull) // 2:
        after_attach = jfull[attach_idx:]
        for header in FACT_HEADERS_CRIMINAL:
            hidx = after_attach.find(header)
            if hidx >= 0:
                start = hidx + len(header)
                match_one = re.search(r"一[、．,，]\s*", after_attach[start:start+200])
                if match_one:
                    start = start + match_one.start() + match_one.end()
                segment = after_attach[start:start+600]
                end_markers = re.search(
                    r"\n[二三四五六七八九十]+[、．,，]|\n[（(][一二三四五六七八九十][）)]|\n證據",
                    segment
                )
                if end_markers:
                    segment = segment[:end_markers.start()]
                cleaned = clean_whitespace(segment)
                if len(cleaned) >= 50:
                    return truncate_at_sentence(cleaned, max_chars=600)

    # 策略2：正文中的「犯罪事實」段
    # 優先用「一、...二、」結構完整抓取：能包含被告行為、受害經過、傷亡結果
    # ACCIDENT_PATTERN 作為備用，避免標題後段落沒有「一、」時漏接
    for header in FACT_HEADERS_CRIMINAL:
        hidx = jfull.find(header)
        if hidx >= 0:
            start = hidx + len(header)
            segment = jfull[start:start+1200]
            m2 = re.search(r"一[、．,，]\s*(.+?)(?:\n二[、．,，]|\Z)", segment, re.DOTALL)
            if m2:
                txt = clean_whitespace(m2.group(1))
                if len(txt) >= 50:
                    return truncate_at_sentence(txt, max_chars=600)
            m = ACCIDENT_PATTERN.search(segment)
            if m:
                txt = clean_whitespace(extend_match_to_sentence(segment, m))
                if len(txt) >= 50:
                    return truncate_at_sentence(txt, max_chars=600)

    # 策略3：全文中找時間地點的事故描述
    m = ACCIDENT_PATTERN.search(jfull)
    if m:
        txt = clean_whitespace(extend_match_to_sentence(jfull, m))
        if len(txt) >= 50:
            return truncate_at_sentence(txt, max_chars=600)

    m = ACCIDENT_PATTERN_LOOSE.search(jfull)
    if m:
        txt = clean_whitespace(extend_match_to_sentence(jfull, m))
        if len(txt) >= 50:
            return truncate_at_sentence(txt, max_chars=600)

    # 備用：前 500 字
    return truncate_at_sentence(clean_whitespace(jfull[:500]), max_chars=600)


def extract_fact_section_civil(jfull: str) -> str:
    """
    從民事判決書抽取事故事實段。
    """
    jfull = jfull.replace("\r\n", "\n")
    # 策略0：小額判決「理由要領」格式
    # 此類判決無「原告主張」段，事故描述直接在理由要領正文中
    for header in ("理由要領\n", "　　理由要領\n"):
        idx = jfull.find(header)
        if idx >= 0:
            seg = jfull[idx + len(header): idx + len(header) + 2000]
            for pat in (ACCIDENT_PATTERN, ACCIDENT_PATTERN_LOOSE):
                m = pat.search(seg)
                if m:
                    txt = clean_whitespace(extend_match_to_sentence(seg, m))
                    if len(txt) >= 50:
                        return truncate_at_sentence(txt, max_chars=600)
            break  # 有理由要領但找不到事故 pattern，繼續後面策略

    # 策略1：原告主張段
    for header in FACT_HEADERS_CIVIL:
        hidx = jfull.find(header)
        if hidx >= 0:
            start = hidx + len(header)
            segment = jfull[start:start+800]
            end_markers = re.search(
                r"\n[二三四五六七八九十]+[、．,，]|\n[（(][一二三四五六七八九十][）)]|\n被告",
                segment
            )
            if end_markers:
                segment = segment[:end_markers.start()]
            cleaned = clean_whitespace(segment)
            if len(cleaned) >= 50:
                return truncate_at_sentence(cleaned, max_chars=600)

    # 策略2：事實及理由段
    # 視窗加大到 2500 字，處理有「壹、程序方面」等前導段落的複雜格式
    idx = jfull.find("事實及理由")
    if idx >= 0:
        segment = jfull[idx:idx+2500]
        m2 = re.search(r"原告(?:起訴)?主張[：:]\s*(.+?)(?:\n被告|\n[二三四五六][、．,，]|\Z)", segment, re.DOTALL)
        if m2:
            txt = clean_whitespace(m2.group(1))
            if len(txt) >= 50:
                return truncate_at_sentence(txt, max_chars=600)
        m3 = ACCIDENT_PATTERN.search(segment)
        if m3:
            txt = clean_whitespace(extend_match_to_sentence(segment, m3))
            if len(txt) >= 50:
                return truncate_at_sentence(txt, max_chars=600)

    # 策略3：全文中找事故描述
    m = ACCIDENT_PATTERN.search(jfull)
    if m:
        txt = clean_whitespace(extend_match_to_sentence(jfull, m))
        if len(txt) >= 50:
            return truncate_at_sentence(txt, max_chars=600)

    m = ACCIDENT_PATTERN_LOOSE.search(jfull)
    if m:
        txt = clean_whitespace(extend_match_to_sentence(jfull, m))
        if len(txt) >= 50:
            return truncate_at_sentence(txt, max_chars=600)

    # 備用：前 500 字
    return truncate_at_sentence(clean_whitespace(jfull[:500]), max_chars=600)


def _is_noisy_summary(text: str) -> bool:
    """檢查摘要是否抓到非事故描述的文字（法院頭部或程序性文字）"""
    if COURT_HEADER_RE.match(text):
        return True
    if any(phrase in text for phrase in SUMMARY_NOISE_PHRASES):
        return True
    return False


def extract_fact_summary(record: dict) -> str:
    """根據 _source 選擇對應的事實抽取策略，並後驗雜訊"""
    jfull = record["JFULL"]
    # 宣示判決筆錄：JFULL 本身是法院公告格式，不含事實段落
    if jfull.lstrip().startswith("宣示判決筆錄"):
        return "【事故摘要抽取失敗】"
    source = record["_source"]
    if source == "criminal":
        result = extract_fact_section_criminal(jfull)
    else:
        result = extract_fact_section_civil(jfull)

    # 後驗：若抓到雜訊，對全文重跑精確 pattern 再試一次
    # ACCIDENT_PATTERN 的結果本身可靠（以「於民國...駕駛...」開頭），不再二次過濾
    if _is_noisy_summary(result):
        m = ACCIDENT_PATTERN.search(jfull)
        if m:
            candidate = clean_whitespace(extend_match_to_sentence(jfull, m))
            if len(candidate) >= 50:
                return truncate_at_sentence(candidate, max_chars=600)
        m2 = ACCIDENT_PATTERN_LOOSE.search(jfull)
        if m2:
            candidate = clean_whitespace(extend_match_to_sentence(jfull, m2))
            if len(candidate) >= 50:
                return truncate_at_sentence(candidate, max_chars=600)
        return "【事故摘要抽取失敗】"

    return result


def match_disputes(jfull: str) -> list:
    """
    根據關鍵字規則比對核心爭議，從固定清單選出 1–3 個。
    優先選最具體的，使用 DISPUTE_ORDER 決定優先順序。
    """
    matched = []
    for dispute in DISPUTE_ORDER:
        if len(matched) >= 3:
            break
        rules = DISPUTE_RULES[dispute]
        for rule in rules:
            if isinstance(rule, str):
                if rule in jfull:
                    if dispute not in matched:
                        matched.append(dispute)
                    break
            elif isinstance(rule, tuple):
                if all(kw in jfull for kw in rule):
                    if dispute not in matched:
                        matched.append(dispute)
                    break

    if not matched:
        return ["其他"]
    return matched[:3]


def determine_responsibility(record: dict) -> list:
    """判斷責任類型"""
    source = record["_source"]
    jfull = record["JFULL"]
    if source == "criminal":
        if "賠償" in jfull and "損害賠償" in jfull:
            return ["刑事", "民事"]
        return ["刑事"]
    else:
        return ["民事"]


def _normalize_law_name(name: str) -> str:
    """標準化法律名稱（例如「中華民國刑法」→「刑法」）"""
    return LAW_NAME_NORMALIZE.get(name, name)


def _normalize_law_str(law: str) -> str:
    """標準化法條字串，移除數字與「條」之間的多餘空格"""
    return re.sub(r"(\d)\s+(條)", r"\1\2", law)


def _dedup_laws(laws: list) -> list:
    """
    去重法條清單：
    - 標準化後去重（移除「第284 條」→「第284條」的空格差異）
    - 若「A條第X項前段」和「A條第X項」同時存在，只保留更具體的那個
    """
    normalized_laws = [_normalize_law_str(l) for l in laws]

    seen_exact = set()
    result = []
    for law in normalized_laws:
        if law in seen_exact:
            continue
        seen_exact.add(law)
        result.append(law)

    # 第二輪：去除被更具體版本涵蓋的泛化版本
    # 處理三種後綴：前段/後段/但書，以及 第X項/第X款 的層次
    # 例：刑法第284條 → 第284條前段（前/後/但）
    #     道交規則第86條 → 第86條第1項 → 第86條第1項第5款（第）
    final = []
    result_set = set(result)
    for law in result:
        is_prefix = any(
            other != law and other.startswith(law) and other[len(law):len(law)+1] in ("前", "後", "但", "第")
            for other in result_set
        )
        if not is_prefix:
            final.append(law)
    return final


def extract_laws(jfull: str) -> list:
    """
    抽取所有法條引用（阿拉伯數字 + 中文數字），去重後回傳。
    只抽取 JFULL 裡實際出現的文字，不推斷補入。

    策略：
    1. 優先用已知法律名稱精確比對（乾淨，無前綴污染）
    2. 只有完全沒找到時，才用 fallback regex 搭配名稱清理
    3. span 重疊過濾：若 match A 的位置完全落在 match B 之內，A 為幽靈法條，移除
       例：「強制汽車責任保險法第29條」match 範圍涵蓋「保險法第29條」→ 後者移除
    """
    # 正規化換行：去除行尾換行＋縮排，避免法律名稱跨行被截斷
    # 例：「強制\r\n    汽車責任保險法」→「強制汽車責任保險法」
    jfull = re.sub(r'\r?\n[ \t]+', '', jfull)

    # 步驟1：收集所有 match 及其在原文的位置 span
    all_matches = []  # [(law_string, start, end), ...]

    for name, pat in _LAW_PATTERNS_ARABIC:
        normalized_name = _normalize_law_name(name)
        for m in pat.finditer(jfull):
            full = _normalize_law_str(normalized_name + "第" + m.group(1))
            all_matches.append((full, m.start(), m.end()))

    for name, pat in _LAW_PATTERNS_CHINESE:
        normalized_name = _normalize_law_name(name)
        for m in pat.finditer(jfull):
            full = _normalize_law_str(normalized_name + "第" + m.group(1))
            all_matches.append((full, m.start(), m.end()))

    # 步驟2：幽靈法條過濾
    # 若 match A 的 span [s_a, e_a] 完全包含於另一 match B 的 span [s_b, e_b] 之內
    # （且兩者 span 不完全相同），則 A 是幽靈，丟棄
    def is_ghost(idx: int) -> bool:
        _, s_a, e_a = all_matches[idx]
        for j, (_, s_b, e_b) in enumerate(all_matches):
            if idx == j:
                continue
            if s_b <= s_a and e_a <= e_b and (s_b < s_a or e_b > e_a):
                return True
        return False

    # 步驟3：字串去重（保留原始出現順序）
    seen = set()
    laws = []
    for i, (law, _, _) in enumerate(all_matches):
        if is_ghost(i):
            continue
        if law not in seen:
            seen.add(law)
            laws.append(law)

    # 步驟4：fallback regex（僅在步驟1+2 完全無結果時啟用）
    if not laws:
        for m in LAW_PATTERN_FALLBACK.finditer(jfull):
            raw_name = m.group(1).strip()
            article = m.group(2)
            clean_m = re.search(
                r"([^\s，、。（）()「」【】依按爰核違參揆查]{2,10}(?:法|規則|條例|辦法|細則))$",
                raw_name
            )
            if clean_m:
                law_name = _normalize_law_name(clean_m.group(1))
            elif re.match(r"^[^\s，、。（）()「」【】]{2,10}(?:法|規則|條例|辦法|細則)$", raw_name):
                law_name = _normalize_law_name(raw_name)
            else:
                continue
            full = _normalize_law_str(law_name + "第" + article)
            if full not in seen:
                seen.add(full)
                laws.append(full)

    # 步驟5：過濾程序性法條（刑事/民事訴訟法等，對交通法律 QA 無訓練價值）
    laws = [law for law in laws if not any(proc in law for proc in PROCEDURAL_LAWS)]

    return _dedup_laws(laws)


def process_record(record: dict) -> dict:
    """將單筆輸入記錄轉換為結構化輸出"""
    jfull = record["JFULL"]

    return {
        "JID": record["JID"],
        "_source": record["_source"],
        "JTITLE": record.get("JTITLE", ""),
        "事故摘要": extract_fact_summary(record),
        "核心爭議": match_disputes(jfull),
        "責任類型": determine_responsibility(record),
        "適用法條": extract_laws(jfull),
    }


# ──────────────────────────────────────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────────────────────────────────────

def main():
    print(f"[INFO] 讀取輸入檔案：{INPUT_PATH}")
    with open(INPUT_PATH, encoding="utf-8") as f:
        records = json.load(f)
    print(f"[INFO] 共 {len(records)} 筆記錄")

    results = []
    failed = []
    for i, record in enumerate(records):
        if i % 200 == 0:
            print(f"[INFO] 處理進度：{i}/{len(records)}")
        try:
            out = process_record(record)
            results.append(out)
        except Exception as e:
            jid = record.get("JID", f"idx_{i}")
            print(f"[WARN] 解析失敗 {jid}: {e}", file=sys.stderr)
            failed.append(jid)

    print(f"[INFO] 成功抽取：{len(results)} 筆，失敗：{len(failed)} 筆")

    # 移除空法條案件（小額判決「理由要領」格式，無法條引用，不適合生成訓練對）
    before_filter = len(results)
    results = [r for r in results if len(r.get("適用法條", [])) > 0]
    removed_empty_law = before_filter - len(results)
    print(f"[INFO] 移除空法條案件：{removed_empty_law} 筆，剩餘：{len(results)} 筆")

    # 移除事故摘要抽取失敗的案件（無法生成有效訓練對）
    before_filter2 = len(results)
    results = [r for r in results if r.get("事故摘要") != "【事故摘要抽取失敗】"]
    removed_failed = before_filter2 - len(results)
    print(f"[INFO] 移除摘要抽取失敗案件：{removed_failed} 筆，剩餘：{len(results)} 筆")

    # 確保輸出目錄存在
    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"[INFO] 輸出已寫入：{OUTPUT_PATH}")

    # ──────────────────────────────────────────────────────────────────────────
    # 品質統計
    # ──────────────────────────────────────────────────────────────────────────
    print("\n===== 品質統計 =====")

    # 法條統計
    law_counts = [len(r["適用法條"]) for r in results]
    zero_laws = sum(1 for c in law_counts if c == 0)
    avg_laws = sum(law_counts) / len(law_counts) if law_counts else 0
    print(f"適用法條：平均 {avg_laws:.2f} 條/筆，空法條 {zero_laws} 筆 ({100*zero_laws/len(results):.1f}%)")

    # 核心爭議分布
    dispute_counter = {}
    other_count = 0
    for r in results:
        disputes = r["核心爭議"]
        if disputes == ["其他"]:
            other_count += 1
        for d in disputes:
            dispute_counter[d] = dispute_counter.get(d, 0) + 1
    other_pct = 100 * other_count / len(results)
    print(f"核心爭議「其他」比例：{other_count}/{len(results)} ({other_pct:.1f}%)")
    print("核心爭議分布：")
    for k, v in sorted(dispute_counter.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    # 事故摘要長度
    summary_lens = [len(r["事故摘要"]) for r in results]
    avg_len = sum(summary_lens) / len(summary_lens) if summary_lens else 0
    short = sum(1 for l in summary_lens if l < 50)
    failed_summary = sum(1 for r in results if r["事故摘要"] == "【事故摘要抽取失敗】")
    print(f"事故摘要：平均 {avg_len:.0f} 字，過短(<50字) {short} 筆，抽取失敗 {failed_summary} 筆")

    # 責任類型分布
    resp_counter = {}
    for r in results:
        key = "+".join(r["責任類型"])
        resp_counter[key] = resp_counter.get(key, 0) + 1
    print("責任類型分布：", resp_counter)

    if failed:
        print(f"\n[WARN] 失敗清單（前10筆）：{failed[:10]}")

    print("\n===== 完成 =====")


if __name__ == "__main__":
    main()
