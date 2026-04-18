# xyb OCR 后端增强计划

日期：2026-04-18  
状态：草案 / 待执行

---

## 1. 目标

将 `xyb` 的中文医疗资料解析链正式升级为：

> **PaddleOCR（隐私/本地主力） → MinerU（开放增强） → Tesseract（拖底）**

并把该能力稳定接入：

- `xyb process`
- `xyb full-update`
- 图谱关系抽取
- README / 设计 / 开发文档

---

## 2. 核心原则

- 中文优先，而不是英文优先
- 本地优先、隐私优先
- API / 外部服务是增强，不是唯一依赖
- OCR backend 必须是 `xyb` Python 主代码能力，不依赖 skill 才可用
- skill 负责稳定工作流、安装说明、操作规程，不承载主业务逻辑

---

## 3. 能力分层

### L1：PaddleOCR
- 作为本地主力 OCR
- 重点处理：
  - 肿瘤标志物截图
  - CT / 放射学报告截图
  - 检验单 / 病理单

### L2：MinerU
- 作为开放增强链
- 重点处理：
  - 多页 PDF
  - 扫描文档
  - 复杂版式恢复
- 接入形态优先级：
  1. 本地 CLI
  2. API（上传 / 解析 / 轮询）

### L3：Tesseract
- 作为最小闭环兜底
- 保留本地 `subprocess` 调用方式

---

## 4. 任务拆解

### 任务 A：OCR backend 抽象
- 新增统一 backend 接口
- 统一输入输出 contract
- 支持：
  - `auto`
  - `paddle`
  - `mineru`
  - `tesseract`

交付物建议：
- `xyb/ocr.py`
- `xyb/ocr_backends/`

### 任务 B：Tesseract 逻辑迁移整理
- 将 `xyb/process.py` 中现有 Tesseract 逻辑抽离
- 保持现有 best-effort 行为
- 补中文语言包告警

### 任务 C：PaddleOCR backend
- 增加 optional dependency
- 封装本地 PaddleOCR 调用
- 输出统一文本 / block 结构
- 在 `auto` 策略中优先于 Tesseract

### 任务 D：MinerU backend
- 先调研并确定接入路径：
  - 本地 CLI
  - API
- 若先做 API：
  - token 配置
  - 文件上传
  - 解析任务提交
  - 状态轮询
  - 结果归一化

### 任务 E：process 主链接入
- `xyb process` 支持 `--ocr-backend`
- `xyb full-update` 透传 OCR backend
- `auto = paddle > mineru > tesseract`

### 任务 F：医学图片结构化抽取
- 肿瘤标志物截图专用抽取
- CT / 放射学报告截图专用抽取
- 保证 OCR 改善后，关系能稳定入图

### 任务 G：测试与回归
- 单测：
  - backend 选择逻辑
  - fallback 逻辑
  - 配置与告警
- 集成测试：
  - `xyb process`
  - `xyb full-update`
- 样本验证：
  - `IMG_6301.PNG`
  - `IMG_6309.PNG`

### 任务 H：Skill / 文档
- 新增 OCR 相关 skill（可选）
- README 更新安装说明
- 设计 / 开发 / 排障文档同步

---

## 5. 建议执行顺序

1. 保存当前基线
2. 做 OCR backend 抽象
3. 迁移 Tesseract
4. 接入 PaddleOCR
5. 接入 MinerU
6. 接入 `process` / `full-update`
7. 做结构化抽取与回归测试
8. 完成 skill 与文档

---

## 6. 当前基线版本

- branch: `main`
- baseline commit: `5abf667`
- message: `chore: save OCR strategy baseline before backend refactor`

