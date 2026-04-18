---
name: xyb Tumor Markers Trend
description: This skill should be used when the user asks to "查看肿瘤标志物趋势", "生成 CA19-9/CEA/AFP 趋势图", "导出肿瘤标志物 CSV", "更新肿瘤标志物趋势报告", or wants stable recurring tumor marker trend outputs from xyb graph data.
version: 0.1.0
---

# xyb 肿瘤标志物趋势 Skill

## 目的
从 `xyb process` 产出的 `graph.json` 稳定生成肿瘤标志物趋势产物，默认覆盖：

- CA19-9
- CEA
- AFP
- CA50
- CA72-4
- CA125

输出固定为：

- `tumor_markers_trend.csv`
- `tumor_markers_trend.png`
- `tumor_markers_trend_summary.md`

## 使用条件
当用户提到“趋势图/趋势表/标志物变化”并且项目已经有 `graph.json` 时触发。

## 标准流程
1. 在目标项目目录执行 `xyb process . --output-dir ./xiaoyibao-out`（如需先更新图谱）。
2. 执行 `xyb markers-trend --graph ./xiaoyibao-out/graph.json --output-dir ./xiaoyibao-out`。
3. 返回关键结果：日期点、首末值、总体变化方向，并告知三个输出文件路径。

## 命令
```bash
xyb markers-trend --graph ./xiaoyibao-out/graph.json --output-dir ./xiaoyibao-out
```

只看部分指标时可加：
```bash
xyb markers-trend --markers ca19_9,cea,afp --graph ./xiaoyibao-out/graph.json --output-dir ./xiaoyibao-out
```

