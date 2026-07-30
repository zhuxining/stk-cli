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

## 信号分流

```bash
stk group route <src> <entry-dst> <exit-dst> [--replace]
```

- 趋势买入、超卖修复进入 entry 组。
- 趋势退出进入 exit 组。
- 默认追加；replace 使两个目标组与本次结果一致。
- 三个分组均为 Longport 分组；entry 与 exit 不能同名。
