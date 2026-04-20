# xyb (llm-wiki-xiaoyibao)

[中文](README.md) | [English](README.en.md)

`xyb` 是一个独立 CLI 项目：输入本地病情资料（文档/PDF/图片/视频/DICOM）→ 抽取关系 → 构建知识图谱 → 输出报告与多种导出格式。  
当前版本已完成主链迁移，并加入病情资料场景增强（目录模板、递归扫描、病情摘要、增量 backfill）。

**当前版本：`v0.1.1`**

---

## 1) 当前能力概览

### 核心主链
- `scan`：递归扫描目录并分类统计
- `extract`：抽取节点/边结构化结果
- `process`：主线一键处理（medical-first，含 DICOM 元数据）
- `full-update`：一键 `process + markers-trend`
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
- `markers-trend`：一键生成肿瘤标志物趋势 `csv/png/summary`

---

## 2) 快速开始

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e .
xyb --help
```

---

## 3) 推荐工作流（病情资料）

```bash
# 1) 初始化目录模板
xyb init ./my-records

# 2) 扫描目录（递归）
xyb scan ./my-records

# 3) 一键产出图谱与报告（推荐）
xyb process ./my-records --output-dir ./xiaoyibao-out

# 4) 病情摘要报告
xyb report ./my-records --output-dir ./xiaoyibao-out

# 5) 图谱查询
xyb query "pancreas tumor" --graph ./xiaoyibao-out/graph.json
xyb path "Pancreas" "Tumor" --graph ./xiaoyibao-out/graph.json
xyb explain "Pancreas" --graph ./xiaoyibao-out/graph.json
```

---

## 4) 命令速查

### 基础
```bash
xyb init <path>
xyb scan <path>
xyb process <path> --output-dir ./xiaoyibao-out
xyb extract <path>
xyb analyze <path> --output-dir ./graphify-out
xyb build <extract.json> --output-dir ./graphify-out
xyb graph-report <extract.json> --output-dir ./graphify-out
xyb report <path> --output-dir ./graphify-out
xyb update <path>
xyb watch <path>
xyb backfill-merge ./graphify-out
xyb markers-trend --graph ./xiaoyibao-out/graph.json --output-dir ./xiaoyibao-out
xyb full-update <path> --output-dir ./xiaoyibao-out
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

## 6) 当前边界与注意事项

- 本期优先“本地可运行闭环”，平台深度集成仍是骨架级。
- `xyb add` 的 YouTube 下载链路尚未完成迁移。
- DICOM 当前适合做文件接入/元数据索引，建议主线优先使用 CT 报告文字、病理、检验文本建图。

### 中文 OCR 说明（重要）

`xyb` 的核心输入包含大量**中文病历截图、CT 报告截图、检验单截图、肿瘤标志物截图**。  
因此图片解析默认按**中文优先**设计，而不是英文优先。

当前建议的图片解析能力分层：

1. **主链：Multimodal LLM**
   - 对图片类输入优先使用多模态模型直接做视觉理解 + 结构化抽取
   - 更适合肿瘤标志物截图、CT/放射学报告截图、检验单、病理截图
   - 避免“先 OCR 再写大量规则”的远路

2. **fallback：OCR / layout**
   - `paddle-local`
   - `paddle-api`
   - `mineru-local`
   - `mineru-api`
   - 用于无多模态、离线、隐私优先、或需要可审计文本中间产物的场景

3. **拖底兜底：Tesseract**
   - 推荐语言包：`chi_sim+eng`
   - 若系统仅安装 `eng`，中文图片解析质量会明显下降
   - 适合作为最小闭环 fallback，不建议作为中文主 OCR

如果你主要处理中文医疗图片，建议优先补齐中文 OCR 环境，再运行：

```bash
xyb full-update <path> --output-dir ./xiaoyibao-out
```

推荐 backend 语义：

- `paddle-local`：本地 PaddleOCR，隐私优先
- `paddle-api`：PaddleOCR 在线 API / layout parsing
- `mineru-local`：本地 MinerU（优先走 `mineru-tianshu` backend，可回退 MinerU CLI）
- `mineru-api`：MinerU 远程 API
- `tesseract`：本地兜底 OCR

默认 `auto` 优先级：

```text
multimodal > paddle-api > mineru-api > tesseract
```

若使用 `paddle-api`，请通过环境变量配置，不要把 key 写入仓库：

```bash
export PADDLEOCR_API_URL="https://your-endpoint/layout-parsing"
export PADDLEOCR_API_TOKEN="your-token"
export PADDLEOCR_API_MODEL="PaddleOCR-VL-1.5"
```

若使用 `mineru-api`，请配置：

```bash
export MINERU_API_BASE_URL="https://mineru.net"
export MINERU_API_TOKEN="your-token"
```

若使用 `mineru-local` 的 tianshu 后端（推荐）：

```bash
export XYB_MINERU_LOCAL_MODE="auto"      # auto|tianshu|cli
export XYB_MINERU_TIANSHU_DIR="/path/to/mineru-tianshu/backend"
export XYB_MINERU_LOCAL_DEVICE="auto"    # macOS 自动尝试 mps，失败自动回退 cpu
export XYB_MINERU_LOCAL_LANG="ch"
# 可选：自定义转换产物落盘目录（默认 <workspace>/mineru_converted）
# export XYB_MINERU_CONVERTED_DIR="/path/to/mineru_converted"
```

`mineru-local` 会把转换产物与提取文本持久化到 `<workspace>/mineru_converted/files/...`。  
后续同文件（内容未变）会命中缓存，按增量复用，便于审计与补跑。

如需把旧缓存迁移过来，可配置：

```bash
export XYB_MINERU_CONVERTED_IMPORT_DIR="/old/mineru_converted:/another/legacy_dir"
```

若使用多模态主链（OpenAI-compatible），请配置：

```bash
export OPENAI_COMPAT_BASE_URL="https://api.openai.com/v1"
export OPENAI_COMPAT_API_KEY="your-key"
export OPENAI_COMPAT_MODEL="gpt-5.4"
export OPENAI_COMPAT_PROVIDER="openai"
export OPENAI_COMPAT_TIMEOUT="120"
```

如使用 Step 等兼容接口服务，只需替换：
- `OPENAI_COMPAT_BASE_URL`
- `OPENAI_COMPAT_API_KEY`
- `OPENAI_COMPAT_MODEL`

如使用宿主 CLI 多模态（`auto` 优先级最高），可配置：

```bash
export XYB_HOST_MM_COMMAND="/Users/qinxiaoqiang/Downloads/llm-wiki-xiaoyibao/scripts/host_mm_extract.sh {image}"
export XYB_HOST_MM_TIMEOUT="180"
```

---

## 7) Skills（稳定输出）

已内置本地 Skill：

- `.agents/skills/xyb-tumor-markers-trend/SKILL.md`

用于稳定生成肿瘤标志物趋势输出（CA19-9 / CEA / AFP / CA50 / CA72-4 / CA125）。

常用命令：

```bash
xyb markers-trend --graph ./xiaoyibao-out/graph.json --output-dir ./xiaoyibao-out
```

输出文件：

- `tumor_markers_trend.csv`
- `tumor_markers_trend.png`
- `tumor_markers_trend_summary.md`

---

## 8) 文档

- 生效设计：`docs/superpowers/specs/2026-04-14-xiaoyibao-v1-design.md`
- 生效计划：`docs/superpowers/plans/2026-04-14-xiaoyibao-v1.md`
- 本次收尾报告：`docs/reports/2026-04-17-xyb-v1-dev-closure-report.md`
- CLI 回归与 OCR 排障：`docs/reports/2026-04-18-cli-regression-round2.md`
- 历史归档：`docs/archive/`
