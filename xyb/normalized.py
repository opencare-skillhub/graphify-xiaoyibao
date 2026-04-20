from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path


MARKER_REGEX: list[tuple[str, str, re.Pattern[str]]] = [
    ("ca19_9", "CA19-9", re.compile(r"(?:ca\s*)?19\s*-?\s*9|糖链抗原\s*19\s*-?\s*9|119\s*-?\s*9", re.I)),
    ("cea", "CEA", re.compile(r"\bcea\b|癌胚抗原", re.I)),
    ("afp", "AFP", re.compile(r"\bafp\b|甲胎蛋白", re.I)),
    ("ca50", "CA50", re.compile(r"ca\s*50\b|糖链抗原\s*50|\b5O\b", re.I)),
    ("ca72_4", "CA72-4", re.compile(r"ca\s*72\s*-?\s*4|糖链抗原\s*72\s*-?\s*4|a7\s*2\s*-?\s*4", re.I)),
    ("ca125", "CA125", re.compile(r"ca\s*125\b|糖链抗原\s*125|4\s*125", re.I)),
]

DATE_PATTERNS = [
    re.compile(r"(20\d{2})[-_/年](\d{1,2})[-_/月](\d{1,2})"),
    re.compile(r"(20\d{2})(\d{2})(\d{2})"),
]

VALUE_PATTERN = re.compile(
    r"([0-9]+(?:[.,][0-9]+)?)\s*(U/mL|IU/mL|ng/mL|ug/mL|ug/ml|U/ml|u/ml)?",
    re.I,
)

RESULT_HINTS = ("结果", "测定值", "检测值", "value", "result")
REFERENCE_HINTS = ("参考", "范围", "区间", "normal", "ref", "上限", "下限")


def file_fingerprint(path: Path) -> str:
    st = path.stat()
    raw = f"{path.resolve()}::{st.st_size}::{int(st.st_mtime)}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


def _extract_date(*texts: str) -> str | None:
    for text in texts:
        for pat in DATE_PATTERNS:
            m = pat.search(text or "")
            if not m:
                continue
            y, mo, d = map(int, m.groups())
            try:
                return dt.date(y, mo, d).isoformat()
            except ValueError:
                continue
    return None


def _norm_unit(unit: str | None) -> str:
    u = (unit or "").strip()
    if not u:
        return "U/mL"
    u = u.replace("u/ml", "U/mL").replace("U/ml", "U/mL").replace("ug/ml", "ug/mL")
    return u


def _has_reference_context(text: str) -> bool:
    t = (text or "").lower()
    return any(h in t for h in REFERENCE_HINTS)


def _score_value_candidate(text: str, vm: re.Match[str], marker_start: int, marker_end: int) -> tuple[int, float, str] | None:
    left = text[max(0, vm.start() - 20): vm.start()]
    right = text[vm.end(): vm.end() + 20]
    around = f"{left}{right}"
    # 值若紧邻区间连接符（如 0-37），视为参考范围
    span_left = text[max(0, vm.start() - 4): vm.start()]
    span_right = text[vm.end(): vm.end() + 4]
    if re.search(r"[-~～—至]\s*$", span_left) or re.search(r"^\s*[-~～—至]", span_right):
        return None
    try:
        value = float(str(vm.group(1)).replace(",", "."))
    except Exception:
        return None
    score = 0
    if vm.group(2):
        score += 1
    if any(h in around.lower() for h in RESULT_HINTS):
        score += 3
    # 与 marker 越近越好；后侧值略优先，但允许前侧值（MinerU 常出现右列值在前）
    if vm.start() >= marker_end:
        score += 2
    else:
        score += 1
    distance = min(abs(vm.start() - marker_start), abs(vm.end() - marker_end))
    score -= int(distance / 20)
    if 0 <= value <= 100000:
        score += 1
    else:
        score -= 3
    return score, value, _norm_unit(vm.group(2))


def _pick_best_value_near_marker(text: str, marker_start: int, marker_end: int) -> tuple[float, str] | None:
    best: tuple[int, float, str] | None = None
    for vm in VALUE_PATTERN.finditer(text):
        cand = _score_value_candidate(text, vm, marker_start, marker_end)
        if not cand:
            continue
        if best is None or cand[0] > best[0]:
            best = cand
    if best is None:
        return None
    return best[1], best[2]


def extract_marker_records_from_nodes(nodes: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for n in nodes:
        label = str(n.get("label", ""))
        source_file = str(n.get("source_file", ""))
        node_id = str(n.get("id", ""))
        for key, marker_label, pat in MARKER_REGEX:
            m = pat.search(label)
            if not m:
                continue
            left = max(0, m.start() - 24)
            right = min(len(label), m.end() + 96)
            window = label[left:right]
            picked = _pick_best_value_near_marker(window, m.start() - left, m.end() - left)
            if not picked:
                continue
            date = _extract_date(label, source_file, node_id)
            if not date:
                continue
            rows.append(
                {
                    "date": date,
                    "marker_key": key,
                    "marker_label": marker_label,
                    "value": picked[0],
                    "unit": picked[1],
                    "source_file": source_file,
                    "is_reference": False,
                    "confidence": "INFERRED",
                }
            )
    # 去重
    dedup: dict[tuple[str, str, float, str, str], dict] = {}
    for r in rows:
        k = (r["date"], r["marker_key"], float(r["value"]), r["unit"], r["source_file"])
        dedup[k] = r
    return sorted(dedup.values(), key=lambda x: (x["marker_key"], x["date"], x["value"]))


def extract_marker_records_from_texts(file_texts: list[tuple[str, str]]) -> list[dict]:
    rows: list[dict] = []
    for source_file, text in file_texts:
        if not (text or "").strip():
            continue
        date = _extract_date(text, source_file)
        if not date:
            continue
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for i, line in enumerate(lines):
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            window = f"{line} {nxt}".replace(",", ".")
            for key, marker_label, pat in MARKER_REGEX:
                picked: tuple[float, str] | None = None
                m_line = pat.search(line)
                if m_line:
                    line_norm = line.replace(",", ".")
                    left = max(0, m_line.start() - 24)
                    right = min(len(line_norm), m_line.end() + 96)
                    near = line_norm[left:right]
                    picked = _pick_best_value_near_marker(near, m_line.start() - left, m_line.end() - left)
                if not picked:
                    m_nxt = pat.search(nxt)
                    if m_nxt:
                        nxt_norm = nxt.replace(",", ".")
                        left = max(0, m_nxt.start() - 24)
                        right = min(len(nxt_norm), m_nxt.end() + 96)
                        near = nxt_norm[left:right]
                        picked = _pick_best_value_near_marker(near, m_nxt.start() - left, m_nxt.end() - left)
                if not picked:
                    m = pat.search(window)
                    if not m:
                        continue
                    left = max(0, m.start() - 24)
                    right = min(len(window), m.end() + 96)
                    near = window[left:right]
                    picked = _pick_best_value_near_marker(near, m.start() - left, m.end() - left)
                if not picked:
                    continue
                rows.append(
                    {
                        "date": date,
                        "marker_key": key,
                        "marker_label": marker_label,
                        "value": picked[0],
                        "unit": picked[1],
                        "source_file": source_file,
                        "is_reference": False,
                        "confidence": "INFERRED",
                    }
                )
    dedup: dict[tuple[str, str, float, str, str], dict] = {}
    for r in rows:
        k = (r["date"], r["marker_key"], float(r["value"]), r["unit"], r["source_file"])
        dedup[k] = r
    return sorted(dedup.values(), key=lambda x: (x["marker_key"], x["date"], x["value"]))


def write_normalized_markers(output_dir: Path, records: list[dict], current_files: set[str]) -> dict:
    norm_dir = output_dir / "normalized"
    norm_dir.mkdir(parents=True, exist_ok=True)
    store_path = norm_dir / "markers_by_file.json"
    jsonl_path = norm_dir / "markers.jsonl"

    try:
        store = json.loads(store_path.read_text(encoding="utf-8"))
        if not isinstance(store, dict):
            store = {}
    except Exception:
        store = {}

    grouped: dict[str, list[dict]] = {}
    for r in records:
        sf = str(r.get("source_file", ""))
        if not sf:
            continue
        grouped.setdefault(sf, []).append(r)

    # current_files 为真值基线：不存在的文件直接清理
    for sf in list(store.keys()):
        if sf not in current_files:
            store.pop(sf, None)

    # 对当前文件进行替换式写入（幂等）
    for sf in current_files:
        fp = ""
        p = Path(sf)
        if p.exists():
            try:
                fp = file_fingerprint(p)
            except Exception:
                fp = ""
        store[sf] = {
            "fingerprint": fp,
            "records": grouped.get(sf, []),
        }

    store_path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")

    all_rows: list[dict] = []
    for sf, payload in store.items():
        for r in payload.get("records", []):
            rr = dict(r)
            rr["source_file"] = sf
            all_rows.append(rr)
    all_rows = sorted(all_rows, key=lambda x: (x.get("marker_key", ""), x.get("date", ""), x.get("value", 0)))
    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in all_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {
        "jsonl": str(jsonl_path),
        "store": str(store_path),
        "rows": len(all_rows),
        "files": len(store),
    }
