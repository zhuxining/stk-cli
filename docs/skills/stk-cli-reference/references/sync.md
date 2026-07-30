# Sync 命令

配置 `THS_USERNAME` 和 `THS_PASSWORD` 后使用：

```bash
stk group ths list
stk group sync diff <longport-group> [ths-group]
stk group sync push <longport-group> [ths-group] [--replace]
stk group sync pull <ths-group> [longport-group] [--replace]
```

- diff 只比较 Longport 源组和 THS 目标组。
- push 固定为 Longport → THS。
- pull 固定为 THS → Longport。
- 省略目标名称时使用源分组名。
- 默认追加且不删除目标现有成员；replace 使目标与源一致。
- 科创板、创业板和 ETF symbol 会在平台间转换；不支持的 THS 资产会被过滤。

返回 `SyncResult`，包含 `diff`、`added`、`removed` 和非致命 `errors`。
