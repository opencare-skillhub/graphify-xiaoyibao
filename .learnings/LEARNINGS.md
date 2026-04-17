## [LRN-20260416-001] correction

**Logged**: 2026-04-16T09:50:00+08:00
**Priority**: high
**Status**: pending
**Area**: planning

### Summary
当项目处于“设计更新后、进入任务分解与评估”的阶段时，不应把局部 npm 测试问题误判为整体开发前置阻塞。

### Details
用户明确说明：当前重点是开发任务分解、评估、再进入真实开发。Node/npm 的局部问题只有在它位于当前关键路径时才需要优先处理；若当前阶段主要推进 Python/core 与整体架构落地，应降级为非前置问题。

### Suggested Action
先做关键路径评估：按设计文档与实施计划划分阶段、识别 upstream 可复用模块、确定首批真实开发范围；将 npm 问题作为 side issue 记录，只有进入 Node/MCP 阶段再处理。

### Metadata
- Source: user_feedback
- Related Files: docs/superpowers/plans/2026-04-14-xiaoyibao-v1.md, .learnings/ERRORS.md
- Tags: planning, prioritization, correction

---
