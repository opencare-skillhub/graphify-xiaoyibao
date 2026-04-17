# Findings

- `~/Downloads/graphify` 当前有三个关键分支：`pr/macos-watch-polling`、`local/incremental-backfill-tooling`、`v4`。
- `v4` 当前指向 `7ab62fd`，描述中已包含 macOS watch 修复。
- 本次要把两类经验写回当前项目：
  1. macOS watch 在 FSEvents 不稳定时默认回退/优先使用 polling，并允许环境变量覆盖。
  2. 文档/图片/PDF 的标准化增量语义 backfill 流程，以及 chunk schema/source_file merge 规范。
- `~/Downloads/graphify-upstream` 在 fetch 后确认 `upstream/v4` 已到 `7ab62fd`；`~/Downloads/graphify` 的 `v4` 也已同步到同一提交。
- `pr/macos-watch-polling` 的关键经验是：Darwin 默认 polling + 环境变量覆盖 + watch tests 覆盖 observer mode。
- `aa9d6b5` 的关键经验是：doc/pdf/image 的 semantic backfill 需要 plan/extract/merge/audit 闭环，且主 JSON 保持 strict schema，`source_file` 单字符串，辅助信息进 audit sidecar。
- 已将上述经验回灌到 `docs/superpowers/specs/2026-04-14-xiaoyibao-v1-design.md` 与 `docs/superpowers/plans/2026-04-14-xiaoyibao-v1.md`。
