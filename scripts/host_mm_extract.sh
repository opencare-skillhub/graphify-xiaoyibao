#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: host_mm_extract.sh <image_path>" >&2
  exit 2
fi

IMG_PATH="$1"
if [[ ! -f "$IMG_PATH" ]]; then
  echo "image not found: $IMG_PATH" >&2
  exit 2
fi

TMP_OUT="$(mktemp -t xyb_host_mm_XXXX.txt)"
trap 'rm -f "$TMP_OUT"' EXIT

PROMPT=$'请读取这张医疗图片，尽量完整提取可见文本并保持原有顺序。\n如果是检验单/肿瘤标志物，请区分项目名、结果值、参考值。\n如果是CT/放射学报告，请保留检查所见与诊断结论。\n只输出纯文本，不要解释。'

codex exec \
  --skip-git-repo-check \
  --ephemeral \
  --sandbox workspace-write \
  -i "$IMG_PATH" \
  -o "$TMP_OUT" \
  "$PROMPT" >/dev/null

cat "$TMP_OUT"
