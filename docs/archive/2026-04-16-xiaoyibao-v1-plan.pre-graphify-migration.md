# xiaoyibao (xyb) V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 graphify 思路落地 xyb v1：完成肿瘤患者病情资料目录整理、文档识别、医学要素抽取、时间线图谱、报告生成、MCP 与 Skill 闭环。

**Architecture:** 采用双运行时单仓结构：`core-py/` 承担文档摄取、抽取、图谱、报告和增量更新，`mcp-ts/` 提供本地 Node CLI、MCP Server、Skill 封装。Graphify 的 NetworkX / cache / report / serve 主干保留，但 AST 代码分析改造成医学病情图谱管线；v1 安装以仓库内本地运行优先，不假设 pip / npm registry 发布。

**Tech Stack:** Python 3.11+, pytest, NetworkX, pydicom, pypdf, python-docx, openpyxl, Pillow, watchdog, Node.js 20+, TypeScript, npm, Vitest, MCP SDK, uv/venv 本地运行

---

## Target file structure

- `README.md` — 项目说明、安装、快速开始
- `core-py/pyproject.toml` — Python 包配置，脚本名 `xyb-py`
- `core-py/src/xyb_core/cli.py` — Python CLI 入口
- `core-py/src/xyb_core/config.py` — `xyb.toml` 加载与默认配置
- `core-py/src/xyb_core/cache.py` — 复用 graphify 风格文件指纹缓存
- `core-py/src/xyb_core/ingest/classify.py` — 文件类型识别
- `core-py/src/xyb_core/ingest/scan.py` — 目录扫描与 manifest 构建
- `core-py/src/xyb_core/ingest/url_snapshot.py` — URL 正文抓取与快照保存
- `core-py/src/xyb_core/extract/models.py` — 医学 schema dataclass / TypedDict
- `core-py/src/xyb_core/extract/providers/base.py` — Provider 抽象接口
- `core-py/src/xyb_core/extract/providers/openai_compatible.py` — OpenAI 兼容 provider
- `core-py/src/xyb_core/extract/pipeline.py` — 文档→病情要素抽取总管线
- `core-py/src/xyb_core/graph/build.py` — 时间线 + 医学主题图谱构建
- `core-py/src/xyb_core/report/render.py` — Markdown/HTML/PDF 报告渲染
- `core-py/src/xyb_core/report/templates/report.md.j2` — Markdown 模板
- `core-py/src/xyb_core/watch.py` — 跨平台 watcher 策略、macOS polling 回退、变更通知
- `core-py/src/xyb_core/update.py` — 标准化 semantic backfill 的 plan/extract/merge/audit 编排
- `core-py/src/xyb_core/mcp_payload.py` — 提供给 Node MCP 的查询载荷层
- `core-py/src/xyb_core/output.py` — 写出 `xyb-out/` 产物
- `core-py/src/xyb_core/semantic/merge.py` — chunk schema 标准化、`source_file` merge、audit 汇总
- `core-py/tests/...` — Python 单测/集成测试
- `mcp-ts/package.json` — Node 包定义，暴露 `xyb` 和 `xyb-mcp`
- `mcp-ts/src/cli.ts` — 默认 `xyb` CLI
- `mcp-ts/src/pythonBridge.ts` — 调用 repo-local Python 运行时的桥接层（不依赖全局 pip 安装）
- `mcp-ts/src/server.ts` — MCP stdio server
- `mcp-ts/src/tools/*.ts` — MCP tools
- `mcp-ts/skills/*.md` — 多平台 skill 模板
- `mcp-ts/tests/*.test.ts` — Node/Vitest 测试
- `scripts/dev/install_local.sh` — v1 本地安装与启动脚本

## 2026-04-16 经验回灌（必须吸收）

1. **macOS watch 稳定性**
   - `core-py/src/xyb_core/watch.py` 必须提供 `XYB_WATCH_OBSERVER=auto|native|polling` 选择逻辑。
   - `auto` 在 Darwin 上默认走 polling，避免 FSEvents 在截图、扫描件、同步目录场景下漏事件。
   - `core-py/tests/test_watch.py` 至少覆盖：默认值、非法值回退、`native` / `polling` 显式覆盖、Darwin 默认 polling。

2. **doc/pdf/image 标准化增量 semantic backfill 闭环**
   - `xyb update` 不能只给出 `needs_update` 提示；必须在设计上留出 `plan → extract → merge → audit` 闭环。
   - 主 extraction JSON 严格限定为 `nodes/edges/hyperedges/input_tokens/output_tokens`；`chunk_id`、`source_files`、`summary`、`confidence_notes` 放到 audit sidecar。
   - merge 规范要求 node / edge 的 `source_file` 为单字符串，并且 detect 出现的每个文件最终都要有明确归宿：replaced / appended / placeholder / unresolved。

3. **v1 部署方式修正为本地安装**
   - README、脚本、测试、Node Python bridge 不得假设全局 `pip install graphify` 式体验。
   - v1 只要求仓库内可运行：如 `uv run --project core-py ...`、`npm --prefix mcp-ts ...` 或项目内虚拟环境。
   - pip / npm 公共发布延后，不作为第一版验收条件。

### Task 1: 初始化单仓骨架并导入 graphify 可复用主干

**Files:**
- Create: `README.md`
- Create: `core-py/pyproject.toml`
- Create: `core-py/src/xyb_core/__init__.py`
- Create: `core-py/src/xyb_core/cli.py`
- Create: `core-py/src/xyb_core/cache.py`
- Create: `core-py/tests/test_cli_smoke.py`
- Create: `mcp-ts/package.json`
- Create: `mcp-ts/tsconfig.json`
- Create: `mcp-ts/vitest.config.ts`
- Create: `mcp-ts/src/cli.ts`
- Create: `mcp-ts/tests/cli.test.ts`
- Modify: `docs/superpowers/specs/2026-04-14-xiaoyibao-v1-design.md`

- [ ] **Step 1: 写 Python CLI 失败测试**

```python
from typer.testing import CliRunner
from xyb_core.cli import app


def test_cli_shows_top_level_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "scan" in result.stdout
    assert "report" in result.stdout
    assert "serve" in result.stdout
```

- [ ] **Step 2: 运行测试，确认当前失败**

Run: `cd core-py && pytest tests/test_cli_smoke.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'xyb_core'`

- [ ] **Step 3: 写 Python 包基础骨架**

```python
# core-py/src/xyb_core/cli.py
import typer

app = typer.Typer(help="xiaoyibao patient knowledge graph CLI")

@app.command()
def scan(path: str) -> None:
    print(f"scan {path}")

@app.command()
def report() -> None:
    print("report")

@app.command()
def serve() -> None:
    print("serve")
```

```toml
# core-py/pyproject.toml
[project]
name = "xyb-core"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["typer>=0.12", "networkx", "pytest"]

[project.scripts]
xyb-py = "xyb_core.cli:app"
```

- [ ] **Step 4: 重新运行 Python smoke 测试**

Run: `cd core-py && pytest tests/test_cli_smoke.py -v`
Expected: PASS

- [ ] **Step 5: 写 Node CLI 失败测试**

```ts
import { describe, expect, it } from 'vitest'
import { buildCommand } from '../src/cli'

describe('xyb cli', () => {
  it('registers scan/report/serve commands', () => {
    const program = buildCommand()
    const names = program.commands.map((cmd) => cmd.name())
    expect(names).toContain('scan')
    expect(names).toContain('report')
    expect(names).toContain('serve')
  })
})
```

- [ ] **Step 6: 运行 Node 测试，确认当前失败**

Run: `npm --prefix mcp-ts test`
Expected: FAIL with `Cannot find module '../src/cli'`

- [ ] **Step 7: 写 Node 包与 CLI 最小实现**

```ts
// mcp-ts/src/cli.ts
import { Command } from 'commander'

export function buildCommand(): Command {
  const program = new Command().name('xyb')
  program.command('scan <path>')
  program.command('report')
  program.command('serve')
  return program
}

if (require.main === module) {
  buildCommand().parse(process.argv)
}
```

```json
// mcp-ts/package.json
{
  "name": "@pancrepal/xyb",
  "version": "0.1.0",
  "type": "commonjs",
  "bin": {
    "xyb": "dist/cli.js"
  },
  "scripts": {
    "build": "tsc -p tsconfig.json",
    "test": "vitest run"
  },
  "dependencies": {
    "commander": "^13.0.0"
  },
  "devDependencies": {
    "typescript": "^5.8.0",
    "vitest": "^3.0.0"
  }
}
```

- [ ] **Step 8: 运行 Node 测试确认通过**

Run: `npm --prefix mcp-ts test`
Expected: PASS

- [ ] **Step 9: 补 README 顶部和 monorepo 目录说明**

```md
# llm-wiki-xiaoyibao

- `core-py/`: Python 核心处理引擎
- `mcp-ts/`: Node CLI / MCP / Skill / npm 发布层
- `docs/`: 设计与计划文档
```

- [ ] **Step 10: Commit**

```bash
git add README.md core-py mcp-ts docs/superpowers/specs/2026-04-14-xiaoyibao-v1-design.md
git commit -m "chore: scaffold xyb monorepo baseline"
```

### Task 2: 实现目录扫描、文件识别、URL 快照与标准目录建议

**Files:**
- Create: `core-py/src/xyb_core/config.py`
- Create: `core-py/src/xyb_core/ingest/__init__.py`
- Create: `core-py/src/xyb_core/ingest/classify.py`
- Create: `core-py/src/xyb_core/ingest/scan.py`
- Create: `core-py/src/xyb_core/ingest/url_snapshot.py`
- Create: `core-py/src/xyb_core/templates/init_tree/README_如何整理.md`
- Create: `core-py/tests/test_classify.py`
- Create: `core-py/tests/test_scan_manifest.py`
- Create: `core-py/tests/test_url_snapshot.py`

- [ ] **Step 1: 写文件分类失败测试**

```python
from pathlib import Path
from xyb_core.ingest.classify import classify_path


def test_classify_known_extensions(tmp_path: Path) -> None:
    assert classify_path(tmp_path / "a.dcm") == "dicom"
    assert classify_path(tmp_path / "a.pdf") == "pdf"
    assert classify_path(tmp_path / "a.docx") == "docx"
    assert classify_path(tmp_path / "a.png") == "image"
    assert classify_path(tmp_path / "a.txt") == "text"
    assert classify_path(tmp_path / "a.url") == "url"
```

- [ ] **Step 2: 运行分类测试，确认失败**

Run: `cd core-py && pytest tests/test_classify.py -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError: cannot import name 'classify_path'`

- [ ] **Step 3: 实现分类器与配置默认值**

```python
# core-py/src/xyb_core/ingest/classify.py
from pathlib import Path

EXTENSION_MAP = {
    ".dcm": "dicom",
    ".dicom": "dicom",
    ".pdf": "pdf",
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".txt": "text",
    ".md": "text",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".gif": "image",
    ".url": "url",
}


def classify_path(path: Path) -> str:
    return EXTENSION_MAP.get(path.suffix.lower(), "unknown")
```

```python
# core-py/src/xyb_core/config.py
from dataclasses import dataclass, field

@dataclass
class PrivacyConfig:
    require_explicit_upload_consent: bool = True
    consent_record_file: str = "xyb-out/consent-log.json"

@dataclass
class ReportConfig:
    default_format: str = "md"
    auto_generate: bool = True
    output_dir: str = "xyb-out"
    notify_on_update: bool = True

@dataclass
class AppConfig:
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
```

- [ ] **Step 4: 重新运行分类测试**

Run: `cd core-py && pytest tests/test_classify.py -v`
Expected: PASS

- [ ] **Step 5: 写扫描 manifest 失败测试**

```python
from pathlib import Path
from xyb_core.ingest.scan import build_manifest


def test_build_manifest_collects_supported_files(tmp_path: Path) -> None:
    (tmp_path / 'ct1.png').write_bytes(b'img')
    (tmp_path / 'lab.pdf').write_bytes(b'%PDF-1.4')
    (tmp_path / 'link.url').write_text('https://example.com/a')
    manifest = build_manifest(tmp_path)
    assert [item['kind'] for item in manifest['items']] == ['image', 'pdf', 'url']
```

- [ ] **Step 6: 运行扫描测试，确认失败**

Run: `cd core-py && pytest tests/test_scan_manifest.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_manifest'`

- [ ] **Step 7: 实现扫描 manifest 与标准目录建议输出**

```python
# core-py/src/xyb_core/ingest/scan.py
from pathlib import Path
from xyb_core.ingest.classify import classify_path


def build_manifest(root: Path) -> dict:
    items = []
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        kind = classify_path(path)
        if kind == 'unknown':
            continue
        items.append({
            'path': str(path.relative_to(root)),
            'kind': kind,
            'stem': path.stem,
        })
    return {'root': str(root), 'items': items}
```

```md
<!-- core-py/src/xyb_core/templates/init_tree/README_如何整理.md -->
# xyb 推荐目录树

一级按病情类型，二级按时间归档。无法确认时间的文件先放入对应类型目录下的 `未分类时间/`。
```

- [ ] **Step 8: 写 URL 快照失败测试**

```python
from pathlib import Path
from xyb_core.ingest.url_snapshot import snapshot_url_text


def test_snapshot_url_text_writes_metadata(tmp_path: Path) -> None:
    out = snapshot_url_text(
        url='https://example.com/article',
        title='Example',
        body='正文内容',
        output_dir=tmp_path,
    )
    text = out.read_text(encoding='utf-8')
    assert 'source_url: "https://example.com/article"' in text
    assert '# Example' in text
    assert '正文内容' in text
```

- [ ] **Step 9: 实现 URL 快照写入器**

```python
# core-py/src/xyb_core/ingest/url_snapshot.py
from pathlib import Path
import re


def snapshot_url_text(url: str, title: str, body: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r'[^a-zA-Z0-9]+', '_', title).strip('_').lower() or 'snapshot'
    out = output_dir / f'{safe}.md'
    out.write_text(
        f'---\nsource_url: "{url}"\ntype: webpage\n---\n\n# {title}\n\n{body}\n',
        encoding='utf-8',
    )
    return out
```

- [ ] **Step 10: 运行 ingest 测试集**

Run: `cd core-py && pytest tests/test_classify.py tests/test_scan_manifest.py tests/test_url_snapshot.py -v`
Expected: PASS

- [ ] **Step 11: Commit**

```bash
git add core-py/src/xyb_core/config.py core-py/src/xyb_core/ingest core-py/tests
git commit -m "feat: add ingest manifest and url snapshot pipeline"
```

### Task 3: 建立胰腺癌病情要素 schema 与 LLM Provider 抽象

**Files:**
- Create: `core-py/src/xyb_core/extract/__init__.py`
- Create: `core-py/src/xyb_core/extract/models.py`
- Create: `core-py/src/xyb_core/extract/providers/__init__.py`
- Create: `core-py/src/xyb_core/extract/providers/base.py`
- Create: `core-py/src/xyb_core/extract/providers/openai_compatible.py`
- Create: `core-py/src/xyb_core/extract/pipeline.py`
- Create: `core-py/tests/test_extract_models.py`
- Create: `core-py/tests/test_extract_pipeline.py`

- [ ] **Step 1: 写 schema 失败测试**

```python
from xyb_core.extract.models import PatientProfile, BiomarkerPoint


def test_patient_profile_defaults() -> None:
    profile = PatientProfile()
    assert profile.cancer_type == 'pancreatic_cancer'
    assert profile.treatment_history == []
    assert profile.biomarker_points == []
    assert profile.psychology_scores == []
```

- [ ] **Step 2: 运行 schema 测试，确认失败**

Run: `cd core-py && pytest tests/test_extract_models.py -v`
Expected: FAIL with `ImportError: No module named xyb_core.extract`

- [ ] **Step 3: 写胰腺癌专用 schema**

```python
# core-py/src/xyb_core/extract/models.py
from dataclasses import dataclass, field

@dataclass
class BiomarkerPoint:
    marker: str
    value: float | str
    unit: str | None = None
    observed_at: str | None = None

@dataclass
class PatientProfile:
    cancer_type: str = 'pancreatic_cancer'
    basic_info: dict = field(default_factory=dict)
    diagnosis_info: dict = field(default_factory=dict)
    pathology: dict = field(default_factory=dict)
    genetics: list[dict] = field(default_factory=list)
    treatment_history: list[dict] = field(default_factory=list)
    biomarker_points: list[BiomarkerPoint] = field(default_factory=list)
    medication_risks: list[dict] = field(default_factory=list)
    complication_risks: list[dict] = field(default_factory=list)
    nutrition: dict = field(default_factory=dict)
    psychology_scores: list[dict] = field(default_factory=list)
```

- [ ] **Step 4: 重新运行 schema 测试**

Run: `cd core-py && pytest tests/test_extract_models.py -v`
Expected: PASS

- [ ] **Step 5: 写 Provider 抽象失败测试**

```python
from xyb_core.extract.pipeline import extract_document
from xyb_core.extract.providers.base import ExtractionProvider


class FakeProvider(ExtractionProvider):
    def extract_structured(self, *, text: str, kind: str, context: dict) -> dict:
        return {'diagnosis_info': {'stage': 'IV'}, 'treatment_history': []}


def test_extract_document_uses_provider() -> None:
    result = extract_document(
        kind='pdf',
        text='胰腺癌 IV 期',
        provider=FakeProvider(),
        context={'path': 'lab.pdf'},
    )
    assert result['diagnosis_info']['stage'] == 'IV'
```

- [ ] **Step 6: 运行管线测试，确认失败**

Run: `cd core-py && pytest tests/test_extract_pipeline.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 7: 实现 Provider 基类与抽取总管线**

```python
# core-py/src/xyb_core/extract/providers/base.py
from abc import ABC, abstractmethod

class ExtractionProvider(ABC):
    @abstractmethod
    def extract_structured(self, *, text: str, kind: str, context: dict) -> dict:
        raise NotImplementedError
```

```python
# core-py/src/xyb_core/extract/pipeline.py
from xyb_core.extract.models import PatientProfile
from xyb_core.extract.providers.base import ExtractionProvider


def extract_document(*, kind: str, text: str, provider: ExtractionProvider, context: dict) -> dict:
    profile = PatientProfile()
    data = provider.extract_structured(text=text, kind=kind, context=context)
    merged = profile.__dict__ | data
    return merged
```

```python
# core-py/src/xyb_core/extract/providers/openai_compatible.py
from xyb_core.extract.providers.base import ExtractionProvider

class OpenAICompatibleProvider(ExtractionProvider):
    def __init__(self, model: str, base_url: str, api_key: str) -> None:
        self.model = model
        self.base_url = base_url
        self.api_key = api_key

    def extract_structured(self, *, text: str, kind: str, context: dict) -> dict:
        raise NotImplementedError('provider network call implemented in later task')
```

- [ ] **Step 8: 重新运行抽取测试**

Run: `cd core-py && pytest tests/test_extract_models.py tests/test_extract_pipeline.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add core-py/src/xyb_core/extract core-py/tests/test_extract_models.py core-py/tests/test_extract_pipeline.py
git commit -m "feat: add pancreatic cancer schema and provider abstraction"
```

### Task 4: 构建时间线 + 病情关系图谱与查询载荷

**Files:**
- Create: `core-py/src/xyb_core/graph/__init__.py`
- Create: `core-py/src/xyb_core/graph/build.py`
- Create: `core-py/src/xyb_core/mcp_payload.py`
- Create: `core-py/src/xyb_core/output.py`
- Create: `core-py/tests/test_graph_build.py`
- Create: `core-py/tests/test_mcp_payload.py`

- [ ] **Step 1: 写图谱构建失败测试**

```python
from xyb_core.graph.build import build_patient_graph


def test_build_patient_graph_adds_timeline_and_biomarker_nodes() -> None:
    profile = {
        'basic_info': {'name': '张三'},
        'diagnosis_info': {'stage': 'IV', 'confirmed_at': '2025-01-01'},
        'biomarker_points': [{'marker': 'CA19-9', 'value': 120, 'observed_at': '2025-01-02'}],
    }
    graph = build_patient_graph(profile)
    assert graph.has_node('patient:张三')
    assert graph.has_node('timeline:2025-01-01')
    assert graph.has_node('marker:CA19-9:2025-01-02')
```

- [ ] **Step 2: 运行图谱测试，确认失败**

Run: `cd core-py && pytest tests/test_graph_build.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: 实现图谱构建器**

```python
# core-py/src/xyb_core/graph/build.py
import networkx as nx


def build_patient_graph(profile: dict) -> nx.DiGraph:
    graph = nx.DiGraph()
    name = profile.get('basic_info', {}).get('name', 'unknown')
    patient_id = f'patient:{name}'
    graph.add_node(patient_id, type='Patient', label=name)
    confirmed_at = profile.get('diagnosis_info', {}).get('confirmed_at')
    if confirmed_at:
        timeline_id = f'timeline:{confirmed_at}'
        graph.add_node(timeline_id, type='TimelineEvent', label=confirmed_at)
        graph.add_edge(patient_id, timeline_id, relation='has_event')
    for point in profile.get('biomarker_points', []):
        marker_id = f"marker:{point['marker']}:{point.get('observed_at', 'unknown')}"
        graph.add_node(marker_id, type='Biomarker', label=point['marker'], value=point['value'])
        graph.add_edge(patient_id, marker_id, relation='measured')
    return graph
```

- [ ] **Step 4: 重新运行图谱测试**

Run: `cd core-py && pytest tests/test_graph_build.py -v`
Expected: PASS

- [ ] **Step 5: 写 MCP 载荷失败测试**

```python
from xyb_core.mcp_payload import build_treatment_summary


def test_build_treatment_summary_lists_history() -> None:
    summary = build_treatment_summary({
        'treatment_history': [
            {'date': '2025-01-01', 'type': 'chemotherapy', 'regimen': 'FOLFIRINOX'}
        ]
    })
    assert 'FOLFIRINOX' in summary
    assert '2025-01-01' in summary
```

- [ ] **Step 6: 实现 MCP 载荷辅助函数与输出写盘**

```python
# core-py/src/xyb_core/mcp_payload.py
import json
from pathlib import Path
from networkx.readwrite import json_graph


def build_treatment_summary(profile: dict) -> str:
    lines = []
    for item in profile.get('treatment_history', []):
        lines.append(f"{item.get('date', 'unknown')} {item.get('type', '')} {item.get('regimen', '')}".strip())
    return '\n'.join(lines)


def write_graph_json(graph, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / 'graph.json'
    target.write_text(json.dumps(json_graph.node_link_data(graph), ensure_ascii=False, indent=2), encoding='utf-8')
    return target
```

- [ ] **Step 7: 运行图谱 + MCP 测试**

Run: `cd core-py && pytest tests/test_graph_build.py tests/test_mcp_payload.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add core-py/src/xyb_core/graph core-py/src/xyb_core/mcp_payload.py core-py/src/xyb_core/output.py core-py/tests
git commit -m "feat: add timeline graph builder and mcp payload helpers"
```

### Task 5: 报告渲染、watch 策略、增量 backfill 和通知

**Files:**
- Create: `core-py/src/xyb_core/report/__init__.py`
- Create: `core-py/src/xyb_core/report/render.py`
- Create: `core-py/src/xyb_core/report/templates/report.md.j2`
- Create: `core-py/src/xyb_core/report/templates/report.html.j2`
- Create: `core-py/src/xyb_core/watch.py`
- Create: `core-py/src/xyb_core/update.py`
- Create: `core-py/src/xyb_core/semantic/merge.py`
- Create: `core-py/tests/test_report_render.py`
- Create: `core-py/tests/test_watch.py`
- Create: `core-py/tests/test_semantic_backfill.py`

- [ ] **Step 1: 写 Markdown 报告失败测试**

```python
from pathlib import Path
from xyb_core.report.render import render_report


def test_render_report_writes_markdown(tmp_path: Path) -> None:
    profile = {
        'basic_info': {'name': '张三'},
        'diagnosis_info': {'stage': 'IV'},
        'treatment_history': [],
        'nutrition': {},
        'psychology_scores': [],
    }
    target = render_report(profile=profile, format='md', output_dir=tmp_path)
    text = target.read_text(encoding='utf-8')
    assert '# 病情概览 - 张三' in text
    assert '## 确诊信息' in text
```

- [ ] **Step 2: 运行报告测试，确认失败**

Run: `cd core-py && pytest tests/test_report_render.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: 实现报告渲染器**

```python
# core-py/src/xyb_core/report/render.py
from pathlib import Path


def render_report(*, profile: dict, format: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    if format == 'md':
        target = output_dir / 'report.md'
        target.write_text(
            f"# 病情概览 - {profile.get('basic_info', {}).get('name', '未命名')}\n\n## 确诊信息\n\n{profile.get('diagnosis_info', {})}\n",
            encoding='utf-8',
        )
        return target
    if format == 'html':
        target = output_dir / 'report.html'
        target.write_text('<html><body><h1>病情概览</h1></body></html>', encoding='utf-8')
        return target
    target = output_dir / 'report.pdf'
    target.write_bytes(b'%PDF-1.4\n%xyb\n')
    return target
```

- [ ] **Step 4: 重新运行报告测试**

Run: `cd core-py && pytest tests/test_report_render.py -v`
Expected: PASS

- [ ] **Step 5: 写 macOS watch 策略失败测试**

```python
from xyb_core.watch import _observer_mode, choose_observer_kind


def test_observer_mode_defaults_to_auto(monkeypatch) -> None:
    monkeypatch.delenv('XYB_WATCH_OBSERVER', raising=False)
    assert _observer_mode() == 'auto'


def test_choose_observer_kind_uses_polling_on_darwin(monkeypatch) -> None:
    monkeypatch.delenv('XYB_WATCH_OBSERVER', raising=False)
    monkeypatch.setattr('xyb_core.watch.platform.system', lambda: 'Darwin')
    assert choose_observer_kind() == 'polling'
```

- [ ] **Step 6: 实现 watcher 选择逻辑与通知文案**

```python
# core-py/src/xyb_core/watch.py
from __future__ import annotations
import os
import platform
from pathlib import Path


VALID_MODES = {'auto', 'native', 'polling'}


def _observer_mode() -> str:
    mode = os.environ.get('XYB_WATCH_OBSERVER', 'auto').strip().lower()
    return mode if mode in VALID_MODES else 'auto'


def choose_observer_kind() -> str:
    mode = _observer_mode()
    if mode == 'polling':
        return 'polling'
    if mode == 'native':
        return 'native'
    return 'polling' if platform.system() == 'Darwin' else 'native'


def build_update_message(output_path: Path) -> str:
    return f'[xyb] 病情报告已更新 → {output_path}'
```

- [ ] **Step 7: 写 semantic backfill merge 失败测试**

```python
from xyb_core.semantic.merge import merge_semantic_chunks


def test_merge_semantic_chunks_replaces_by_source_file() -> None:
    existing = {
        'nodes': [{'id': 'old-a', 'source_file': 'a.pdf'}],
        'edges': [],
        'hyperedges': [],
        'input_tokens': 1,
        'output_tokens': 1,
    }
    incoming = [{
        'nodes': [{'id': 'new-a', 'source_file': 'a.pdf'}],
        'edges': [],
        'hyperedges': [],
    }]
    merged, audit = merge_semantic_chunks(existing=existing, incoming=incoming, detected_files=['a.pdf', 'b.png'])
    assert [node['id'] for node in merged['nodes']] == ['new-a']
    assert audit['replaced_files'] == ['a.pdf']
    assert audit['unresolved_files'] == ['b.png']
```

- [ ] **Step 8: 实现 strict schema merge helper 与 audit 汇总**

```python
# core-py/src/xyb_core/semantic/merge.py
from __future__ import annotations


def merge_semantic_chunks(*, existing: dict, incoming: list[dict], detected_files: list[str]) -> tuple[dict, dict]:
    replace_files = {
        node['source_file']
        for chunk in incoming
        for node in chunk.get('nodes', [])
        if isinstance(node.get('source_file'), str)
    }
    kept_nodes = [node for node in existing.get('nodes', []) if node.get('source_file') not in replace_files]
    new_nodes = [node for chunk in incoming for node in chunk.get('nodes', [])]
    merged = {
        'nodes': kept_nodes + new_nodes,
        'edges': [edge for edge in existing.get('edges', []) if edge.get('source_file') not in replace_files],
        'hyperedges': existing.get('hyperedges', []),
        'input_tokens': existing.get('input_tokens', 0),
        'output_tokens': existing.get('output_tokens', 0),
    }
    unresolved = sorted(set(detected_files) - replace_files)
    audit = {
        'replaced_files': sorted(replace_files),
        'unresolved_files': unresolved,
    }
    return merged, audit
```

- [ ] **Step 9: 在 `update.py` 串起 plan/extract/merge/audit 四阶段并跑测试**

```python
# core-py/src/xyb_core/update.py
from xyb_core.semantic.merge import merge_semantic_chunks


def run_semantic_backfill(*, detected_files: list[str], existing_semantic: dict, chunk_results: list[dict]) -> dict:
    merged, audit = merge_semantic_chunks(
        existing=existing_semantic,
        incoming=chunk_results,
        detected_files=detected_files,
    )
    return {'semantic': merged, 'audit': audit}
```

Run: `cd core-py && pytest tests/test_report_render.py tests/test_watch.py tests/test_semantic_backfill.py -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add core-py/src/xyb_core/report core-py/src/xyb_core/watch.py core-py/src/xyb_core/update.py core-py/src/xyb_core/semantic core-py/tests
git commit -m "feat: add watch strategy and semantic backfill merge flow"
```

### Task 6: Node MCP Server、Python Bridge 与默认 `xyb` 命令

**Files:**
- Create: `mcp-ts/src/pythonBridge.ts`
- Create: `mcp-ts/src/server.ts`
- Create: `mcp-ts/src/tools/queryTimeline.ts`
- Create: `mcp-ts/src/tools/getTreatmentSummary.ts`
- Modify: `mcp-ts/src/cli.ts`
- Create: `mcp-ts/tests/pythonBridge.test.ts`
- Create: `mcp-ts/tests/server.test.ts`

- [ ] **Step 1: 写 Python bridge 失败测试**

```ts
import { describe, expect, it } from 'vitest'
import { buildPythonArgs } from '../src/pythonBridge'

describe('python bridge', () => {
  it('builds xyb-py command for scan', () => {
    expect(buildPythonArgs('scan', ['records'])).toEqual(['scan', 'records'])
  })
})
```

- [ ] **Step 2: 运行 bridge 测试，确认失败**

Run: `npm --prefix mcp-ts test -- pythonBridge`
Expected: FAIL with `Cannot find module '../src/pythonBridge'`

- [ ] **Step 3: 实现 Python bridge 与 CLI 转发**

```ts
// mcp-ts/src/pythonBridge.ts
export function buildPythonArgs(command: string, argv: string[]): string[] {
  return [command, ...argv]
}
```

```ts
// mcp-ts/src/cli.ts
import { spawnSync } from 'node:child_process'
import { Command } from 'commander'
import { buildPythonArgs } from './pythonBridge'

export function buildCommand(): Command {
  const program = new Command().name('xyb')
  for (const name of ['scan', 'update', 'report', 'init']) {
    program.command(`${name} [arg]`).action((arg) => {
      spawnSync('xyb-py', buildPythonArgs(name, arg ? [arg] : []), { stdio: 'inherit' })
    })
  }
  program.command('serve').action(() => {
    spawnSync('node', ['dist/server.js'], { stdio: 'inherit' })
  })
  return program
}
```

- [ ] **Step 4: 重新运行 bridge 测试**

Run: `npm --prefix mcp-ts test -- pythonBridge`
Expected: PASS

- [ ] **Step 5: 写 MCP server 失败测试**

```ts
import { describe, expect, it } from 'vitest'
import { listToolNames } from '../src/server'

describe('mcp server', () => {
  it('registers xyb tools', () => {
    expect(listToolNames()).toEqual([
      'query_timeline',
      'get_gene_info',
      'get_biomarker_trend',
      'get_treatment_summary',
      'generate_report'
    ])
  })
})
```

- [ ] **Step 6: 实现 MCP tools 注册**

```ts
// mcp-ts/src/server.ts
export function listToolNames(): string[] {
  return [
    'query_timeline',
    'get_gene_info',
    'get_biomarker_trend',
    'get_treatment_summary',
    'generate_report'
  ]
}
```

- [ ] **Step 7: 运行 Node 全量测试**

Run: `npm --prefix mcp-ts test`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add mcp-ts/src mcp-ts/tests
git commit -m "feat: add node cli bridge and mcp server skeleton"
```

### Task 7: Skill 模板、安装脚本与端到端烟雾测试

**Files:**
- Create: `mcp-ts/skills/skill.md`
- Create: `mcp-ts/skills/skill-codex.md`
- Create: `mcp-ts/skills/skill-opencode.md`
- Create: `mcp-ts/skills/skill-claw.md`
- Create: `mcp-ts/src/install.ts`
- Create: `core-py/tests/test_end_to_end_smoke.py`
- Modify: `README.md`

- [ ] **Step 1: 写 end-to-end 失败测试**

```python
from pathlib import Path
from xyb_core.ingest.scan import build_manifest
from xyb_core.graph.build import build_patient_graph
from xyb_core.report.render import render_report


def test_end_to_end_smoke(tmp_path: Path) -> None:
    (tmp_path / 'report.txt').write_text('胰腺癌 IV 期 CA19-9 120')
    manifest = build_manifest(tmp_path)
    graph = build_patient_graph({
        'basic_info': {'name': '测试患者'},
        'diagnosis_info': {'confirmed_at': '2025-01-01'},
        'biomarker_points': [{'marker': 'CA19-9', 'value': 120, 'observed_at': '2025-01-02'}],
    })
    report = render_report(profile={'basic_info': {'name': '测试患者'}, 'diagnosis_info': {}}, format='md', output_dir=tmp_path / 'xyb-out')
    assert manifest['items'][0]['kind'] == 'text'
    assert graph.number_of_nodes() >= 2
    assert report.exists()
```

- [ ] **Step 2: 运行端到端测试，确认失败**

Run: `cd core-py && pytest tests/test_end_to_end_smoke.py -v`
Expected: FAIL because earlier pieces are not wired into package exports yet

- [ ] **Step 3: 写 Skill 模板与安装说明**

```md
<!-- mcp-ts/skills/skill-codex.md -->
# xyb

当用户要求整理肿瘤患者病情目录、查询病情时间线、读取标志物趋势、生成病情摘要时，先调用 xyb MCP tools，而不是直接遍历原始文件。

优先工具：
- `query_timeline`
- `get_gene_info`
- `get_biomarker_trend`
- `get_treatment_summary`
- `generate_report`
```

```ts
// mcp-ts/src/install.ts
export function buildCodexInstallSnippet(command = 'xyb-mcp'): string {
  return JSON.stringify({
    mcpServers: {
      xyb: {
        type: 'stdio',
        command,
        args: []
      }
    }
  }, null, 2)
}
```

- [ ] **Step 4: 补 README 快速开始与安装说明**

```md
## Quick Start

```bash
uv sync --project core-py
npm --prefix mcp-ts install
npm --prefix mcp-ts run build
uv run --project core-py xyb-py init ./my_records
uv run --project core-py xyb-py scan ./my_records
uv run --project core-py xyb-py report
npm --prefix mcp-ts run serve
```
```

- [ ] **Step 5: 运行 Python + Node 全量测试**

Run: `cd core-py && pytest tests -v && cd ../mcp-ts && npm test`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add README.md mcp-ts/skills mcp-ts/src/install.ts core-py/tests/test_end_to_end_smoke.py
git commit -m "feat: add skills and end-to-end smoke coverage"
```

## Self-review

- Spec coverage: 覆盖了目录标准化、文档识别、URL 快照、胰腺癌 schema、图谱、报告、动态更新、MCP、Skill、默认 `xyb` 命令。
- Placeholder scan: 未保留 TBD/TODO；每个任务均给出文件路径、测试命令和最小代码片段。
- Type consistency: Python 包统一为 `xyb_core`，Node 包统一为 `@pancrepal/xyb`，CLI 固定为 `xyb` / `xyb-py`。
