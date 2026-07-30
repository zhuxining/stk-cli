# Group 命令

## Longport

```bash
stk group longport list
stk group longport show <group>
stk group longport create <group> [--symbol SYMBOL ...]
stk group longport add <group> <symbols...>
stk group longport remove <group> <symbols...>
stk group longport delete <group>
```

## 同花顺

```bash
stk group ths list
```

同花顺分组写入由 sync 内部完成。

## 跨平台同步

配置 `THS_USERNAME` 和 `THS_PASSWORD` 后使用：

```bash
stk group sync diff <longport-group> [ths-group]
stk group sync push <longport-group> [ths-group] [--replace]
stk group sync pull <ths-group> [longport-group] [--replace]
```

- `diff` 比较 Longport 源组和 THS 目标组。
- `push` 固定为 Longport → THS，`pull` 固定为 THS → Longport。
- 省略目标名称时使用源分组名。
- 默认追加；`--replace` 使目标成员与源分组一致。
- 平台间会转换 Symbol，并过滤 THS 不支持的资产。

同步结果包含 `diff`、`added`、`removed` 和非致命 `errors`。

## 信号分流

```bash
stk group route <src> <buy-dst> <sell-dst> [--replace|--append]
```

- 默认 replace：buy 和 sell 都表示当前仍满足对应条件的信号快照。
- 两组从源分组独立计算，不依赖昨日成员或今日首次触发事件。
- 任一标的扫描失败时中止整个 route，两个目标组均不修改。
- `--append` 只兼容旧的追加工作流，不适合每日过滤。
- 三个分组均为 Longport 分组，并且必须互不相同。
