# xyb (llm-wiki-xiaoyibao)

[中文](README.md) | [English](README.en.md)

`xyb` is an independent CLI project: local medical records (docs/PDF/images/video/DICOM) → extraction → knowledge graph → reports and exports.  
Current version includes migrated core pipeline plus medical-record workflow enhancements (template init, recursive scan, medical summary, incremental backfill).

**Current version: `v0.1.1`**

---

## 1) Current capabilities

### Core pipeline
- `scan`: recursive directory scan + classification summary
- `extract`: structured node/edge extraction
- `process`: primary medical-first pipeline (includes DICOM metadata)
- `full-update`: one-shot `process + markers-trend`
- `graph-report`: graph + report from extraction JSON
- `query/path/explain`: graph query, shortest path, node explain
- `update`: incremental scan
- `watch`: file watch + update signal
- `backfill-merge`: semantic backfill merge + audit

### Export & integration
- `wiki`: agent-crawlable wiki export
- `graphml`: GraphML export
- `obsidian`: Obsidian vault export
- `neo4j`: Cypher export
- `neo4j-push`: direct Neo4j push
- `serve`: local MCP stdio server

### Medical workflow enhancements
- `init`: scaffold standard patient-record template
- recursive subdirectory scanning by default
- `report`: medical summary (`MEDICAL_SUMMARY.md`)
- query/explain can surface medical directory bucket signals
- `markers-trend`: one-shot tumor-marker trend outputs (`csv/png/summary`)

---

## 2) Quick start

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e .
xyb --help
```

---

## 3) Recommended workflow (medical records)

```bash
# 1) Initialize template
xyb init ./my-records

# 2) Scan recursively
xyb scan ./my-records

# 3) One-shot graph + report (recommended)
xyb process ./my-records --output-dir ./xiaoyibao-out

# 4) Medical summary report
xyb report ./my-records --output-dir ./xiaoyibao-out

# 5) Graph queries
xyb query "pancreas tumor" --graph ./xiaoyibao-out/graph.json
xyb path "Pancreas" "Tumor" --graph ./xiaoyibao-out/graph.json
xyb explain "Pancreas" --graph ./xiaoyibao-out/graph.json
```

---

## 4) Command quick reference

### Basics
```bash
xyb init <path>
xyb scan <path>
xyb process <path> --output-dir ./xiaoyibao-out
xyb extract <path>
xyb analyze <path> --output-dir ./graphify-out
xyb build <extract.json> --output-dir ./graphify-out
xyb graph-report <extract.json> --output-dir ./graphify-out
xyb report <path> --output-dir ./xiaoyibao-out
xyb update <path>
xyb watch <path>
xyb backfill-merge ./graphify-out
xyb markers-trend --graph ./xiaoyibao-out/graph.json --output-dir ./xiaoyibao-out
xyb full-update <path> --output-dir ./xiaoyibao-out
```

### Query / service
```bash
xyb query "<question>" --graph ./graphify-out/graph.json
xyb path "<source>" "<target>" --graph ./graphify-out/graph.json
xyb explain "<node>" --graph ./graphify-out/graph.json
xyb serve ./graphify-out/graph.json
```

### Export
```bash
xyb wiki ./graphify-out/graph.json --output-dir ./graphify-out/wiki
xyb graphml ./graphify-out/graph.json --output ./graphify-out/graph.graphml
xyb obsidian ./graphify-out/graph.json --output-dir ./graphify-out/obsidian
xyb neo4j ./graphify-out/graph.json --output ./graphify-out/neo4j.cypher
xyb neo4j-push ./graphify-out/graph.json --uri bolt://localhost:7687 --user neo4j --password secret
```

### URL ingest
```bash
xyb add https://example.com/article --dir ./raw
```

### Platform skeleton install / Hook
```bash
# project-local
xyb install
xyb claude install
xyb codex install
xyb opencode install
xyb cursor install
xyb gemini install

# install + git hook in one command
xyb claude install --hook
xyb codex install --hook

# global platform skeleton
xyb install --global-platform codex
xyb install uninstall --global-platform codex

# git hook management
xyb hook install
xyb hook status
xyb hook uninstall
```

---

## 5) Default outputs

```text
xiaoyibao-out/
├── .graphify_extract.json
├── .graphify_analysis.json
├── .graphify_labels.json
├── graph.json
├── graph.html
├── GRAPH_REPORT.md
└── MEDICAL_SUMMARY.md
```

---

## 6) Current boundaries

- This phase focuses on a stable local workflow; deep platform integrations are still skeleton-level.
- `xyb add` YouTube/video ingestion path is not fully migrated yet.
- For DICOM, current recommendation is file-level indexing / metadata-first; use CT report text + pathology/lab text as the primary graph source in v1.

### Chinese OCR note (important)

`xyb` works heavily with **Chinese medical screenshots**: CT reports, lab panels, tumor-marker screenshots, pathology screenshots, and similar materials.  
So the image parsing path should be treated as **Chinese-first**, not English-first.

Recommended image-understanding layers:

1. **Primary path: Multimodal LLM**
   - For image-like medical inputs, prefer direct multimodal understanding + structured extraction
   - Better suited for tumor-marker screenshots, CT/radiology report screenshots, lab panels, and pathology screenshots

2. **Fallback: OCR / layout**
   - `paddle-local`
   - `paddle-api`
   - `mineru-local`
   - `mineru-api`
   - Useful when multimodal is unavailable, offline/privacy constraints apply, or auditable text intermediates are needed

3. **Fallback / floor path: Tesseract**
   - Recommended language pack: `chi_sim+eng`
   - If only `eng` is installed, Chinese image extraction quality will degrade significantly
   - Keep it as a lightweight fallback, not the primary Chinese OCR engine

If your main input is Chinese medical screenshots, set up Chinese OCR first, then run:

```bash
xyb full-update <path> --output-dir ./xiaoyibao-out
```

Recommended backend semantics:

- `paddle-local`: local PaddleOCR, privacy-first
- `paddle-api`: PaddleOCR online API / layout parsing
- `mineru-local`: local MinerU (prefer `mineru-tianshu` backend, fallback to MinerU CLI)
- `mineru-api`: remote MinerU API
- `tesseract`: local fallback OCR

Default `auto` priority:

```text
multimodal > paddle-api > mineru-api > tesseract
```

If you use `paddle-api`, configure it via environment variables instead of storing keys in the repo:

```bash
export PADDLEOCR_API_URL="https://your-endpoint/layout-parsing"
export PADDLEOCR_API_TOKEN="your-token"
export PADDLEOCR_API_MODEL="PaddleOCR-VL-1.5"
```

If you use `mineru-api`, configure:

```bash
export MINERU_API_BASE_URL="https://mineru.net"
export MINERU_API_TOKEN="your-token"
```

If you use `mineru-local` with the tianshu backend (recommended):

```bash
export XYB_MINERU_LOCAL_MODE="auto"      # auto|tianshu|cli
export XYB_MINERU_TIANSHU_DIR="/path/to/mineru-tianshu/backend"
export XYB_MINERU_LOCAL_DEVICE="auto"    # on macOS: try mps first, fallback to cpu
export XYB_MINERU_LOCAL_LANG="ch"
# Optional: custom persistent conversion directory (default: <workspace>/mineru_converted)
# export XYB_MINERU_CONVERTED_DIR="/path/to/mineru_converted"
```

`mineru-local` now persists conversion artifacts and extracted text under
`<workspace>/mineru_converted/files/...`.  
Unchanged files will hit this cache in later runs (incremental reuse + audit trace).

To import old cache directories, set:

```bash
export XYB_MINERU_CONVERTED_IMPORT_DIR="/old/mineru_converted:/another/legacy_dir"
```

If you use the multimodal primary path (OpenAI-compatible), configure:

```bash
export OPENAI_COMPAT_BASE_URL="https://api.openai.com/v1"
export OPENAI_COMPAT_API_KEY="your-key"
export OPENAI_COMPAT_MODEL="gpt-5.4"
export OPENAI_COMPAT_PROVIDER="openai"
export OPENAI_COMPAT_TIMEOUT="120"
```

For Step or other OpenAI-compatible providers, replace:
- `OPENAI_COMPAT_BASE_URL`
- `OPENAI_COMPAT_API_KEY`
- `OPENAI_COMPAT_MODEL`

If you want host CLI multimodal as the highest-priority `auto` backend:

```bash
export XYB_HOST_MM_COMMAND="/Users/qinxiaoqiang/Downloads/llm-wiki-xiaoyibao/scripts/host_mm_extract.sh {image}"
export XYB_HOST_MM_TIMEOUT="180"
```

---

## 7) Skills (stable output)

Built-in local skill:

- `.agents/skills/xyb-tumor-markers-trend/SKILL.md`

Use this for recurring/stable tumor marker trend outputs (CA19-9 / CEA / AFP / CA50 / CA72-4 / CA125).

Command:

```bash
xyb markers-trend --graph ./xiaoyibao-out/graph.json --output-dir ./xiaoyibao-out
```

Generated files:

- `tumor_markers_trend.csv`
- `tumor_markers_trend.png`
- `tumor_markers_trend_summary.md`

---

## 8) Docs

- Active spec: `docs/superpowers/specs/2026-04-14-xiaoyibao-v1-design.md`
- Active plan: `docs/superpowers/plans/2026-04-14-xiaoyibao-v1.md`
- Dev closure report: `docs/reports/2026-04-17-xyb-v1-dev-closure-report.md`
- CLI regression + OCR debugging: `docs/reports/2026-04-18-cli-regression-round2.md`
- Archive: `docs/archive/`
