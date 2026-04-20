from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import requests

from xyb.normalized import extract_marker_records_from_texts

_PANEL_RE = re.compile(r"\[\[PANEL:(\d+)\]\]")

_DATE_PATTERNS = [
    re.compile(r"(20\d{2})[-_/年](\d{1,2})[-_/月](\d{1,2})"),
    re.compile(r"(20\d{2})(\d{2})(\d{2})"),
]


def _extract_date(text: str) -> str | None:
    for pat in _DATE_PATTERNS:
        m = pat.search(text or "")
        if not m:
            continue
        y, mo, d = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    return None


def split_panel_sections(text: str) -> list[tuple[str, str]]:
    matches = list(_PANEL_RE.finditer(text or ""))
    if not matches:
        return [("", text or "")]
    out: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        panel = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = (text[start:end] or "").strip()
        if block:
            out.append((panel, block))
    return out or [("", text or "")]


def llm_available() -> bool:
    return bool(os.getenv("OPENAI_COMPAT_BASE_URL") and os.getenv("OPENAI_COMPAT_API_KEY") and os.getenv("OPENAI_COMPAT_MODEL"))


def _llm_extract_observation_facts(source_file: str, panel_id: str, text: str) -> list[dict]:
    base_url = os.getenv("OPENAI_COMPAT_BASE_URL", "").rstrip("/")
    api_key = os.getenv("OPENAI_COMPAT_API_KEY", "")
    model = os.getenv("OPENAI_COMPAT_MODEL", "")
    if not base_url or not api_key or not model:
        return []
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    prompt = (
        "你是医疗事实抽取器。只输出 JSON。"
        "从输入中提取 observation_facts（仅肿瘤标志物/检验项），"
        "字段：item_code,item_name,value,unit,reference_range,abnormal_flag,report_date,evidence_text,confidence。"
        "必须区分结果值与参考范围；不能把项目名中的数字当结果值。"
        "如果不确定请不输出该项。"
        f"\nsource_file={source_file}\npanel_id={panel_id or ''}\ntext:\n{text[:5000]}"
    )
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }
    try:
        r = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=90)
        r.raise_for_status()
        content = str(r.json()["choices"][0]["message"]["content"]).strip()
        start = content.find("{")
        end = content.rfind("}")
        body = json.loads(content[start : end + 1]) if start >= 0 and end > start else {}
        facts = body.get("observation_facts", [])
        if isinstance(facts, list):
            return [x for x in facts if isinstance(x, dict)]
    except Exception:
        return []
    return []


def _fallback_extract_observation_facts(source_file: str, panel_id: str, text: str) -> list[dict]:
    source = source_file if not panel_id else f"{source_file}#panel{panel_id}"
    rows = extract_marker_records_from_texts([(source, text)])
    out: list[dict] = []
    for r in rows:
        out.append(
            {
                "fact_type": "observation_fact",
                "source_file": r.get("source_file", source),
                "panel_id": f"panel_{panel_id}" if panel_id else "",
                "report_date": r.get("date"),
                "item_code": r.get("marker_key"),
                "item_name": r.get("marker_label"),
                "value": r.get("value"),
                "unit": r.get("unit"),
                "reference_range": "",
                "abnormal_flag": "unknown",
                "confidence": "medium",
                "status": "ok",
                "evidence": {"text": text[:300], "bbox": None, "page_index": 0, "source_backend": "rule-fallback"},
            }
        )
    return out


def extract_medical_facts(file_texts: list[tuple[str, str]], *, mode: str = "auto") -> dict:
    """
    mode: auto|llm|rule
    """
    use_llm = mode == "llm" or (mode == "auto" and llm_available())
    observation_facts: list[dict] = []
    document_facts: list[dict] = []
    panel_facts: list[dict] = []
    for source_file, text in file_texts:
        if not (text or "").strip():
            continue
        report_date = _extract_date(text or "")
        document_facts.append(
            {
                "fact_type": "document_fact",
                "source_file": source_file,
                "report_date": report_date,
                "status": "ok",
                "confidence": "medium",
                "evidence": {"text": (text or "")[:180], "bbox": None, "page_index": 0},
            }
        )
        sections = split_panel_sections(text)
        for panel_id, section in sections:
            if panel_id:
                panel_facts.append(
                    {
                        "fact_type": "panel_fact",
                        "source_file": source_file,
                        "panel_id": f"panel_{panel_id}",
                        "report_date": _extract_date(section) or report_date,
                        "status": "ok",
                        "confidence": "medium",
                        "evidence": {"text": section[:180], "bbox": None, "page_index": 0},
                    }
                )
            facts = _llm_extract_observation_facts(source_file, panel_id, section) if use_llm else []
            if facts:
                for f in facts:
                    sf = source_file if not panel_id else f"{source_file}#panel{panel_id}"
                    observation_facts.append(
                        {
                            "fact_type": "observation_fact",
                            "source_file": sf,
                            "panel_id": f"panel_{panel_id}" if panel_id else "",
                            "report_date": f.get("report_date") or _extract_date(section) or report_date,
                            "item_code": f.get("item_code"),
                            "item_name": f.get("item_name"),
                            "value": f.get("value"),
                            "unit": f.get("unit"),
                            "reference_range": f.get("reference_range", ""),
                            "abnormal_flag": f.get("abnormal_flag", "unknown"),
                            "confidence": f.get("confidence", "medium"),
                            "status": "ok",
                            "evidence": {"text": f.get("evidence_text", section[:220]), "bbox": None, "page_index": 0, "source_backend": "llm"},
                        }
                    )
            else:
                observation_facts.extend(_fallback_extract_observation_facts(source_file, panel_id, section))
    return {
        "document_facts": document_facts,
        "panel_facts": panel_facts,
        "observation_facts": observation_facts,
        "diagnosis_facts": [],
        "conflict_facts": [],
    }


def observation_facts_to_marker_records(observation_facts: list[dict]) -> list[dict]:
    out: list[dict] = []
    for o in observation_facts:
        try:
            value = float(o.get("value"))
        except Exception:
            continue
        out.append(
            {
                "date": o.get("report_date", ""),
                "marker_key": o.get("item_code", ""),
                "marker_label": o.get("item_name", o.get("item_code", "")),
                "value": value,
                "unit": o.get("unit", "U/mL"),
                "source_file": o.get("source_file", ""),
                "is_reference": False,
                "confidence": "INFERRED",
            }
        )
    return out


def write_medical_facts(output_dir: Path, facts: dict) -> dict:
    norm = output_dir / "normalized"
    norm.mkdir(parents=True, exist_ok=True)
    paths = {
        "document_facts": norm / "document_facts.jsonl",
        "panel_facts": norm / "panel_facts.jsonl",
        "observation_facts": norm / "observation_facts.jsonl",
        "diagnosis_facts": norm / "diagnosis_facts.jsonl",
        "conflict_facts": norm / "conflict_facts.jsonl",
    }
    for k, p in paths.items():
        rows = facts.get(k, []) if isinstance(facts.get(k, []), list) else []
        with p.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {k: str(v.resolve()) for k, v in paths.items()}

