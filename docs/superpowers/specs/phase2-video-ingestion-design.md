# xyb 二期设计：短视频摄取能力（中国平台优先）

日期：2026-04-17  
状态：二期预研（不纳入本期开发）

## 1. 目标

在不影响当前稳定主线（文字资料图谱）的前提下，补齐短视频资料摄取能力。

优先顺序：
1. 本地已下载视频/字幕导入
2. 显式转写链路
3. 平台 URL 适配器接口
4. URL 直连下载（后置）

## 2. 本期边界（冻结）

- 本期不实现 `xyb add` 的在线视频下载链路。
- 不承诺 YouTube / 抖音 / B站 / 视频号 URL 直连可用。
- 主线继续以 CT 报告、病理、检验等文字资料为主。

## 3. 二期能力分层

### P2.1（低风险）
- `xyb media import <file_or_dir>`：导入本地视频/音频/字幕
- `xyb media transcribe <file>`：显式转写

### P2.2（中风险）
- 平台适配器接口：
  - `bilibili`
  - `douyin`
  - `wechat_channels`
- 输出统一到标准媒体产物目录

### P2.3（高风险）
- URL 直连下载与自动转写一体化
- 单独做反爬/鉴权/稳定性风险评审

## 4. 产物协议（建议）

```text
graphify-out/media/<id>/
├── meta.json
├── transcript.md
├── segments.json
└── audio.wav           # 可选
```

## 5. 架构建议

- `xyb/ingest/video_adapters/base.py`
- `xyb/ingest/video_adapters/bilibili.py`
- `xyb/ingest/video_adapters/douyin.py`
- `xyb/ingest/video_adapters/wechat_channels.py`
- `xyb/transcribe.py`
- `xyb/ingest/video_pipeline.py`

## 6. 验收建议

二期最小验收：
- 本地视频导入 + 转写稳定可用
- `transcript.md` 能进入现有 `extract -> graph-report` 主链
- 对平台 URL 输入，至少能给出明确 capability 提示与失败原因

