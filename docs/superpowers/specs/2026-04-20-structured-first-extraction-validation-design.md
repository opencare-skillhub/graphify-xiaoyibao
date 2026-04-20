# xyb 结构化优先 + LLM 抽取校验 设计文档（方案B）

日期：2026-04-20  
状态：已确认（进入实现）

---

## 1. 背景与问题

当前主要痛点：
- 医疗报告图片中文 OCR 存在错位（尤其表格行列绑定）。
- MinerU `full.md` 线性化后会出现“项目名-结果值”错绑。
- 仅靠模板规则不可持续，新报告形态持续变化。

结论：不能走“模板穷举”。必须走**结构化优先 + AI语义抽取 + 校验闭环**。

---

## 2. 设计目标

1. 以结构化数据为主，不依赖模板硬编码。  
2. 抽取链路可解释、可追踪、可复核。  
3. 运行中可见“抽取阶段 + 校验阶段”进度。  
4. 冲突数据不直接污染趋势主表。  

---

## 3. 总体方案（方案B）

`OCR/layout -> 结构化重建 -> LLM抽取 -> 校验 -> 入图谱/趋势`

### 3.1 数据源优先级
1) `content_list.json / layout.json`（主）  
2) `full.md`（次）  
3) 纯文本 OCR（兜底）

### 3.2 抽取原则
- 优先按行列关系绑定“项目/结果/单位/参考范围”。
- 支持值在项目名前后的乱序情况（OCR常见）。
- 标记字段必须分离：`value` 与 `reference_range` 不能混用。

### 3.3 校验原则
- **结构校验**：字段完整性、类型、单位合法性。
- **语义校验**：结果值不得等同参考区间上下界。
- **差异校验**：多来源结果冲突时触发复核（可接 stepfun-1o-vision）。

---

## 4. 统一数据契约（核心）

标准记录（normalized）：
- `source_file`
- `date`
- `marker_key` / `marker_label`
- `value`
- `unit`
- `ref_low` / `ref_high`（可空）
- `confidence`
- `evidence`（页面、bbox、原文片段）
- `status`（`ok` / `conflict` / `review_needed`）

冲突记录（validation）：
- `source_file`
- `field`
- `value_a` / `value_b`
- `reason`
- `resolver`（规则/LLM/人工）

---

## 5. 进度与可观测性

CLI 增加双阶段进度：
- `[xyb] extracting ... i/N (%)`
- `[xyb] validating ... i/N (%)`

并在结束时输出汇总：
- 抽取：`success / failed / empty`
- 校验：`ok / conflict / review_needed`
- 日志与报告路径

---

## 6. 冲突处理策略

1. 抽取成功且校验通过：进入主数据。  
2. 抽取成功但校验冲突：进入 `validation_conflicts.jsonl`，不入主趋势。  
3. 低置信度或字段不全：进入 `review_queue.jsonl`。  
4. 可选二次复核：调用 stepfun-1o-vision 对冲突条目做局部复核。  

---

## 7. 非目标（明确不做）

- 不做医院/系统模板硬编码穷举。  
- 不以单一 OCR 文本顺序作为唯一真值。  
- 不直接将未校验值写入趋势主表。  

---

## 8. 验收标准

1. 关键样本（含 `IMG_6301/6067/6070/6309`）可复现。  
2. `value` 与 `reference_range` 分离正确。  
3. 冲突条目可追踪、可复核、可重跑。  
4. 运行时可见抽取与校验两段进度。  

