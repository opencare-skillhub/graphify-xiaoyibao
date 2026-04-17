## [ERR-20260416-001] npm_test_strip_types

**Logged**: 2026-04-16T09:45:00+08:00
**Priority**: medium
**Status**: pending
**Area**: tests

### Summary
`npm --prefix mcp-ts test` 在 Node strip-types 模式下失败，原因是 `src/cli.ts` 使用了 parameter property 语法。

### Error
```
SyntaxError [ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX]: TypeScript parameter property is not supported in strip-only mode
```

### Context
- Command: `npm --prefix mcp-ts test`
- Environment: Node.js v22.19.0
- Related file: `mcp-ts/src/cli.ts`

### Suggested Fix
将 parameter property 改为兼容 strip-types 的普通字段赋值写法，避免依赖完整 TS 转译。

### Metadata
- Reproducible: yes
- Related Files: mcp-ts/src/cli.ts

---
## [ERR-20260416-002] pytest_import_path_for_root_package

**Logged**: 2026-04-16T10:06:00+08:00
**Priority**: low
**Status**: pending
**Area**: tests

### Summary
根目录下的 `xyb/` 包可被 `python -m xyb` 运行，但 pytest 收集测试时未能导入，需要显式补 root path。

### Error
```
ModuleNotFoundError: No module named 'xyb'
```

### Context
- Command: `pytest tests/test_cache.py tests/test_detect.py -v`
- Package layout: top-level `xyb/`

### Suggested Fix
增加 `tests/conftest.py` 将项目根目录插入 `sys.path`，稳定本地测试导入行为。

---
