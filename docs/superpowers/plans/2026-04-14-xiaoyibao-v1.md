# xiaoyibao (xyb) V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在新目录中完成 `graphify` 主链向独立 `xyb` 项目的迁移，先跑通 `xyb` CLI 与主流程，再在此基础上实施病情资料专病增强。

**Architecture:** 以 `graphify` 项目形态为主进行迁移，保留 `docs/`，主 Python 包统一为 `xyb/`，CLI 统一为 `xyb`。第一阶段优先迁移并改名 `detect / extract / build / report / watch / serve` 等成熟主链；第二阶段再加入病情资料 detect、报告、watch、semantic backfill 等增强。

**Tech Stack:** Python 3.11+, pytest, NetworkX, Typer/argparse（按迁移结果定）, watchdog, pypdf, python-docx, openpyxl, Pillow, pydicom, 本地虚拟环境运行

---

## Target file structure

- `README.md` — 项目说明、安装、快速开始
- `pyproject.toml` — Python 包配置，暴露 `xyb` CLI
- `xyb/__init__.py` — 包入口
- `xyb/__main__.py` — `python -m xyb` 入口
- `xyb/cache.py` — 文件缓存与签名
- `xyb/detect.py` — 文件发现、分类、统计
- `xyb/ingest.py` — URL/网页抓取与快照
- `xyb/extract.py` — 抽取与 chunk 处理主链
- `xyb/build.py` — 图谱构建
- `xyb/cluster.py` — 聚类与社区分析
- `xyb/analyze.py` — 分析与问题建议
- `xyb/report.py` — 报告生成
- `xyb/export.py` — graph/json/html 输出
- `xyb/watch.py` — watch 监听与更新策略
- `xyb/serve.py` — 本地服务/MCP 兼容入口
- `xyb/security.py` — URL/文件抓取安全边界
- `xyb/transcribe.py` — 多媒体/转录辅助（如迁移需要）
- `xyb/wiki.py` — 兼容原始主链的 orchestrator，后续逐步专病化
- `xyb/semantic_backfill.py` — semantic backfill plan/extract/merge/audit 编排
- `tests/` — 与迁移模块对应的测试
- `docs/` — 设计文档、开发说明、增强记录

## Migration rules

1. 允许从 `graphify` 迁移结构和代码，但必须落在当前项目目录。
2. 迁移后主包名统一为 `xyb`，不得继续以 `graphify` 作为主包名。
3. 第一阶段优先保留已验证主链和输出协议，不急于重命名 `graphify-out/`。
4. 第二阶段的病情资料增强必须建立在“迁移版 xyb 可运行”的前提上。
5. 旧版 `core-py/`、`mcp-ts/` 不再作为主形态，若保留仅作归档，不作为实现目标。

---

### Task 1: 迁移 graphify 项目骨架到 xyb 项目形态

**Files:**
- Modify: `README.md`
- Create: `pyproject.toml`
- Create: `xyb/__init__.py`
- Create: `xyb/__main__.py`
- Create: `tests/test_cli_smoke.py`
- Delete or archive from active path: `core-py/`, `mcp-ts/`（若仍存在）

- [ ] **Step 1: 写 CLI 冒烟失败测试**

```python
from pathlib import Path
import subprocess
import sys


def test_python_module_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, '-m', 'xyb', '--help'],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert 'xyb' in result.stdout.lower()
```

- [ ] **Step 2: 运行测试，确认当前失败**

Run: `pytest tests/test_cli_smoke.py -v`
Expected: FAIL with `No module named xyb`

- [ ] **Step 3: 迁移基础包入口并建立最小 CLI**

```python
# xyb/__init__.py
__all__ = []
```

```python
# xyb/__main__.py
from __future__ import annotations
import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='xyb', description='xiaoyibao CLI')
    parser.add_argument('--version', action='store_true')
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.version:
        print('xyb 0.1.0')


if __name__ == '__main__':
    main()
```

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "xyb"
version = "0.1.0"
requires-python = ">=3.11"

[project.scripts]
xyb = "xyb.__main__:main"

[tool.setuptools]
package-dir = {"" = "."}

[tool.setuptools.packages.find]
include = ["xyb*"]
```

- [ ] **Step 4: 更新 README 为迁移型项目说明**

```md
# llm-wiki-xiaoyibao

独立 `xyb` 项目，采用 `graphify` 形态迁移开发。

- 主包：`xyb/`
- CLI：`xyb`
- 文档：`docs/`
```

- [ ] **Step 5: 重新运行 CLI 冒烟测试**

Run: `pytest tests/test_cli_smoke.py -v`
Expected: PASS

- [ ] **Step 6: 清理旧主形态目录**

Run: `test ! -d core-py && test ! -d mcp-ts`
Expected: PASS after archive/remove

- [ ] **Step 7: Commit**

```bash
git add README.md pyproject.toml xyb tests
git commit -m "chore: migrate project skeleton to xyb package layout"
```

### Task 2: 迁移 detect / cache 主链并改名为 xyb 模块

**Files:**
- Create: `xyb/cache.py`
- Create: `xyb/detect.py`
- Create: `tests/test_cache.py`
- Create: `tests/test_detect.py`
- Reference: `/Users/qinxiaoqiang/Downloads/graphify-upstream/graphify/cache.py`
- Reference: `/Users/qinxiaoqiang/Downloads/graphify-upstream/graphify/detect.py`

- [ ] **Step 1: 写 detect 分类失败测试**

```python
from pathlib import Path
from xyb.detect import classify_file


def test_classify_medical_files(tmp_path: Path) -> None:
    assert classify_file(tmp_path / 'a.pdf').value in {'paper', 'document'}
    assert classify_file(tmp_path / 'a.png').value == 'image'
    assert classify_file(tmp_path / 'a.docx').value == 'document'
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_detect.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: 从 graphify 迁移 cache / detect 并完成命名替换**

```python
# xyb/cache.py
# 从 graphify.cache 迁移核心实现，模块内 import 全部替换为 xyb.*
```

```python
# xyb/detect.py
# 从 graphify.detect 迁移核心实现，保留 detect/classify/count 逻辑
# 在此阶段只做必要命名替换与最小兼容修正
```

- [ ] **Step 4: 追加病情资料文件扩展名兼容测试**

```python
def test_detect_supports_medical_assets(tmp_path: Path) -> None:
    assert classify_file(tmp_path / 'scan.heic').value in {'image', 'document', 'image'}
    assert classify_file(tmp_path / 'study.dcm').value in {'document', 'image', 'paper'}
```

- [ ] **Step 5: 运行 cache/detect 测试**

Run: `pytest tests/test_cache.py tests/test_detect.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add xyb/cache.py xyb/detect.py tests/test_cache.py tests/test_detect.py
git commit -m "feat: migrate cache and detect modules into xyb"
```

### Task 3: 迁移 ingest / security 主链并保留 URL 快照能力

**Files:**
- Create: `xyb/security.py`
- Create: `xyb/ingest.py`
- Create: `tests/test_ingest.py`
- Reference: `/Users/qinxiaoqiang/Downloads/graphify-upstream/graphify/security.py`
- Reference: `/Users/qinxiaoqiang/Downloads/graphify-upstream/graphify/ingest.py`

- [ ] **Step 1: 写 URL snapshot 失败测试**

```python
from pathlib import Path
from xyb.ingest import _safe_filename


def test_safe_filename_from_url() -> None:
    name = _safe_filename('https://example.com/a/b', '.md')
    assert name.endswith('.md')
    assert 'example' in name
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_ingest.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: 迁移 security / ingest 并改名为 xyb**

```python
# xyb/security.py
# 从 graphify.security 迁移 validate_url / safe_fetch 等实现
```

```python
# xyb/ingest.py
# 从 graphify.ingest 迁移 URL 分类、网页抓取、markdown 快照逻辑
# import 改为 xyb.security
```

- [ ] **Step 4: 运行 ingest 测试**

Run: `pytest tests/test_ingest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add xyb/security.py xyb/ingest.py tests/test_ingest.py
git commit -m "feat: migrate ingest and security modules into xyb"
```

### Task 4: 迁移 build / cluster / analyze / export / report 主链

**Files:**
- Create: `xyb/build.py`
- Create: `xyb/cluster.py`
- Create: `xyb/analyze.py`
- Create: `xyb/export.py`
- Create: `xyb/report.py`
- Create: `tests/test_build.py`
- Create: `tests/test_report.py`
- Reference: `/Users/qinxiaoqiang/Downloads/graphify-upstream/graphify/build.py`
- Reference: `/Users/qinxiaoqiang/Downloads/graphify-upstream/graphify/cluster.py`
- Reference: `/Users/qinxiaoqiang/Downloads/graphify-upstream/graphify/analyze.py`
- Reference: `/Users/qinxiaoqiang/Downloads/graphify-upstream/graphify/export.py`
- Reference: `/Users/qinxiaoqiang/Downloads/graphify-upstream/graphify/report.py`

- [ ] **Step 1: 写图谱构建失败测试**

```python
from xyb.build import build_from_json


def test_build_from_minimal_json() -> None:
    graph = build_from_json({'nodes': [], 'edges': [], 'hyperedges': []})
    assert graph.number_of_nodes() == 0
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_build.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: 迁移 build/cluster/analyze/export/report 实现**

```python
# xyb/build.py
# 从 graphify.build 迁移，改写 import 为 xyb.*
```

```python
# xyb/report.py
# 从 graphify.report 迁移，保持 GRAPH_REPORT.md 生成能力
```

- [ ] **Step 4: 运行 build/report 测试**

Run: `pytest tests/test_build.py tests/test_report.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add xyb/build.py xyb/cluster.py xyb/analyze.py xyb/export.py xyb/report.py tests
git commit -m "feat: migrate graph build and report pipeline into xyb"
```

### Task 5: 迁移 extract / wiki orchestrator 主链，形成可运行闭环

**Files:**
- Create: `xyb/extract.py`
- Create: `xyb/wiki.py`
- Create: `tests/test_extract.py`
- Create: `tests/test_pipeline.py`
- Reference: `/Users/qinxiaoqiang/Downloads/graphify-upstream/graphify/extract.py`
- Reference: `/Users/qinxiaoqiang/Downloads/graphify-upstream/graphify/wiki.py`

- [ ] **Step 1: 写抽取主链失败测试**

```python
from xyb.extract import extract


def test_extract_returns_structured_payload_for_empty_files() -> None:
    result = extract([])
    assert set(result.keys()) >= {'nodes', 'edges', 'hyperedges'}
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_extract.py tests/test_pipeline.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: 迁移 extract/wiki 并修复 import 路径**

```python
# xyb/extract.py
# 从 graphify.extract 迁移 chunk/semantic 主链
```

```python
# xyb/wiki.py
# 从 graphify.wiki 迁移 scan->extract->build->report orchestrator
```

- [ ] **Step 4: 运行抽取主链测试**

Run: `pytest tests/test_extract.py tests/test_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add xyb/extract.py xyb/wiki.py tests/test_extract.py tests/test_pipeline.py
git commit -m "feat: migrate extract and pipeline orchestrator into xyb"
```

### Task 6: 迁移 watch / serve，并纳入 macOS polling 修正

**Files:**
- Create: `xyb/watch.py`
- Create: `xyb/serve.py`
- Create: `tests/test_watch.py`
- Create: `tests/test_serve.py`
- Reference: `/Users/qinxiaoqiang/Downloads/graphify/graphify/watch.py`
- Reference: `/Users/qinxiaoqiang/Downloads/graphify-upstream/graphify/serve.py`

- [ ] **Step 1: 写 watch observer 失败测试**

```python
from xyb.watch import _observer_mode


def test_observer_mode_defaults_to_auto(monkeypatch) -> None:
    monkeypatch.delenv('XYB_WATCH_OBSERVER', raising=False)
    assert _observer_mode() == 'auto'
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_watch.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: 从本地 graphify 分支迁移 watch 修正并改名**

```python
# xyb/watch.py
# 基于 ~/Downloads/graphify 的 macOS polling 修正版迁移
# 环境变量名改为 XYB_WATCH_OBSERVER
```

```python
# xyb/serve.py
# 从 graphify.serve 迁移本地服务入口
```

- [ ] **Step 4: 运行 watch/serve 测试**

Run: `pytest tests/test_watch.py tests/test_serve.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add xyb/watch.py xyb/serve.py tests/test_watch.py tests/test_serve.py
git commit -m "feat: migrate watch and serve with macOS polling defaults"
```

### Task 7: 迁移并固化 semantic backfill helper

**Files:**
- Create: `xyb/semantic_backfill.py`
- Create: `tests/test_semantic_backfill.py`
- Reference: `/Users/qinxiaoqiang/Downloads/graphify/docs/INCREMENTAL_SEMANTIC_BACKFILL.md`
- Reference: `/Users/qinxiaoqiang/Downloads/graphify/scripts/semantic_backfill_merge.py`

- [ ] **Step 1: 写 semantic backfill merge 失败测试**

```python
from xyb.semantic_backfill import merge_semantic_chunks


def test_merge_semantic_chunks_replaces_matching_source_file() -> None:
    merged, audit = merge_semantic_chunks(
        existing={'nodes': [{'id': 'old', 'source_file': 'a.pdf'}], 'edges': [], 'hyperedges': []},
        incoming=[{'nodes': [{'id': 'new', 'source_file': 'a.pdf'}], 'edges': [], 'hyperedges': []}],
        detected_files=['a.pdf', 'b.png'],
    )
    assert [n['id'] for n in merged['nodes']] == ['new']
    assert audit['replaced_files'] == ['a.pdf']
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_semantic_backfill.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: 迁移 helper 并抽成 xyb 模块**

```python
# xyb/semantic_backfill.py
# 基于 semantic_backfill_merge.py 抽取 plan/extract/merge/audit 核心逻辑
# import 改为 xyb.build / xyb.report / xyb.export / xyb.analyze / xyb.cluster
```

- [ ] **Step 4: 运行 semantic backfill 测试**

Run: `pytest tests/test_semantic_backfill.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add xyb/semantic_backfill.py tests/test_semantic_backfill.py
git commit -m "feat: add semantic backfill merge helper to xyb"
```

### Task 8: 跑通迁移版 xyb 的端到端主链

**Files:**
- Modify: `README.md`
- Create: `tests/test_end_to_end_smoke.py`

- [ ] **Step 1: 写端到端烟雾测试**

```python
from pathlib import Path

from xyb.detect import detect
from xyb.build import build_from_json


def test_end_to_end_smoke(tmp_path: Path) -> None:
    (tmp_path / 'note.md').write_text('# note\n\nhello', encoding='utf-8')
    detected = detect(tmp_path)
    assert detected['total_files'] >= 1
    graph = build_from_json({'nodes': [], 'edges': [], 'hyperedges': []})
    assert graph.number_of_nodes() == 0
```

- [ ] **Step 2: 运行迁移主链测试集**

Run: `pytest tests -v`
Expected: PASS

- [ ] **Step 3: 更新 README 的本地运行说明**

```md
## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
xyb --help
```
```

- [ ] **Step 4: Commit**

```bash
git add README.md tests/test_end_to_end_smoke.py
git commit -m "feat: validate migrated xyb baseline end to end"
```

### Task 9: 实施第一批病情资料增强

**Files:**
- Modify: `xyb/detect.py`
- Modify: `xyb/report.py`
- Modify: `xyb/watch.py`
- Modify: `xyb/semantic_backfill.py`
- Create: `docs/medical-enhancement-notes.md`
- Create: `tests/test_medical_detect.py`
- Create: `tests/test_medical_report.py`

- [ ] **Step 1: 写病情资料分类增强失败测试**

```python
from pathlib import Path
from xyb.detect import classify_file


def test_medical_detect_handles_dicom_and_heic(tmp_path: Path) -> None:
    assert classify_file(tmp_path / 'study.dcm') is not None
    assert classify_file(tmp_path / 'photo.HEIC') is not None
```

- [ ] **Step 2: 运行测试，确认失败或行为不符**

Run: `pytest tests/test_medical_detect.py -v`
Expected: FAIL or current behavior insufficient

- [ ] **Step 3: 调整 detect/report/watch/backfill 为病情资料场景**

```python
# xyb/detect.py
# 增加病情资料常见扩展名与目录启发式
```

```python
# xyb/report.py
# 增加病情摘要导向模板字段
```

```python
# xyb/watch.py
# 保留 macOS polling 默认策略，并强化 non-code 资料变更提示
```

```python
# xyb/semantic_backfill.py
# 针对 pdf/image/docx 的 source_file merge 与审计做固化
```

- [ ] **Step 4: 运行病情增强测试集**

Run: `pytest tests/test_medical_detect.py tests/test_medical_report.py tests/test_watch.py tests/test_semantic_backfill.py -v`
Expected: PASS

- [ ] **Step 5: 记录增强说明并提交**

```bash
git add xyb/detect.py xyb/report.py xyb/watch.py xyb/semantic_backfill.py docs/medical-enhancement-notes.md tests
git commit -m "feat: specialize xyb baseline for medical record workflows"
```

### Task 10（二期预研）: 短视频摄取能力设计与接口预留

**范围定位：**
- 本期不落地在线视频平台下载链路。
- 本任务只完成二期方案文档与接口边界定义，不引入高风险下载实现。

**Files:**
- Create: `docs/superpowers/specs/phase2-video-ingestion-design.md`
- Modify: `xyb/ingest.py`（仅补注释或 capability 提示，不改动现有稳定链路）

- [ ] **Step 1: 形成二期技术设计文档**
  - 本地导入优先：`xyb media import <file_or_dir>`
  - 显式转写：`xyb media transcribe <file>`
  - 平台适配器接口：`bilibili` / `douyin` / `wechat_channels`
  - URL 直连下载延后，单独风险评审

- [ ] **Step 2: 明确二期产物协议**
  - 建议目录：`graphify-out/media/<id>/`
  - 最小产物：`meta.json`、`transcript.md`、`segments.json`
  - 可选产物：`audio.wav`

- [ ] **Step 3: 记录本期边界**
  - `xyb add` 当前不承诺视频平台下载
  - 主线继续聚焦文字资料图谱（CT报告/病理/检验）

- [ ] **Step 4: Commit（二期设计）**

```bash
git add docs/superpowers/specs/phase2-video-ingestion-design.md docs/superpowers/plans/2026-04-14-xiaoyibao-v1.md
git commit -m "docs: define phase2 short-video ingestion design scope"
```

## Self-review

- Spec coverage: 已按新生效设计切换为“graphify 形态迁移 → xyb 改名 → 病情增强”的顺序。
- Placeholder scan: 每个任务都给出文件路径、验证命令和迁移来源，无 TBD/TODO 占位。
- Type consistency: 主包统一为 `xyb`，CLI 统一为 `xyb`，第一阶段不再使用 `core-py` / `mcp-ts` 作为主实现形态。
