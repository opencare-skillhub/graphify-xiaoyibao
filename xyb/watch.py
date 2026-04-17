from __future__ import annotations

import json
import os
import platform
import time
from pathlib import Path

from xyb.detect import CODE_EXTENSIONS, DOC_EXTENSIONS, PAPER_EXTENSIONS, IMAGE_EXTENSIONS

_WATCHED_EXTENSIONS = CODE_EXTENSIONS | DOC_EXTENSIONS | PAPER_EXTENSIONS | IMAGE_EXTENSIONS
_CODE_EXTENSIONS = CODE_EXTENSIONS


def _observer_mode() -> str:
    mode = os.environ.get("XYB_WATCH_OBSERVER", "auto").strip().lower()
    if mode not in {"auto", "native", "polling"}:
        mode = "auto"
    return mode


def _observer_class():
    try:
        from watchdog.observers import Observer
        from watchdog.observers.polling import PollingObserver
    except ImportError as e:
        raise ImportError("watchdog not installed. Run: pip install watchdog") from e

    mode = _observer_mode()
    if mode == "polling":
        return PollingObserver, "polling"
    if mode == "native":
        return Observer, "native"
    if platform.system() == "Darwin":
        return PollingObserver, "polling"
    return Observer, "native"


def _rebuild_code(watch_path: Path, *, follow_symlinks: bool = False) -> bool:
    try:
        from xyb.extract import extract
        from xyb.detect import detect
        from xyb.build import build_from_json
        from xyb.cluster import cluster, score_all
        from xyb.analyze import god_nodes, surprising_connections, suggest_questions
        from xyb.report import generate
        from xyb.export import to_json

        detected = detect(watch_path, follow_symlinks=follow_symlinks)
        code_files = [Path(f) for f in detected['files']['code']]
        if not code_files:
            print("[xyb watch] No code files found - nothing to rebuild.")
            return False

        result = extract(code_files)
        out = watch_path / "graphify-out"
        existing_graph = out / "graph.json"
        if existing_graph.exists():
            try:
                existing = json.loads(existing_graph.read_text(encoding="utf-8"))
                code_ids = {n["id"] for n in existing.get("nodes", []) if n.get("file_type") == "code"}
                sem_nodes = [n for n in existing.get("nodes", []) if n.get("file_type") != "code"]
                sem_edges = [
                    e for e in existing.get("links", existing.get("edges", []))
                    if e.get("confidence") in ("INFERRED", "AMBIGUOUS")
                    or (e.get("source") not in code_ids and e.get("target") not in code_ids)
                ]
                result = {
                    "nodes": result["nodes"] + sem_nodes,
                    "edges": result["edges"] + sem_edges,
                    "hyperedges": existing.get("hyperedges", []),
                    "input_tokens": 0,
                    "output_tokens": 0,
                }
            except Exception:
                pass

        detection = {
            "files": {"code": [str(f) for f in code_files], "document": [], "paper": [], "image": []},
            "total_files": len(code_files),
            "total_words": detected.get("total_words", 0),
        }

        G = build_from_json(result)
        communities = cluster(G)
        cohesion = score_all(G, communities)
        gods = god_nodes(G)
        surprises = surprising_connections(G, communities)
        labels = {cid: "Community " + str(cid) for cid in communities}
        questions = suggest_questions(G, communities, labels)

        out.mkdir(exist_ok=True)
        report = generate(G, communities, cohesion, labels, gods, surprises, detection, {"input": 0, "output": 0}, str(watch_path), suggested_questions=questions)
        (out / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
        to_json(G, communities, str(out / "graph.json"))
        flag = out / "needs_update"
        if flag.exists():
            flag.unlink()
        print(f"[xyb watch] Rebuilt: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(communities)} communities")
        print(f"[xyb watch] graph.json and GRAPH_REPORT.md updated in {out}")
        return True
    except Exception as exc:
        print(f"[xyb watch] Rebuild failed: {exc}")
        return False


def _notify_only(watch_path: Path) -> None:
    flag = watch_path / "graphify-out" / "needs_update"
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text("1", encoding="utf-8")
    print(f"\n[xyb watch] New or changed files detected in {watch_path}")
    print("[xyb watch] Non-code files changed - semantic re-extraction requires LLM.")
    print("[xyb watch] Run `/xyb update` to update the graph.")
    print(f"[xyb watch] Flag written to {flag}")


def _has_non_code(changed_paths: list[Path]) -> bool:
    return any(p.suffix.lower() not in _CODE_EXTENSIONS for p in changed_paths)


def watch(watch_path: Path, debounce: float = 3.0) -> None:
    try:
        from watchdog.events import FileSystemEventHandler
    except ImportError as e:
        raise ImportError("watchdog not installed. Run: pip install watchdog") from e

    last_trigger: float = 0.0
    pending: bool = False
    changed: set[Path] = set()

    class Handler(FileSystemEventHandler):
        def on_any_event(self, event):
            nonlocal last_trigger, pending
            if event.is_directory:
                return
            path = Path(event.src_path)
            if path.suffix.lower() not in _WATCHED_EXTENSIONS:
                return
            if any(part.startswith(".") for part in path.parts):
                return
            if "graphify-out" in path.parts:
                return
            last_trigger = time.monotonic()
            pending = True
            changed.add(path)

    handler = Handler()
    ObserverClass, observer_kind = _observer_class()
    observer = ObserverClass()
    observer.schedule(handler, str(watch_path), recursive=True)
    observer.start()

    print(f"[xyb watch] Watching {watch_path.resolve()} - press Ctrl+C to stop")
    print(f"[xyb watch] Observer: {observer_kind}")
    print(f"[xyb watch] Code changes rebuild graph automatically. Doc/image changes require /xyb update.")
    print(f"[xyb watch] Debounce: {debounce}s")

    try:
        while True:
            time.sleep(0.5)
            if pending and (time.monotonic() - last_trigger) >= debounce:
                pending = False
                batch = list(changed)
                changed.clear()
                print(f"\n[xyb watch] {len(batch)} file(s) changed")
                if _has_non_code(batch):
                    _notify_only(watch_path)
                else:
                    _rebuild_code(watch_path)
    except KeyboardInterrupt:
        print("\n[xyb watch] Stopped.")
    finally:
        observer.stop()
        observer.join()
