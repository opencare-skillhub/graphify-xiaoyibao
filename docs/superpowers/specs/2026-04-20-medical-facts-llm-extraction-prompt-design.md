# xyb 医疗事实抽取 Prompt 设计

日期：2026-04-20  
状态：已确认（供 host / openclaw / stepfun 抽取器实现使用）

---

## 1. 目标

让 LLM 在**不负责图谱建边**的前提下，稳定完成：
- 医疗报告结构理解
- 事实级抽取
- 冲突复核
- 严格 JSON 输出

这里的 LLM 角色是：
> **信息抽取器（information extractor）**，不是自由总结器，也不是关系生成器。

---

## 2. 输入设计

LLM 输入分 3 层：

### 2.1 文档上下文
- `source_file`
- `document_kind`（可猜测）
- `report_date`（若已知）
- `panel_id`（若已切分）

### 2.2 结构化识别结果
优先输入：
- `content_list` 重建后的 panel 文本
- 关键 block / 行文本
- 可选 bbox 信息

### 2.3 原始视觉输入（可选增强）
用于：
- host multimodal
- stepfun-1o-vision
- OpenAI-compatible multimodal

说明：
- 对复杂截图，建议同时输入“图像 + 结构化文本”
- 对局部复核，建议输入“panel 局部图 + 候选文本”

---

## 3. 输出设计

LLM 必须输出**严格 JSON**，不输出解释段落。

### 主输出格式

```json
{
  "document_fact": { ... },
  "panel_facts": [ ... ],
  "observation_facts": [ ... ],
  "diagnosis_facts": [ ... ],
  "conflict_facts": [ ... ]
}
```

### 输出约束
- 所有数值字段必须为 number 或 null
- 不允许 markdown 包裹 JSON
- 不允许额外自然语言前后缀
- 不允许输出图谱关系边

---

## 4. Prompt 角色定义

### System Prompt（建议）

```text
你是医疗文档结构化抽取器。
你的任务不是总结，也不是生成图谱关系，而是从给定的医疗报告文本/图像中提取“结构化医疗事实”。
请严格输出 JSON。
禁止猜测不存在的值；无法确认时返回 null 或放入 conflict_facts。
必须区分：项目名称、结果值、单位、参考范围、异常标记、报告日期、证据文本。
不得把参考范围当结果值，不得把项目名称中的数字当结果值。
```

### User Prompt（主抽取）

```text
请从下面输入中提取结构化医疗事实。
要求：
1. 先识别 document_fact / panel_facts
2. 对检验类输出 observation_facts
3. 对影像结论输出 diagnosis_facts
4. 若候选值冲突、来源不明或 panel 混淆，写入 conflict_facts
5. 只输出 JSON

输入：
- source_file: ...
- panel_id: ...
- structured_text: ...
- optional_image_context: ...
```

---

## 5. 三类任务 Prompt 模式

### 5.1 主抽取模式
适用于：
- 单份检验单
- 单 panel 图像
- 单页 CT 报告

输出全部 facts。

### 5.2 冲突复核模式
适用于：
- 已经存在 `candidate_values`
- 需要在 2~3 个候选值中判断谁更可信

输入增加：
- `item_code`
- `candidate_values`
- `candidate_evidence`
- `panel_local_text`
- `optional_panel_crop`

输出格式：

```json
{
  "resolved_value": 15.7,
  "confidence": "high",
  "reason": "同一行中 CA19-9 与 15.70U/ml 对齐，50.0 来自 CA50 行",
  "evidence_text": "糖类抗原19-9(高值)...15.70U/ml"
}
```

### 5.3 拖底抽取模式
适用于：
- OCR/layout 结构较差
- 图像复杂但仍需尽量产出事实

要求：
- 置信度保守
- 可疑项尽量进 `conflict_facts`

---

## 6. 抽取策略要求

LLM 在抽取时必须遵守：

1. **panel 优先**：同一张对比图先区分 panel，再抽取事实
2. **行级优先**：同一行内的 marker-value 优先绑定
3. **证据强绑定**：每个 observation 必须附原文 evidence
4. **不能跨项目偷值**：若值明显属于其他行，必须冲突化，不得硬判
5. **不能根据 marker 名称数字猜值**：例如 `CA125` 的 `125` 不是结果值

---

## 7. 推荐调用策略

### 默认优先级
1. `host`（Codex / OpenClaw 默认模型）
2. `OPENAI_COMPAT_*` 指定模型
3. `stepfun-1o-vision`（复杂图或冲突复核）

### 路由建议
- 结构化文本较好：优先文本抽取 prompt
- 对比图 / 双 panel / 多候选冲突：优先视觉复核 prompt
- 单条 conflict：局部调用，不跑全量大图

---

## 8. 成本与稳定性控制

- 主抽取尽量基于 panel 文本，不必每次上传整图
- 只对 `conflict_facts` 调用视觉模型
- temperature 固定为 0
- 输出固定 JSON schema
- 每个 prompt 限定任务边界：只抽 facts，不做摘要

---

## 9. 评估指标

至少跟踪：
- 字段完整率
- 值准确率
- 参考范围误判率
- 多 panel 混淆率
- conflict 复核收敛率

---

## 10. 验收标准

1. `Picsew_20250306153026` 这类对比图能稳定抽出两个 panel 的事实
2. `ca125=7.28` 不会被 `1.53` 污染
3. `ca19_9=15.70` 不会被 `ca50` 行污染
4. 输出始终为严格 JSON

