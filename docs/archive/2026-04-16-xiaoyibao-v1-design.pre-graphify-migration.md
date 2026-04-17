# xiaoyibao (xyb) v1 设计文档

日期：2026-04-14
状态：已纳入已确认需求（待最终评审）

---

## 1. 项目定位

将 Graphify（代码知识图谱工具）重构为 **xiaoyibao (xyb)** —— 肿瘤患者病情文档整理与知识库构建工具。

**核心目标**：患者把病情治疗文档放到一个目录下，xyb 扫描后自动提取病情要素、建立带时间线的知识图谱，通过 MCP/Skill 供 AI Agent 查询。

**命令名称**：`xyb`（xiaoyibao 缩写）

### 已确认约束（冻结为 v1）
- 目录与开发根：`/Users/qinxiaoqiang/Downloads/llm-wiki-xiaoyibao`
- 图谱模板：胰腺癌专用（v1）
- URL 处理：抓取正文快照并保留原链接
- LLM 接入：Provider 抽象层（可切换）
- 隐私策略：允许上传原文，但必须用户显式确认
- 输出模板：`md/html/pdf` 三种（默认 `md`）
- 报告更新：支持动态更新与提醒
- 运行时策略：双运行时（Python 核心 + Node CLI/MCP/Skill，本地安装优先）
- CLI：双入口，默认 Node `xyb`
- 安装/部署：v1 仅支持仓库内本地安装与本地运行，不以 pip / npm registry 发布为交付前提

---

## 2. 总体技术架构（v1）

### 2.1 双运行时
- `core-py/`：文档识别、医学要素抽取、图谱构建、报告渲染
- `mcp-ts/`：MCP Server + Skill 封装 + 本地 Node CLI 构建
- `cli/`：默认 Node `xyb` 命令入口（调用 Python 核心）

### 2.1.1 Task 1 骨架约定
- Python CLI 与 Node CLI 在 v1 初始化阶段都至少暴露 `scan` / `report` / `serve`
- `core-py/` 先落地可运行的主干骨架与缓存占位，后续再接入文档管线
- `mcp-ts/` 先落地命令注册与测试骨架，后续再接入 MCP tools

### 2.2 进程通信
- Node → Python 采用本地 JSON-RPC（stdio 优先，HTTP 作为调试模式）
- Python 产出标准中间件：`xyb-out/index.json`、`xyb-out/graph.json`、`xyb-out/report.*`

### 2.3 发布策略
- v1 交付以 **repo-local 安装** 为准：Python 使用项目内虚拟环境/`uv run --project core-py`，Node 使用 `npm --prefix mcp-ts install && npm --prefix mcp-ts run build`
- v1 README、脚本、测试与桥接层都不得假设用户已通过 pip 或 npm 全局安装 `xyb` / `xyb-py`
- pip / npm registry 发布保留为 v1 之后的增强项；当前阶段只需要本地可安装、可运行、可验证

### 2.4 watch 与增量 backfill 约束（新增）
- macOS 下文件监听默认使用 polling 策略，而不是直接依赖 FSEvents；原因是 FSEvents 在目录层级复杂、同步盘、截图/PDF 高频写入场景下稳定性不足
- 监听策略允许环境变量覆盖：`XYB_WATCH_OBSERVER=auto|native|polling`；`auto` 在 Darwin 上选择 `polling`，其他平台选择 `native`
- 文档 / PDF / 图片变更不得只停留在 `needs_update` 提示层，设计上必须预留 **plan → extract → merge → audit** 的标准化增量语义 backfill 闭环
- merge 阶段必须遵守单一 `source_file` 归因规范：主提取 JSON 中每个 node / edge 只允许一个字符串 `source_file`；`chunk_id`、`source_files`、`summary`、`confidence_notes` 等辅助信息写入 sidecar audit 文件

## 3. 用户场景

- 肿瘤患者手上有各种格式的病情文档（CT截图、PDF报告、DICOM影像、基因检测报告、用药记录等）
- 文件名混乱，格式不统一，没有分类
- 需要一个工具帮助整理病情，方便就医时快速提取信息

---

## 4. 文档类型支持

| 类型 | 扩展名 | 提取方式 |
|------|--------|----------|
| DICOM | .dcm, .dicom | pydicom 解析元数据（设备、序列、日期、层厚等） |
| PDF | .pdf | pypdf/LLM 提取文本内容 |
| 图片 | .png, .jpg, .jpeg, .gif, .webp | Vision 模型识别（截图、报告照片） |
| Word | .docx | python-docx 提取文本 |
| Excel | .xlsx | openpyxl 提取检验指标 |
| 文本 | .txt, .md | 直接读取 |
| URL | .url 文件或文本中的链接 | 网页抓取提取内容 |

**不再支持**：代码文件（.py/.js 等）的 AST 提取。tree-sitter 依赖移除。

---

## 5. 病情要素体系

按照标准病情要素模板，提取以下维度：

### 5.1 基础信息
- 姓名、年龄、性别、联系方式、医保信息

### 5.2 确诊信息
- 癌种、分期（TNM）、病理类型、确诊日期、确诊医院

### 5.3 基因与病理详情
- 基因突变位点（如 KRAS G12D、TP53、ATM 等）
- 免疫组化指标（PD-L1、MSI 等）
- 病理报告详情

### 5.4 标志物与影像记录

#### 肿瘤标志物（可配置，支持10-20个指标）

**默认展示（5个核心标志物）**：CA19-9、CEA、CA125、CA724、CA50

**按类型分组的完整指标体系**（用户可按需启用/禁用，总计20+个）：

| 类别 | 指标 | 说明 |
|------|------|------|
| 肿瘤标志物（默认展开） | CA19-9, CEA, CA125, CA724, CA50 | 胰腺癌核心标志物 |
| 扩展肿瘤标志物 | AFP, CA15-3, CA242, SCC, NSE, CYFRA21-1 | 按癌种启用 |
| 感染指标 | CRP, PCT, IL-6, WBC, 血培养 | 感染风险监测（化疗后骨髓抑制期重点关注） |
| 血糖与代谢 | 空腹血糖, 餐后血糖, HbA1c, 胰岛素, C肽 | 胰腺癌患者血糖管理（胰腺内分泌功能） |
| 肝肾功能 | ALT, AST, TBIL, DBIL, ALB, Cr, BUN, eGFR | 化疗毒性监测 |
| 血常规 | ANC, PLT, HGB | 骨髓抑制监测 |
| 炎症与凝血 | D-dimer, FIB, PT | 血栓风险 |
| 营养与代谢 | 前白蛋白, 转铁蛋白, 总蛋白, K, Na, Ca | 营养状态 |

**展示逻辑**：
- 报告/图表中默认展开5个核心肿瘤标志物的趋势曲线
- 其他指标按类别分组，默认折叠，点击展开
- 每个指标显示：最近值、趋势方向（↑↓→）、参考范围、历史曲线
- 异常值自动标红

**配置方式**（xyb.toml）：
```toml
[markers]
# 默认展示的核心标志物
default = ["CA19-9", "CEA", "CA125", "CA724", "CA50"]

# 启用的完整指标池（支持20+个）
enabled = [
  "CA19-9", "CEA", "CA125", "CA724", "CA50",
  "AFP", "CA242", "CA15-3",
  "CRP", "PCT", "IL-6", "WBC",
  "空腹血糖", "餐后血糖", "HbA1c", "胰岛素", "C肽",
  "ALT", "AST", "ALB", "Cr",
  "ANC", "PLT", "HGB",
  "D-dimer", "FIB"
]

# 异常阈值（超出参考范围自动标红）
[markers.thresholds]
"CA19-9" = { ref_high = 37, unit = "U/mL" }
"CEA"    = { ref_high = 5.0, unit = "ng/mL" }
"CA125"  = { ref_high = 35, unit = "U/mL" }
"CA724"  = { ref_high = 6.9, unit = "U/mL" }
"CA50"   = { ref_high = 25, unit = "U/mL" }
```

#### 影像检查记录
- 影像检查关键发现（病灶尺寸、位置变化）
- 支持 DICOM 元数据提取（设备、序列、日期、层厚）
- 支持 Vision 模型识别影像截图中的文字信息

### 5.5 治疗历史
- 手术记录（时间、术式、医院）
- 化疗方案（药物、周期、剂量）
- 放疗记录
- 靶向/免疫治疗
- 介入治疗

### 5.6 用药方案与药物基因组
- 当前用药清单
- 药物毒性基因（如 UGT1A1）
- 药敏性信息
- 药物相互作用

### 5.7 并发症预防与风险
- 已知风险因素
- 预防措施
- 预警指标

### 5.8 治疗提醒
- 副作用监测
- 复查时间提醒
- 用药提醒

### 5.9 营养评估
- 营养状态评分
- 饮食建议
- 体重变化

### 5.10 心理评估
- 量表结果（PHQ-9、GAD-7 等）
- 心理干预记录

---

## 6. 图谱结构：双层架构

### 第一层：时间线维度（全局）
- 按时间排列所有事件节点
- 支持自动提取时间（DICOM 元数据、PDF 报告日期、文件名中的日期）
- 无法识别时间的标记为"未分类"
- 支持用户通过目录命名提供时间（如 `2024-03_第一次化疗/`）

### 第二层：主题维度（每个时间段内）
- 每个时间点下按病情要素主题展开
- 形成"那个时间段的完整病情快照"

### 节点类型
- Patient（患者）
- Diagnosis（诊断）
- GeneMutation（基因突变）
- Drug（药物）
- Examination（检查）
- Imaging（影像）
- Biomarker（标志物）
- SideEffect（副作用）
- Hospital（医院/科室）
- TimelineEvent（时间事件）

### 边类型
- Patient → diagnosed_with → Diagnosis
- Diagnosis → has_mutation → GeneMutation
- GeneMutation → targets → Drug
- Drug → causes → SideEffect
- Patient → underwent → Examination
- Examination → measured → Biomarker
- TimelineEvent → contains → [所有相关节点]
- Biomarker → trend → [时间序列]

---

## 7. 标准目录建议

xyb 不自动移动文件，而是生成建议的标准目录树供用户参考：

```
my_records/
├── 00_说明与索引/
│   ├── README_如何整理.md
│   ├── 文件清单.xlsx
│   └── 时间线总表.xlsx
├── 01_基础信息/
│   ├── 身份信息/
│   ├── 医保与商业保险/
│   └── 过敏史_既往史_家族史/
├── 02_确诊信息/
│   ├── 首诊资料/
│   ├── 病理报告/
│   ├── 分期评估/
│   └── MDT结论/
├── 03_基因与病理详情/
│   ├── NGS报告/
│   ├── 药敏性与药物代谢基因/
│   │   ├── UGT1A1/
│   │   ├── DPYD/
│   │   ├── TPMT_NUDT15/
│   │   └── CYP相关/
│   └── 免疫与分子标志物/
├── 04_治疗记录/
│   ├── 手术/
│   ├── 化疗/
│   ├── 放疗/
│   ├── 靶向/
│   ├── 免疫治疗/
│   └── 临床试验/
├── 05_影像资料/
│   ├── CT/
│   ├── MRI/
│   ├── PET-CT/
│   └── 影像光盘与原始DICOM说明/
├── 06_检验指标与曲线/
│   ├── 肿瘤标志物/
│   ├── 血常规/
│   ├── 生化_肝肾功能/
│   ├── 炎症与凝血/
│   └── 趋势曲线导出/
├── 07_用药方案与提醒/
│   ├── 当前用药清单/
│   ├── 历史用药/
│   ├── 不良反应与处理/
│   └── 给药日历_复诊提醒/
├── 08_并发症预防与风险管理/
│   ├── 血栓_感染_出血风险/
│   ├── 胰外分泌不足与血糖管理/
│   └── 急症预警卡/
├── 09_营养评估/
│   ├── 体重与BMI变化/
│   ├── PG-SGA_营养筛查/
│   └── 营养干预记录/
├── 10_心理评估/
│   ├── HADS/
│   ├── PHQ-9_GAD-7/
│   └── 心理干预记录/
├── 11_随访与复发监测/
│   ├── 随访计划/
│   ├── 复查记录/
│   └── 复发_转移评估/
└── 12_其他/
```

`xyb init` 生成此目录结构（含 README 说明），用户自行将文件放入对应目录。

---

## 8. 命令设计

```bash
# 默认入口（Node CLI）
xyb scan ./my_records

# Python 直接入口（调试/开发）
xyb-py scan ./my_records

# 自然语言查询
xyb query "我的基因检测结果是什么"

# 生成标准目录建议
xyb init ./my_records

# 启动 MCP Server
xyb serve

# 更新图谱（增量）
xyb update ./my_records

# 仅执行标准化语义 backfill 闭环（plan/extract/merge/audit）
xyb update ./my_records --mode semantic-backfill

# 生成病情概览报告
xyb report                    # 默认 md
xyb report --format html      # HTML 版
xyb report --format pdf       # PDF 版
```

---

## 9. MCP Server 工具

| 工具名 | 描述 |
|--------|------|
| `query_timeline` | 查询指定时间段的病情事件 |
| `get_gene_info` | 查询基因突变和靶向药匹配 |
| `get_biomarker_trend` | 查询标志物变化趋势 |
| `get_medication_history` | 查询用药历史和副作用 |
| `get_imaging_summary` | 查询影像检查摘要 |
| `get_treatment_summary` | 查询治疗历史概览 |
| `search_records` | 自然语言搜索病情记录 |
| `generate_report` | 生成病情概览报告（md/html/pdf） |

---

## 10. Skill 设计

为以下平台提供标准化 Skill 文件：
- Claude Code（skill.md）
- Hermes/OpenClaw（skill-claw.md）
- Codex（skill-codex.md）
- OpenCode（skill-opencode.md）
- 通用 MCP（通过 `xyb serve`）

Skill 内容：说明如何使用 MCP 工具查询病情图谱。

---

## 11. 保留与移除

### 保留（从 Graphify）
- NetworkX 图谱构建框架
- 缓存机制（SHA256 文件指纹）
- 导出格式（JSON、HTML 可视化）
- MCP Server 骨架（FastMCP）
- Skill 安装逻辑（多平台适配）
- 增量更新机制（但要从代码 AST 增量更新改造为病情资料的 semantic backfill 闭环）
- 报告生成框架

### 移除
- tree-sitter 依赖和所有代码 AST 提取逻辑
- 代码语言配置（LanguageConfig）
- 代码调用关系分析
- 代码-specific 的检测逻辑

### 新增
- DICOM 解析模块（pydicom）
- 医学实体提取模块（LLM + Vision）
- 病情要素 schema 定义
- 时间线构建逻辑
- 标准目录生成
- 医学术语标准化
- 病情报告模板输出（HTML/Markdown/PDF）
- macOS watch observer 策略选择与环境变量覆盖
- chunk schema / source_file merge 规范与增量 backfill 审计输出

---

## 12. 病情报告输出

每次扫描/更新图谱后，xyb 自动生成一份结构化病情报告，供患者保存或打印带给医生。

### 模板格式
| 格式 | 命令 | 说明 |
|------|------|------|
| Markdown | `xyb report` | 默认，轻量通用 |
| HTML | `xyb report --format html` | 可视化图表，浏览器打开 |
| PDF | `xyb report --format pdf` | 打印友好，带排版 |

### 报告内容结构
```
# 病情概览 - [患者姓名]
生成时间: 2024-04-14

## 基础信息（01）
## 确诊信息（02）含分期、MDT结论
## 基因与病理详情（03）含NGS、药敏性基因
## 治疗时间线（04）
  └── 按时间排列的治疗事件（手术/化疗/放疗/靶向/免疫/临床试验）
## 影像资料摘要（05）
  └── CT/MRI/PET-CT 关键发现与对比
## 检验指标与趋势（06）
  └── 肿瘤标志物曲线、血常规、肝肾功能
## 当前用药方案（07）
  └── 用药清单、不良反应、给药日历
## 并发症与风险管理（08）
  └── 血栓/感染/出血风险、急症预警
## 营养评估（09）含PG-SGA
## 心理评估（10）含HADS/PHQ-9/GAD-7
## 随访与复发监测（11）
## 近期提醒
  └── 复查时间、用药提醒、副作用监测
```

### 动态更新机制
- `xyb scan` 或 `xyb update` 执行后，自动重新生成报告
- 报告文件写入 `xyb-out/report.md`（或 .html/.pdf）
- 文件变化时输出提醒：`[xyb] 病情报告已更新 → xyb-out/report.md`
- 支持 `--notify` 标志，更新后发送系统通知（macOS/Linux toast）

### 配置
```toml
# pyproject.toml 或 xyb.toml
[report]
default_format = "md"        # md | html | pdf
auto_generate = true          # scan 后自动生成
output_dir = "xyb-out"        # 报告输出目录
notify_on_update = true       # 更新时提醒
```

### 增量语义 backfill 闭环（新增硬约束）
- `xyb update` 对 doc / pdf / image / url 类型输入必须形成四阶段闭环：
  1. `plan`：对 detect 结果与已有语义覆盖做差集，产出目标文件列表与 chunk plan
  2. `extract`：仅对目标 chunk 执行 LLM / Vision 提取，并要求严格 JSON schema
  3. `merge`：当 `source_file` 归因可靠时替换旧节点；归因不完整时追加并保留覆盖占位
  4. `audit`：显式输出 replaced / appended / unresolved / malformed 统计
- chunk worker 的主输出 JSON 统一约束为：
```json
{
  "nodes": [],
  "edges": [],
  "hyperedges": [],
  "input_tokens": 0,
  "output_tokens": 0
}
```
- `source_file` 必须为单字符串；如果 chunk 涉及多个文件，允许在 audit sidecar 记录 `source_files`，但不得污染主抽取 JSON
- merge 结果必须保证 detect 里出现的每个文件都有覆盖结论：已替换、已追加、仅占位、或 unresolved，不允许静默丢失
- v1 可以先以内置 helper / 本地脚本形式落地 merge 逻辑，但设计上要保证后续可以升级成正式 CLI 子命令

---

### 隐私与上传确认（策略 B）
- 默认允许使用云端模型，但首次涉及原文上传时必须显式确认
- 确认项至少包含：模型提供方、上传文档类型、是否包含影像截图/病理全文
- 配置项（示例）：
```toml
[privacy]
require_explicit_upload_consent = true
consent_record_file = "xyb-out/consent-log.json"
```

## 13. 技术栈

- **图谱**：NetworkX
- **DICOM**：pydicom
- **PDF**：pypdf
- **图片**：Pillow + LLM Vision
- **Office**：python-docx, openpyxl
- **MCP**：mcp SDK
- **LLM**：通过用户配置的 API（支持多 provider）

---

## 14. 第一期范围

v1 聚焦核心能力：
1. ✅ 文件类型识别（DICOM/PDF/图片/文档/URL）
2. ✅ 病情要素提取（LLM + Vision）
3. ✅ 双层图谱构建（时间线 + 主题）
4. ✅ 标准目录建议生成
5. ✅ MCP Server 基础查询
6. ✅ 多平台 Skill 输出
7. ✅ 病情报告模板输出（MD/HTML/PDF + 动态更新提醒）

不在 v1 范围：
- ❌ 自动 OCR + 文件移动
- ❌ 实时医学数据库对接（如 DrugBank、ClinVar）
- ❌ 复杂的医学术语标准化（NLP 实体链接）
- ❌ 多患者管理

---

## 开发原则

遵循 Karpathy Guidelines：
1. 简单优先，不做过度抽象
2. 最小改动，只改需要改的
3. 目标驱动，每步可验证
4. 先有测试再写实现
