# 2026-04-18 CLI 回归修复（Round 2）

## 背景
- 用户连续触发 CLI 报错（`xyb --help`、`xyb process`、安装与入口行为不一致）。
- 目标：稳定 `uv + editable` 安装链路，补齐 `process` 主流程，修复语法/依赖/命令回归。

## 原因 - 类型 - 分析 - 修复

### 1) `ModuleNotFoundError: networkx`
- **类型**：打包/依赖缺失
- **原因**：`pyproject.toml` 未声明运行时依赖
- **修复**：
  - 在 `[project.dependencies]` 增加 `networkx>=3.0`
  - 增加 optional 依赖分组（`watch/pdf/office/dicom/neo4j`）

### 2) `xyb process` 不存在
- **类型**：CLI 入口功能缺失
- **原因**：子命令未注册，主线仍偏向 `analyze`（代码 AST）
- **修复**：
  - 新增 `process` 子命令（`xyb/__main__.py`）
  - 新增 `xyb/process.py`：medical-first 主线
    - 输入：目录扫描结果（非代码）
    - 输出：`graph.json`、`graph.html`、`GRAPH_REPORT.md`、`.graphify_detect.json`、`.graphify_extract.json`

### 3) DICOM 未作为独立类型
- **类型**：业务分类遗漏
- **原因**：`.dcm` 被归为 `document`
- **修复**：
  - `xyb/detect.py` 增加 `FileType.DICOM`
  - `classify_file` 支持扩展名 + DICM 魔术头识别
  - 扫描统计新增 `dicom` 分类

### 4) 代码扫描未按 xyb 场景收敛
- **类型**：场景偏离
- **原因**：沿用 graphify code-first 默认
- **修复**：
  - `xyb/detect.py` 中 `CODE_EXTENSIONS` 置空（保留符号兼容）
  - 主流程使用 `process`（文档/PDF/图片/视频/DICOM）

### 5) 抽取校验告警（invalid file_type）
- **类型**：schema 不一致
- **原因**：校验允许类型集合过旧（缺 `video/dicom`）
- **修复**：
  - `xyb/validate.py` 扩展 `VALID_FILE_TYPES`
  - `process` 根节点类型调整为合法值（`document`）

### 6) pytest 收集冲突（legacy tests import mismatch）
- **类型**：测试配置污染
- **原因**：`docs/archive` 中历史测试被 pytest 递归收集
- **修复**：
  - `pyproject.toml` 增加 pytest 配置：
    - `testpaths = ["tests"]`
    - `norecursedirs` 排除 `docs/archive`

## 影响文件
- `pyproject.toml`
- `xyb/__main__.py`
- `xyb/detect.py`
- `xyb/validate.py`
- `xyb/report.py`
- `xyb/process.py`（新增）
- `xyb/dicom.py`（新增）
- `README.md`
- `README.en.md`
- `tests/test_detect.py`

## 验证结果
- 语法检查：`python -m py_compile` 全通过
- 测试：`pytest -q` → **61 passed**
- CLI：
  - `xyb --help` 正常
  - 所有子命令 `--help` 逐个校验通过
  - `xyb process <dir>` 可产出图谱与报告，且统计 `dicom_count`

## 后续回归排障补充：中文 OCR 问题

### 问题现象
- 新增中文截图（肿瘤标志物 / CT 报告）扫描到目录后，图谱中未稳定出现对应医学实体。
- 图片本身清晰，但 OCR 与后续关系抽取结果失真。

### 根因
- 本机 `tesseract` 环境缺少中文语言包，`--list-langs` 仅有：
  - `eng`
  - `osd`
  - `snum`
- 这会导致中文图片退化为英文 OCR 路径，后续概念抽取质量显著下降。

### 修复方向
- 代码层面已改为中文优先语言选择策略（优先 `chi_sim+eng`）
- 文档层面已明确：
  - 中文是核心语言
  - OCR 不得静默退化
  - PaddleOCR 应作为本地主力方案
  - MinerU 作为开放增强方案
  - Tesseract 作为拖底方案

### 备注
- `graphify-out/graph.json` 在当前项目中仅作**参考/对比用途**
- `xyb process` 的主输入应来自：
  - 实际扫描文件
  - 标准化 chunk / semantic 中间产物
  - `xyb` 自身抽取链路
