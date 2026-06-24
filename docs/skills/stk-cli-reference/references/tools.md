# Tools 命令参考

**何时读取**：用户要诊断数据源状态、管理缓存、或使用全局参数时读取此文件。

## 适用场景

- 检查数据源是否正常：`stk doctor check`
- 清除缓存获取最新数据：`stk cache clear`
- 查看缓存使用情况：`stk cache stats`
- 任意命令跳过缓存：`--no-cache` 全局标志

---

## `stk doctor check`

数据源健康检查。验证 longport API 和其他上游数据源是否可正常连接。

```bash
# 完整检查
stk doctor check

# 快速检查（跳过耗时项）
stk doctor check --quick
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--quick` | `false` | 快速模式，跳过某些耗时检测项 |

> **何时用**：扫描结果异常（无数据/大量报错）时先跑一次 doctor 确认数据源正常。

---

## `stk cache clear`

清除缓存，下次运行时强制从 API 获取最新数据。

```bash
# 清除所有缓存
stk cache clear

# 仅清除特定前缀的缓存
stk cache clear --prefix kline
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--prefix` | （无） | 仅清除匹配前缀的缓存条目。如 `kline` 仅清除 K 线缓存，保留行情缓存 |

> **何时用**：怀疑缓存数据过时（如价格已变但 scan 结果没反映），或刚修改了配置需要刷新。如果只是单次需要最新数据，用 `--no-cache` 更方便。

---

## `stk cache stats`

查看缓存统计信息：内存条目数、磁盘文件数、磁盘占用大小、缓存上限。

```bash
stk cache stats
```

---

## 全局参数：`--no-cache`

所有子命令通用的全局标志。跳过所有缓存，强制从 API 获取最新数据。不影响缓存内容本身（不清除，只是这次不用）。

```bash
# 单次跳过缓存获取最新数据
stk --no-cache watchlist scoop 热点股

# 临时获取最新行情
stk --no-cache market index
```

> **何时用**：偶尔需要最新数据但又不想清除缓存时使用。如果需要持续使用最新数据，用 `stk cache clear` 清掉缓存更高效。
