# xyb 结构化优先 + LLM 抽取校验 实施计划

日期：2026-04-20  
对应设计：`docs/superpowers/specs/2026-04-20-structured-first-extraction-validation-design.md`  
状态：执行中

---

## Phase 0：基线与回滚

- [ ] 提交当前代码基线（便于回滚）
- [ ] 固化样本集清单（重点：`IMG_6301/6067/6070/6309`）
- [ ] 记录当前指标（抽取正确率、冲突率）

---

## Phase 1：结构化重建主链

目标：摆脱 `full.md` 线性错位，优先结构化 JSON。

### 任务
- [ ] `xyb/ocr.py`：MinerU 单文件优先 `content_list/layout` 重建
- [ ] `xyb/mineru_batch.py`：批处理同样优先结构化重建
- [ ] 增加行列排序/合并策略（按 page+y+x）

### 验收
- [ ] 同图重复运行结果稳定
- [ ] 关键样本可读行顺序正确

---

## Phase 2：字段级抽取与校验

目标：统一 schema，并引入校验状态机。

### 任务
- [ ] `xyb/normalized.py`：输出 `value/ref/confidence/evidence/status`
- [ ] 增加校验器模块（建议：`xyb/validation.py`）
  - [ ] 结构校验
  - [ ] 语义校验
  - [ ] 差异校验
- [ ] 冲突/待复核落盘：
  - [ ] `validation_conflicts.jsonl`
  - [ ] `review_queue.jsonl`

### 验收
- [ ] `value` 与 `reference_range` 无混淆
- [ ] 冲突不会写入主趋势

---

## Phase 3：CLI 进度与报告增强

目标：让用户实时看到“抽取 + 校验”过程。

### 任务
- [ ] `xyb/process.py`：增加 extracting/validating 双阶段进度
- [ ] 结果汇总加入：
  - [ ] 抽取统计
  - [ ] 校验统计
  - [ ] 日志路径
  - [ ] 冲突文件路径

### 验收
- [ ] 运行中可见两段进度
- [ ] 最终输出包含成功/失败/冲突统计

---

## Phase 4：LLM 复核通道（stepfun）

目标：对冲突条目做局部二次复核，不拖慢全量。

### 任务
- [ ] 新增复核开关（env/cli）
- [ ] 仅对 `conflict/review_needed` 条目调用 stepfun
- [ ] 复核决策落盘（包含来源与理由）

### 验收
- [ ] 冲突条目可收敛
- [ ] 不影响全量吞吐

---

## Phase 5：测试与文档

### 测试
- [ ] 单测：结构化重建、marker抽取、校验器
- [ ] 集成：`xyb process` / `xyb full-update`
- [ ] 回归：关键样本结果对齐

### 文档
- [ ] README：方案B链路、配置项、排障
- [ ] 设计/计划/报告同步

---

## 风险与对策

1. OCR 源数据本身错误（如 28.6 -> 128.6）  
对策：冲突标记 + LLM 局部复核 + 人工队列。

2. 不同后端文本风格差异大  
对策：统一 schema 与验证层，不把后端输出直接入库。

3. 进度显示导致刷屏  
对策：TTY 动态刷新 + 非TTY分段节流。

---

## 完成定义（DoD）

- [ ] 关键样本 CA19-9 等指标抽取准确  
- [ ] 校验状态可追踪（ok/conflict/review_needed）  
- [ ] 产物文件完整（日志/冲突/复核队列）  
- [ ] CLI 双阶段进度可见  
- [ ] 测试通过并可复现  

