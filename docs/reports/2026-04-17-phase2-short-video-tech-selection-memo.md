# 二期短视频摄取技术选型备忘录（xyb）

日期：2026-04-17  
范围：`xyb` 二期短视频摄取能力（抖音 / B站 / 微信视频号优先）

---

## 1. 背景

当前 `xyb` 主线已经稳定在“本地资料 → 抽取 → 图谱 → 报告”。
短视频链路尚未纳入本期交付，需在二期明确技术路线，避免影响现有稳定闭环。

---

## 2. 公开项目对比（GitHub）

> 数据基于 2026-04-17 检索结果，关注 stars、技术栈、实现形态。

| 项目 | Stars | 技术栈 | 形态 | 典型能力 |
|---|---:|---|---|---|
| yt-dlp/yt-dlp | 157,281 | Python | CLI | 通用多站点下载框架 |
| ytdl-org/youtube-dl | 140,083 | Python | CLI | 老牌通用下载器 |
| soimort/you-get | 56,827 | Python | CLI | 通用抓取下载 |
| iawia002/lux | 31,232 | Go | CLI | 高性能通用下载 |
| putyy/res-downloader | 16,626 | Go + Wails | 桌面 | 代理抓包 + 多平台资源下载 |
| JoeanAmier/TikTokDownloader | 14,052 | Python(HTTPX) | CLI/WebAPI/Docker | 抖音/TikTok 数据采集+下载 |
| nilaoda/BBDown | 13,712 | C#(.NET) | CLI | B站专用深度下载 |
| caorushizi/mediago | 8,935 | TypeScript | 桌面/Web | m3u8/HLS 嗅探下载 |
| will-17173/electron-weixin-channels-downloader | 62 | JavaScript | 桌面 | 视频号下载 |
| KingsleyYau/WeChatChannelsDownloader | 59 | C++ | 桌面 | 视频号下载 |

结论：
- 高星项目集中在 **通用下载器** 和 **抖音/B站方向**。
- 视频号专用生态较小，成熟度和稳定性相对弱。

---

## 3. 实现路线类型

### A. 通用 Extractor 路线
- 代表：yt-dlp / you-get / lux
- 优点：站点覆盖广、生态成熟
- 风险：集成后维护面大，平台策略变化会带来持续适配成本

### B. 平台专用 API/签名路线
- 代表：TikTokDownloader / BBDown
- 优点：平台深度能力强，质量与元信息更完整
- 风险：签名、Cookie、风控策略变化快，稳定性依赖持续维护

### C. 代理抓包/嗅探路线
- 代表：res-downloader / mediago
- 优点：启动快，对未知站点有较强泛化
- 风险：对客户端环境和网络条件依赖高，可重复性不如 API 路线

### D. 下载引擎组合
- 常见：ffmpeg / mp4box / aria2c
- 作用：分片下载、合流、容器封装、转码后处理

---

## 4. 对 xyb 的二期建议

### 4.1 总体策略
采用“**本地导入优先，平台直连后置**”策略：
1. 先把短视频资料纳入现有图谱主链（不依赖平台反爬）
2. 再逐步增加平台 URL 适配器
3. 最后评估是否开放直连下载

### 4.2 分期建议

#### P2.1（低风险，优先）
- 新增：`xyb media import <file_or_dir>`
- 新增：`xyb media transcribe <file>`
- 支持输入：`mp4/mov/mkv/mp3/wav/srt/vtt`
- 产物写入统一媒体目录

#### P2.2（中风险）
- 预留适配器接口：
  - `bilibili`
  - `douyin`
  - `wechat_channels`
- 先做 capability 检测和标准化元数据抽取

#### P2.3（高风险）
- URL 直连下载与自动转写一体化
- 独立风险评审（风控、鉴权、限流、可用性）

---

## 5. 统一产物协议建议

```text
graphify-out/media/<id>/
├── meta.json
├── transcript.md
├── segments.json
└── audio.wav            # 可选
```

接入点：
- `transcript.md` 进入现有 `extract -> build -> report` 主链
- `meta.json` 可做节点补充（平台、作者、发布时间、时长）

---

## 6. 与当前项目边界对齐

本备忘录与当前生效策略一致：
- 本期不交付在线视频平台下载链路
- 主线继续聚焦文字资料（CT报告、病理、检验）
- 短视频能力在二期按分层推进

---

## 7. 关键提示

1. 不建议把短视频平台下载当作本期阻塞项。  
2. 如果必须支持平台 URL，优先 B站/抖音，视频号单列为实验能力。  
3. 先打通“本地媒体导入 + 转写 + 图谱”即可覆盖大部分真实场景。  
4. 法律与平台条款需在二期上线前单独评审，避免把合规风险带入核心链路。

