# xyb OCR 后端增强计划

日期：2026-04-18  
状态：草案 / 待执行

---

## 1. 目标

将 `xyb` 的中文医疗资料解析链正式升级为：

> **Multimodal LLM（主链） → OCR/layout（fallback） → Tesseract（拖底）**

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

### L1：Multimodal LLM
- 作为图片解析主链
- 重点处理：
  - 肿瘤标志物截图
  - CT / 放射学报告截图
  - 检验单 / 病理单
- 目标：
  - 直接完成视觉理解
  - 直接输出结构化抽取结果
  - 减少手写规则与 OCR 误差传递

### L2：OCR / layout fallback
- 作为 fallback 与可审计中间产物
- 包括：
  - `paddle-local`
  - `paddle-api`
  - `mineru-local`
  - `mineru-api`

### L3：Tesseract
- 作为拖底兜底路径
- 仅在更强 backend 不可用时使用

### L4：MinerU / Paddle layout 增强
- 用于复杂 PDF / 扫描件 / 版面恢复
- 重点处理：
  - 多页 PDF
  - 扫描文档
  - 复杂版式恢复
- 接入形态：
  - 本地 CLI
  - API（上传 / 解析 / 轮询）

---

## 4. 任务拆解

### 任务 A：多模态抽取 backend 抽象
- 新增统一 image extract backend 接口
- 支持：
  - `multimodal`
  - `ocr-fallback`
  - `tesseract`

交付物建议：
- `xyb/ocr.py`
- `xyb/ocr_backends/`
- `xyb/mm_extract.py`

### 任务 B：Tesseract 逻辑迁移整理
- 将 `xyb/process.py` 中现有 Tesseract 逻辑抽离
- 保持现有 best-effort 行为
- 补中文语言包告警

### 任务 C：OCR/layout fallback 层
- 增加 optional dependency
- 封装 Paddle / MinerU / Tesseract
- 输出统一文本 / block 结构
- 仅在多模态不可用时启用

### 任务 D：Multimodal backend
- 对图片类输入优先调用多模态模型
- 输出结构化 JSON / 图谱抽取中间表示
- 必要时再回退 OCR 文本

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
