# xyb (llm-wiki-xiaoyibao)

[中文](README.md) | [English](README.en.md)

`xyb` 是一个独立 CLI 项目：输入本地资料（代码/文档/图片等）→ 抽取关系 → 构建知识图谱 → 输出报告与多种导出格式。  
当前版本已完成主链迁移，并加入病情资料场景增强（目录模板、递归扫描、病情摘要、增量 backfill）。

---

## 1) 当前能力概览

### 核心主链
- `scan`：递归扫描目录并分类统计
- `extract`：抽取节点/边结构化结果
- `analyze`：一键 `extract + build + report`
- `graph-report`：从 extraction 生成图谱与报告
- `query/path/explain`：图谱查询、最短路径、节点解释
- `update`：增量扫描
- `watch`：文件监听并触发更新提示
- `backfill-merge`：语义 backfill 合并与审计

### 导出与集成
- `wiki`：导出 agent 可浏览 wiki
- `graphml`：导出 GraphML
- `obsidian`：导出 Obsidian vault
- `neo4j`：导出 Cypher
- `neo4j-push`：直接推送到 Neo4j
- `serve`：本地 MCP stdio server

### 病情资料增强
- `init`：生成标准病情资料目录模板
- 默认递归扫描子目录
- `report` 生成病情摘要（`MEDICAL_SUMMARY.md`）
- 查询/解释可显示病情目录 bucket 信号

---

## 2) 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
xyb --help
```

---

## 3) 推荐工作流（病情资料）

```bash
# 1) 初始化目录模板
xyb init ./my-records

# 2) 扫描目录（递归）
xyb scan ./my-records

# 3) 一键产出图谱与报告
xyb analyze ./my-records --output-dir ./graphify-out

# 4) 病情摘要报告
xyb report ./my-records --output-dir ./graphify-out

# 5) 图谱查询
xyb query "pancreas tumor" --graph ./graphify-out/graph.json
xyb path "Pancreas" "Tumor" --graph ./graphify-out/graph.json
xyb explain "Pancreas" --graph ./graphify-out/graph.json
```

---

## 4) 命令速查

### 基础
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

### 查询/服务
```bash
xyb query "<question>" --graph ./graphify-out/graph.json
xyb path "<source>" "<target>" --graph ./graphify-out/graph.json
xyb explain "<node>" --graph ./graphify-out/graph.json
xyb serve ./graphify-out/graph.json
```

### 导出
```bash
xyb wiki ./graphify-out/graph.json --output-dir ./graphify-out/wiki
xyb graphml ./graphify-out/graph.json --output ./graphify-out/graph.graphml
xyb obsidian ./graphify-out/graph.json --output-dir ./graphify-out/obsidian
xyb neo4j ./graphify-out/graph.json --output ./graphify-out/neo4j.cypher
xyb neo4j-push ./graphify-out/graph.json --uri bolt://localhost:7687 --user neo4j --password secret
```

### URL 导入
```bash
xyb add https://example.com/article --dir ./raw
```

### 平台安装骨架 / Hook
```bash
# 项目级
xyb install
xyb claude install
xyb codex install
xyb opencode install
xyb cursor install
xyb gemini install

# 安装时一并注入 git hook
xyb claude install --hook
xyb codex install --hook

# 全局平台骨架
xyb install --global-platform codex
xyb install uninstall --global-platform codex

# git hook 管理
xyb hook install
xyb hook status
xyb hook uninstall
```

---

## 5) 关键输出目录

默认输出目录沿用：

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

## 6) 当前边界与注意事项

- 本期优先“本地可运行闭环”，平台深度集成仍是骨架级。
- `xyb add` 的 YouTube 下载链路尚未完成迁移。
- DICOM 当前适合做文件接入/元数据索引，建议主线优先使用 CT 报告文字、病理、检验文本建图。

---

## 7) 文档

- 生效设计：`docs/superpowers/specs/2026-04-14-xiaoyibao-v1-design.md`
- 生效计划：`docs/superpowers/plans/2026-04-14-xiaoyibao-v1.md`
- 本次收尾报告：`docs/reports/2026-04-17-xyb-v1-dev-closure-report.md`
- 历史归档：`docs/archive/`
