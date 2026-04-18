# xiaoyibao (xyb) v1 设计文档

日期：2026-04-16  
状态：已确认，作为当前生效设计

---

## 1. 项目定位

`xyb` 是一个**独立项目**，开发目录为：

- `/Users/qinxiaoqiang/Downloads/llm-wiki-xiaoyibao`

它的目标不是从 0 发明一套新的图谱系统，也不是直接在 `graphify` 仓库内继续开发，而是：

> **在新项目中迁移 `graphify` 的成熟结构与主链能力，并将其改造为面向病情资料场景的独立 CLI 工具。**

### 核心原则
- 所有开发都在新目录内完成
- 与 `graphify` 保持项目边界独立
- 允许迁移 `graphify` 结构与代码，再进行改造
- CLI 命令词统一为 `xyb`
- 主 Python 包目录统一为 `xyb/`
- `docs/` 保留并持续维护

---

## 2. 当前设计基线

### 2.1 总体形态
项目放弃旧版 `core-py/ + mcp-ts/` 双运行时主形态，改为以 `graphify` 现有仓库结构为主要参考进行迁移。

推荐目标结构：

```text
llm-wiki-xiaoyibao/
├── docs/
├── xyb/
│   ├── __init__.py
│   ├── __main__.py
│   ├── analyze.py
│   ├── build.py
│   ├── cache.py
│   ├── cluster.py
│   ├── detect.py
│   ├── export.py
│   ├── extract.py
│   ├── ingest.py
│   ├── report.py
│   ├── serve.py
│   ├── watch.py
│   └── ...
├── tests/
├── pyproject.toml
└── README.md
```

### 2.2 迁移来源
主要参考来源：

- `/Users/qinxiaoqiang/Downloads/graphify-upstream`
- `/Users/qinxiaoqiang/Downloads/graphify`

其中，`~/Downloads/graphify` 已包含经真实验证的本地增强经验：
- macOS watch polling 默认策略
- incremental semantic backfill 设计与 helper

### 2.3 真实验证依据
真实测试目录：

- `/Users/qinxiaoqiang/Downloads/sam_llm_wiki`

该目录已经验证：
- 图谱构建可跑通
- `graphify-out/graph.json` 已生成
- `GRAPH_REPORT.md` 已生成
- semantic/backfill/audit 相关产物已生成

这说明：

> `graphify` 主链对病情资料场景已经具备可迁移性，`xyb` 应基于这一事实推进，而不是按“从零构建全新系统”的思路推进。

---

## 3. CLI 与包命名约束

### 3.1 CLI 命令
顶层命令统一使用：

```bash
xyb
```

目标子命令包括：

```bash
xyb scan <path>
xyb watch <path>
xyb report
xyb update <path>
xyb serve
```

### 3.2 Python 包名
项目主包统一使用：

```text
xyb/
```

不保留 `graphify/` 作为主包名。

---

## 4. 第一阶段开发目标

第一阶段目标不是做“病情专用全新架构”，而是：

> **先把 `graphify` 的成熟主链迁移到 `xyb` 项目中，并完成命名切换与独立运行。**

### 第一阶段必须完成
- 将 `graphify` 主包结构迁入新项目
- 全量改名为 `xyb`
- 顶层 CLI 改为 `xyb`
- 在新项目中独立运行成功
- 保留 `docs/` 并更新说明
- 保留并纳入官方目录模板 `templates/patient-records-template-v2/`

### 第一阶段优先迁移模块
- `__main__`
- `cache`
- `detect`
- `ingest`
- `extract`
- `build`
- `cluster`
- `report`
- `export`
- `watch`
- `serve`
- 与上述模块直接相关的 tests

---

## 4.1 用户目录模板与子目录扫描要求

为了避免用户随意堆放病情资料、降低整理与追踪成本，项目必须提供官方目录模板。

### 官方模板目录
当前项目内保留：

- `templates/patient-records-template-v2/`

该模板用于指导用户整理以下内容：
- 基础信息
- 确诊信息
- 基因与病理详情
- 治疗记录
- 影像资料
- 检验指标与曲线
- 用药方案与提醒
- 并发症预防与风险管理
- 营养评估
- 心理评估
- 随访与复发监测

### 目录模板的产品要求
- 提供 `xyb init <path>` 或等价初始化命令，将模板复制到用户指定目录
- 模板的作用是**引导整理**，不是扫描前置条件
- 用户即使未按模板整理，detect / transform / graph build 仍应可运行
- 但规范目录会提升时间线、审计、报告与人工复核的可解释性

### 子目录扫描要求
- `xyb scan <path>` 默认**递归扫描所有子目录**
- 递归扫描必须覆盖用户模板中的多级子目录
- 需跳过隐藏目录、缓存目录、输出目录、依赖目录等噪声路径
- 目录模板和递归扫描应配合使用：模板帮助用户整理，递归扫描保证用户不必手动逐级指定路径

## 5. 第二阶段开发目标：病情资料专病增强

在第一阶段迁移完成后，再做专病增强。

### 重点增强方向
- 病情资料文件分类规则
- 图片 / PDF / docx / xlsx / DICOM 场景优化
- 病程时间线与主题关系组织
- 病情摘要报告模板
- 面向病情资料的 extraction contract
- 病情场景的增量 semantic backfill 闭环
- `xyb init` 目录模板初始化能力
- 面向多级子目录的默认递归扫描策略

### 病情场景增强的原则
- 优先复用 graphify 已验证主链
- 尽量避免在迁移前先发明大量新抽象
- 专病改造应建立在“独立可运行迁移版 xyb”之上

---

## 5.1 中文 OCR 与医学截图解析增强设计

`xyb` 的核心输入不是英文技术文档，而是**中文病历、检验截图、CT/放射学报告截图、病理截图、票据与随访材料**。  
因此，图片/PDF 解析链路必须以**中文优先**为默认设计，而不是把中文当成英文 OCR 的降级场景。

### 设计原则
- 中文是核心语言，英文只是辅助手段
- 医学图片解析优先保证**可读性与结构化提取质量**
- OCR 能力必须显式分层，不能静默退化
- `graphify-out/graph.json` 仅用于参考对比，**不作为 `xyb process` 的最终图谱输入**

### 分层能力设计

#### L1：本地主力 OCR（默认）
- 默认优先使用 **PaddleOCR**
- 适用场景：
  - 中文病历截图
  - 肿瘤标志物截图
  - CT / 放射学报告截图
  - 检验单、病理单等版式稳定的中文图像
- 设计定位：
  - `xyb` 的**隐私优先、本地主力 OCR**
  - 面向中文医疗资料，优先于通用英文导向 OCR

#### L2：开放增强解析（推荐增强）
- 推荐纳入 **MinerU**
- 更适合：
  - 多页 PDF
  - 扫描文档
  - 混合版式文档
  - OCR + layout + markdown/结构化恢复
- 设计要求：
  - 作为开放增强链纳入 `xyb`
  - 输出统一进入 `xyb` 的标准抽取 contract，避免双轨 schema

#### L3：基础兜底 OCR（拖底）
- 保留 **Tesseract**
- 语言优先级：
  - `chi_sim+eng`
  - `chi_tra+eng`
  - `chi_sim`
  - `chi_tra`
  - `eng`
- 设计定位：
  - 轻量、通用、易安装
  - 作为拖底路径，而非中文主力 OCR

### 明确约束
- 若仅检测到 `eng`，不得把结果视为“中文已正常解析”
- 当中文 OCR 语言包缺失时，系统应显式提示：
  - 当前 OCR 环境缺少中文语言包
  - 图片解析质量将明显下降
  - 建议安装中文 OCR 组件，或启用 PaddleOCR / MinerU
- 对以下对象需优先做结构化抽取，而不是通用 token 化：
  - 肿瘤标志物截图
  - CT / 放射学诊断截图
  - 检验报告截图

### 当前阶段结论
- v1 图片解析主线应调整为：**Multimodal LLM → OCR/layout → Tesseract**
- 默认原则：
  - 有多模态时，优先直接做视觉理解 + 结构化抽取
  - 无多模态或受隐私/成本限制时，再走 OCR / layout
  - `Tesseract` 仅作为拖底兜底能力

### Multimodal-first 设计原则
- 对图片类输入（截图、检验单、CT 报告、病理截图），应优先使用多模态 LLM
- 目标不是只识别字符，而是**直接完成结构化理解与语义抽取**
- 适用模型包括但不限于：
  - `step-1o-vision`
  - `gpt-5.4` 系列多模态能力
- OCR / layout 在此阶段定位为：
  - fallback
  - 可审计中间文本产物
  - 在无多模态、离线、隐私优先场景下的替代路径

### OCR backend 命名约定
为避免“同一种引擎的本地 / API 两种模式”混淆，`xyb` 统一采用以下 backend 命名：

- `paddle-local`
- `paddle-api`
- `mineru-local`
- `mineru-api`
- `tesseract`

默认 `auto` 选择顺序（OCR fallback 层）：

```text
paddle-local > paddle-api > mineru-local > mineru-api > tesseract
```

### API 配置约定
所有远程解析后端统一通过 `.env` / 环境变量配置，不允许把真实 token 写入源码或文档示例。

#### PaddleOCR API
- `PADDLEOCR_API_URL`
- `PADDLEOCR_API_TOKEN`
- `PADDLEOCR_API_MODEL`

#### MinerU API
- `MINERU_API_BASE_URL`
- `MINERU_API_TOKEN`

### MinerU API 设计约束
`mineru-api` 仅采用**精准解析 API**，不接入轻量 Agent API。

原因：
- 支持 batch
- 支持高精度输出
- 支持 zip 包结果
- 更适合复杂病历 / 扫描件 / 多格式结构化提取

必须处理的特殊流程：
- batch 上传 URL 申请
- 上传后自动触发解析
- 轮询任务状态
- 下载 `full_zip_url`
- 自动解压并提取 markdown / json

---

## 6. 输出协议与兼容策略

第一阶段建议尽量兼容 `graphify` 已验证的输出协议与工作流，以降低迁移风险。

### 短期策略
短期允许继续沿用：
- `graphify-out/` 输出目录形态
- 既有图谱产物协议
- 既有 report / export / analysis 产物格式

### 中期策略
在 `xyb` 稳定后，再评估是否将输出目录或产物命名整体改为 `xyb-out/`。

结论：

> 第一阶段优先“迁得稳、跑得通”，而不是急于重命名全部产物协议。

---

## 7. watch 与 incremental backfill 约束

以下经验已确认需要纳入 `xyb`：

### 7.1 macOS watch
- macOS 下默认使用 polling observer
- 允许环境变量覆盖 observer 模式
- 重点避免 FSEvents 在复杂目录、同步盘、截图/PDF 高频写入场景下的不稳定

### 7.2 incremental semantic backfill
必须保留并进一步固化以下闭环：

1. `plan`
   - 检测新增或缺失语义覆盖的文件
   - 生成 target list 与 chunk plan
2. `extract`
   - 仅对目标 chunk 做语义提取
3. `merge`
   - 在 `source_file` 归因可靠时替换旧结果
   - 不完整时追加并保留覆盖
4. `audit`
   - 输出 replaced / appended / unresolved / malformed 统计

### 7.3 chunk schema 规范
主 extraction JSON 应保持严格 schema：

```json
{
  "nodes": [],
  "edges": [],
  "hyperedges": [],
  "input_tokens": 0,
  "output_tokens": 0
}
```

并要求：
- `source_file` 为单字符串
- `chunk_id`、`source_files`、`summary`、`confidence_notes` 写入 sidecar audit 文件

---

## 8. 设计边界

### 当前明确保留
- `docs/`
- 独立项目目录
- `xyb` CLI
- `xyb/` 主包名
- graphify 主链迁移策略
- 本地安装 / 本地运行优先

### 当前明确放弃
- 继续沿用旧版 `core-py/ + mcp-ts/` 作为主架构
- 把 graphify 只当作“概念参考”
- 从零搭新主链

---

## 9. 当前生效开发顺序

### Phase 1：迁移与改名
- 以 `graphify` 结构为主迁移到新项目
- 主包名改为 `xyb`
- CLI 改为 `xyb`
- 跑通独立版本

### Phase 2：病情资料增强
- 逐步替换/增强 detect、report、watch、backfill、extract 逻辑
- 强化病情时间线与病情摘要输出
- 引入 `xyb init` 与用户目录模板落地能力
- 固化默认递归扫描子目录与噪声目录跳过规则

### Phase 3：再评估更高层接口
- 再决定是否增加独立 MCP 层、额外工具层或更强场景封装

### Phase 4（二期）：短视频摄取专项（中国平台优先）
- 本期不实现 `xyb add` 的在线视频平台下载链路（YouTube / 抖音 / B站 / 视频号）
- 二期优先做“本地导入优先”方案：
  - 本地视频/音频/字幕导入
  - 显式转写命令
  - 平台适配器接口预留（`bilibili` / `douyin` / `wechat_channels`）
- 二期再评估 URL 直连下载能力，避免平台反爬与稳定性问题影响主线

---

## 10. 当前结论

当前 `xyb` 项目的正确路线是：

> **以 `graphify` 的项目形态和成熟主链为主进行迁移，在新目录中形成独立的 `xyb` 项目，再在其上完成病情资料专病增强。**

这份文档自现在起为当前生效设计文档。
