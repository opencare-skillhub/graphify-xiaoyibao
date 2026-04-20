# xyb 医疗事实抽取 Schema 设计

日期：2026-04-20  
状态：已确认（供方案B实现使用）

---

## 1. 目标

把 OCR / layout / multimodal 的输出，统一收敛为**结构化医疗事实（medical facts）**，再由程序确定性编译为图谱、趋势和报告。

核心原则：
- 不让 LLM 直接产出图谱边
- 不让规则直接决定最终医学值
- 先抽“事实”，再编译“关系”
- 每条事实都必须有 `evidence`

---

## 2. 适用范围

一期优先覆盖：
- 肿瘤标志物 / 检验单截图
- 血液 / 生化检验报告
- CT / 影像学报告截图或 PDF

二期扩展：
- 病理报告
- 出院小结
- DICOM 派生结构化事实

---

## 3. 顶层对象模型

统一抽取结果由 4 类对象组成：

1. `document_fact`
2. `panel_fact`
3. `observation_fact`
4. `diagnosis_fact`

其中：
- 检验类主对象是 `observation_fact`
- 影像结论类主对象是 `diagnosis_fact`
- `document_fact` / `panel_fact` 负责来源和结构上下文

---

## 4. 通用字段

所有事实对象共用：

- `fact_id`: 稳定 ID
- `fact_type`: 对象类型
- `source_file`: 原始文件路径
- `panel_id`: 面板标识；单面板为空，多面板时如 `panel_1`
- `page_index`: 页码 / 图片页索引
- `report_date`: 报告日期，ISO 格式优先
- `confidence`: `high | medium | low`
- `status`: `ok | conflict | review_needed | rejected`
- `evidence`: 证据对象
- `meta`: 扩展元数据

### `evidence` 结构

```json
{
  "text": "糖类抗原19-9(高值) 15.70U/ml",
  "bbox": [72, 1440, 1080, 1518],
  "page_index": 0,
  "source_backend": "mineru-api",
  "source_kind": "content_list"
}
```

说明：
- `text` 是主证据文本
- `bbox` 可为空，但建议保留
- `source_backend` 记录识别来源（mineru / paddle / host-mm）

---

## 5. 文档级 Schema

### 5.1 `document_fact`

```json
{
  "fact_id": "doc_sha1_xxx",
  "fact_type": "document_fact",
  "source_file": "raw/IMG_6301.PNG",
  "report_date": "2026-03-31",
  "document_kind": "lab_report",
  "department": "胰腺胆道专病门诊",
  "panel_count": 1,
  "confidence": "high",
  "status": "ok",
  "evidence": { ... },
  "meta": {}
}
```

### 5.2 `panel_fact`

```json
{
  "fact_id": "panel_sha1_xxx",
  "fact_type": "panel_fact",
  "source_file": "raw/Picsew_20250306153026.JPEG",
  "panel_id": "panel_1",
  "report_date": "2025-03-06",
  "panel_role": "comparison_left",
  "confidence": "medium",
  "status": "ok",
  "evidence": { ... },
  "meta": {}
}
```

说明：
- `panel_fact` 用来承接 Picsew 这类左右对比图
- 后续 observation / diagnosis 都归属于 panel，而不是直接归整个文件

---

## 6. 检验类事实 Schema

### 6.1 `observation_fact`

```json
{
  "fact_id": "obs_sha1_xxx",
  "fact_type": "observation_fact",
  "source_file": "raw/Picsew_20250306153026.JPEG",
  "panel_id": "panel_1",
  "report_date": "2025-03-06",
  "category": "lab",
  "item_code": "ca19_9",
  "item_name": "CA19-9",
  "value": 15.7,
  "unit": "U/mL",
  "reference_range": "0-27 U/mL",
  "ref_low": 0,
  "ref_high": 27,
  "abnormal_flag": "high",
  "confidence": "high",
  "status": "ok",
  "evidence": { ... },
  "meta": {
    "raw_item_name": "糖类抗原19-9(高值)",
    "source_backend": "mineru-api"
  }
}
```

### 6.2 字段约束

- `item_code`：统一标准 key，例如：
  - `ca19_9`
  - `cea`
  - `afp`
  - `ca125`
  - `ca50`
  - `ca72_4`
- `value` 必须是数值，不允许字符串主存
- `unit` 必须标准化，如 `U/mL`, `ng/mL`
- `reference_range` 可以保留原始字符串
- `ref_low/ref_high` 为可选解析字段
- `abnormal_flag` 允许：`high | low | normal | unknown`

---

## 7. 影像/诊断类事实 Schema

### `diagnosis_fact`

```json
{
  "fact_id": "dx_sha1_xxx",
  "fact_type": "diagnosis_fact",
  "source_file": "raw/IMG_6309.PNG",
  "panel_id": "",
  "report_date": "2026-04-28",
  "category": "imaging",
  "study_type": "CT",
  "finding": "胰头不规则肿块，范围较前相仿，目前大小约27*19mm",
  "impression": "腹膜网膜、肝包膜多发强化结节，较前相仿",
  "anatomy": ["胰头", "肝脏", "腹膜", "网膜"],
  "confidence": "medium",
  "status": "ok",
  "evidence": { ... },
  "meta": {}
}
```

说明：
- 影像类不强行拆成“过多边”
- 先沉淀成稳定 facts，再决定如何编译图谱

---

## 8. 冲突与复核 Schema

### `conflict_fact`

```json
{
  "fact_id": "conflict_sha1_xxx",
  "fact_type": "conflict_fact",
  "source_file": "raw/Picsew_20250306153026.JPEG",
  "panel_id": "panel_1",
  "report_date": "2025-03-06",
  "item_code": "ca125",
  "candidate_values": [1.53, 7.28],
  "conflict_type": "binding_conflict",
  "status": "review_needed",
  "confidence": "low",
  "evidence": { ... },
  "meta": {
    "source_candidates": ["降钙素 1.53pg/ml", "糖类抗原CA125 7.28U/ml"]
  }
}
```

### 冲突类型建议

- `binding_conflict`：绑定错误候选
- `multi_panel_conflict`：多面板对比图混入同一组
- `ocr_conflict`：识别文本本身冲突
- `llm_conflict`：多模型抽取结果不一致

---

## 9. 存储与文件产物

建议输出：

- `normalized/document_facts.jsonl`
- `normalized/panel_facts.jsonl`
- `normalized/observation_facts.jsonl`
- `normalized/diagnosis_facts.jsonl`
- `normalized/conflict_facts.jsonl`

说明：
- `markers.jsonl` 后续可作为 `observation_facts.jsonl` 的一个视图/兼容产物
- 主事实层不再只围绕 markers 设计

---

## 10. 验收标准

1. 同一张报告的事实可稳定复现
2. 多面板图片不会把左右两份报告混为一体
3. 指标名称中的数字（如 `CA125`）不会被误当结果值
4. 每条入库事实都能追溯到 `evidence`

