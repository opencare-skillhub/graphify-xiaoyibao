#!/usr/bin/env bash
set -euo pipefail

GRAPH_PATH="${1:-./xiaoyibao-out/graph.json}"
OUT_DIR="${2:-./xiaoyibao-out}"
MARKERS="${3:-ca19_9,cea,afp,ca50,ca72_4,ca125}"

xyb markers-trend --graph "$GRAPH_PATH" --output-dir "$OUT_DIR" --markers "$MARKERS"

