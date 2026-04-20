# xyb 医疗事实到图谱编译器设计

日期：2026-04-20  
状态：已确认（事实层稳定后实施）

---

## 1. 目标

将 `medical facts` 作为**单一事实源（single source of truth）**，通过确定性程序逻辑编译为图谱节点和关系。

核心原则：
- 图谱关系由程序生成，不由 LLM 直接输出
- 冲突事实不进入主图谱
- 证据始终可反查

---

## 2. 编译输入

输入为 4 类 JSONL：
- `document_facts.jsonl`
- `panel_facts.jsonl`
- `observation_facts.jsonl`
- `diagnosis_facts.jsonl`

只编译满足以下条件的事实：
- `status == ok`
- `confidence != low`（可配置）

对于：
- `conflict`
- `review_needed`
- `rejected`

默认不进入主图谱，仅进入审计侧产物。

---

## 3. 图谱节点模型

### 3.1 文档节点
- `Document`
- 唯一键：`source_file + report_date + panel_id?`

### 3.2 面板节点
- `Panel`
- 用于对比图、拼图、多报告场景

### 3.3 检验项节点
- `Observation`
- 表示一次具体检验结果，不是抽象概念词

### 3.4 指标概念节点
- `Marker`
- 如：`CA19-9`, `CEA`, `AFP`

### 3.5 影像诊断节点
- `ImagingFinding`
- `Impression`

### 3.6 解剖部位节点
- `Anatomy`

### 3.7 证据节点（可选）
- `Evidence`
- 用于强审计场景

---

## 4. 图谱边模型

### 检验类主边
- `Document -> HAS_PANEL -> Panel`
- `Panel -> HAS_OBSERVATION -> Observation`
- `Observation -> OF_MARKER -> Marker`
- `Observation -> HAS_EVIDENCE -> Evidence`（可选）

### Observation 属性
建议直接挂属性，不必全部拆边：
- `value`
- `unit`
- `reference_range`
- `ref_low`
- `ref_high`
- `abnormal_flag`
- `report_date`
- `confidence`

### 影像类主边
- `Document -> HAS_IMAGING_FINDING -> ImagingFinding`
- `ImagingFinding -> LOCATED_IN -> Anatomy`
- `ImagingFinding -> HAS_IMPRESSION -> Impression`

---

## 5. 为什么不用 LLM 直接生成关系

因为这样会引入三个问题：

1. 关系命名漂移（`mentions/contains/describes/reports` 混乱）
2. 同一事实重复建边
3. 一旦 OCR 或抽取偏差，错误会直接扩散到图谱

所以正确做法是：
> LLM 负责事实抽取，编译器负责关系生成。

---

## 6. 编译流程

### Phase A：事实清洗
- 过滤 `status != ok`
- 标准化 marker 名称
- 标准化单位
- 规范日期

### Phase B：实体归一
- `CA19-9` / `糖类抗原19-9` -> 同一 `Marker`
- 相同 `source_file + panel_id + item + date + value` 的 observation 去重

### Phase C：生成节点
- 先文档、再 panel、再 observation / diagnosis、再概念节点

### Phase D：生成边
- 根据编译规则生成稳定边
- 不允许动态 invent relation 名称

### Phase E：生成审计侧产物
- `graph_compile_audit.json`
- 记录跳过的 facts、冲突 facts、去重情况

---

## 7. ID 设计

所有图谱节点 ID 建议稳定生成：
- `doc_<sha1>`
- `panel_<sha1>`
- `obs_<sha1>`
- `marker_<normalized_name>`
- `finding_<sha1>`

Observation 的 key 建议：
- `source_file + panel_id + report_date + item_code + value + unit`

这样可支持增量更新与幂等重跑。

---

## 8. 与趋势/报告的关系

趋势不应再从松散 graph label 反推，应该：

- **趋势主数据源：`observation_facts.jsonl`**
- 图谱仅作导航、检索、可视化

也就是说：
- `tumor_markers_trend.csv` 从 facts 生成
- graph 只是副产物，而不是唯一真值源

---

## 9. 审计与可解释性

建议输出：
- `graph_compile_audit.json`
- `skipped_facts.jsonl`
- `compiled_nodes_edges_summary.json`

最低要求：
- 每个 Observation 节点都能回指 `source_file/panel_id/evidence`
- 用户能从图谱回看到原报告证据

---

## 10. 实施顺序建议

1. 先稳定 `medical facts`
2. 再做 `facts -> graph compiler`
3. 再让报告/趋势切换到 facts 主源
4. 最后缩减旧的弱规则图谱生成路径

---

## 11. 验收标准

1. graph 中不再出现大量弱语义 `mentions/co_occurs_with` 污染主事实层
2. markers 趋势与 facts 一致
3. 对比图 / 多 panel 输入不会把两份报告编进同一个 observation
4. 所有主图谱边都可由事实层反推复现

