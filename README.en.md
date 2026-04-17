# xyb (llm-wiki-xiaoyibao)

[中文](README.md) | [English](README.en.md)

`xyb` is an independent CLI project: local inputs (code/docs/images, etc.) → extraction → knowledge graph → reports and exports.  
Current version includes migrated core pipeline plus medical-record workflow enhancements (template init, recursive scan, medical summary, incremental backfill).

---

## 1) Current capabilities

### Core pipeline
- `scan`: recursive directory scan + classification summary
- `extract`: structured node/edge extraction
- `analyze`: one-shot `extract + build + report`
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

---

## 2) Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
xyb --help
```

---

## 3) Recommended workflow (medical records)

```bash
# 1) Initialize template
xyb init ./my-records

# 2) Scan recursively
xyb scan ./my-records

# 3) One-shot graph + report
xyb analyze ./my-records --output-dir ./graphify-out

# 4) Medical summary report
xyb report ./my-records --output-dir ./graphify-out

# 5) Graph queries
xyb query "pancreas tumor" --graph ./graphify-out/graph.json
xyb path "Pancreas" "Tumor" --graph ./graphify-out/graph.json
xyb explain "Pancreas" --graph ./graphify-out/graph.json
```

---

## 4) Command quick reference

### Basics
```bash
xyb init <path>
xyb scan <path>
xyb extract <path>
xyb analyze <path> --output-dir ./graphify-out
xyb build <extract.json> --output-dir ./graphify-out
xyb graph-report <extract.json> --output-dir ./graphify-out
xyb report <path> --output-dir ./graphify-out
xyb update <path>
xyb watch <path>
xyb backfill-merge ./graphify-out
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
graphify-out/
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

---

## 7) Docs

- Active spec: `docs/superpowers/specs/2026-04-14-xiaoyibao-v1-design.md`
- Active plan: `docs/superpowers/plans/2026-04-14-xiaoyibao-v1.md`
- Dev closure report: `docs/reports/2026-04-17-xyb-v1-dev-closure-report.md`
- Archive: `docs/archive/`

