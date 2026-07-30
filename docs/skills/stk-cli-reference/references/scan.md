# Scan 命令

```bash
stk scan <longport-group> [--daily10] [--full-context]
```

扫描 Longport 分组中的已确认日线信号：

- 默认仅展开推荐/预警 focus。
- `--daily10` 为适合复核的 focus 附加最近 10 根压缩日线。
- `--full-context` 保留 neutral/none 辅助因子。
- 单标的失败进入 `errors`，不会中断整个分组。

返回结构参见 `output-schema.md`，策略含义参见 `signal-strategy.md`。
