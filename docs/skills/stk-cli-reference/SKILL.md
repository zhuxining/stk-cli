---
name: stk-cli-reference
description: >
  `stk` 是用于请求 K 线与技术指标、管理 Longport 分组、同步同花顺分组、
  扫描分组日线信号并按 entry/exit 分流的 JSON CLI。
---

# stk-cli 命令参考

所有命令输出 `{"ok": true/false, "data": ..., "error": ..., "meta": ...}`。
stdout 仅用于 JSON，日志写入 stderr。

## 路由

| 需求 | 参考 |
|---|---|
| 请求 K 线和指标 | `references/data.md` |
| 管理 Longport/同花顺分组、信号分流 | `references/group.md` |
| 跨平台同步 | `references/sync.md` |
| 扫描信号与理解返回字段 | `references/scan.md`、`references/output-schema.md` |
| 理解信号策略 | `references/signal-strategy.md` |

## 常用工作流

```bash
stk data kline 600519 --count 60
stk group longport list
stk group ths list
stk group sync diff 长桥组 同花顺组
stk group sync push 长桥组 同花顺组
stk scan 长桥组 --daily10
stk group route 长桥组 买入观察 卖出预警 --replace
```

Longport 是行情与主要分组平台；同花顺是分组同步对端。扫描和 route 的分组均为
Longport 分组。
