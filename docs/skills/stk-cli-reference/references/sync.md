# Sync 命令参考

**何时读取**：用户要同步长桥和同花顺自选数据（推或拉）、对比分组差异、或查看同花顺分组时读取此文件。

## 前置条件

需要先配置 `.env`：

```env
THS_USERNAME=手机号
THS_PASSWORD=密码
```

---

## 适用场景

- 查看同花顺现有分组：`stk sync ths list`
- 同步前预览差异：`stk sync ths diff`
- 将长桥自选推送到同花顺：`stk sync ths push`
- 将同花顺自选拉取到长桥：`stk sync ths pull`

建议流程：先 `list` 了解分组 → `diff` 预览变更 → `push`/`pull` 执行。

---

## `stk sync ths list`

列出同花顺所有自选分组（含"我的自选"默认分组）。

```bash
stk sync ths list
```

**示例输出**：
```json
{
  "ok": true,
  "data": [
    {"name": "我的自选", "group_id": "default", "count": 25, "readonly": false},
    {"name": "科创板精选", "group_id": "g_abc123", "count": 10, "readonly": false}
  ]
}
```

- `readonly: true` 表示同花顺动态板块，不可写入（仅警告，不会报错）
- 返回 `ThsGroup[]`

---

## `stk sync ths diff`

对比长桥与同花顺分组差异，**不修改任何数据**。始终在 push/pull 前先跑一次 diff。

```bash
stk sync ths diff --from A股持仓 --to 我的自选
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--from` `-f` | 必填 | 长桥分组名（源） |
| `--to` `-t` | 同 `--from` | 同花顺分组名（目标）。不指定时间名同 `--from` |

**示例输出**：
```json
{
  "ok": true,
  "data": {
    "action": "diff",
    "diff": {
      "from_group": "A股持仓",
      "to_group": "我的自选",
      "to_add": ["600519.SH", "300750.SZ"],
      "to_remove": ["000001.SZ"],
      "unchanged": 23
    }
  }
}
```

返回 `SyncResult`。

---

## `stk sync ths push`

将长桥分组推送到同花顺。目标分组不存在时自动创建。

```bash
# 仅追加（安全，不会删目标端数据）
stk sync ths push --from A股持仓 --to 我的自选

# 全量覆盖（镜像同步）
stk sync ths push --from A股持仓 --to 我的自选 --replace
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--from` `-f` | 必填 | 长桥分组名（源） |
| `--to` `-t` | 同 `--from` | 同花顺分组名（目标） |
| `--replace` `-r` | `false` | 不加 = 仅追加（长桥标的追加到同花顺，保留同花顺已有标的）。加 = 全量覆盖（先删除目标端不在源端的标的，再写入源端全量） |

**推送规则**：
- 自动跳过指数等不支持品种
- 科创板自动映射：`688xxx.SH` → `688xxx.KC`
- 创业板自动映射：`300xxx/301xxx.SZ` → `300xxx/301xxx.CYB`
- 只读分组（同花顺动态板块）不可写入，仅警告

**示例输出**：
```json
{
  "ok": true,
  "data": {
    "action": "push",
    "diff": {...},
    "added": 2,
    "removed": 0,
    "errors": []
  }
}
```

返回 `SyncResult`。

---

## `stk sync ths pull`

将同花顺分组拉取到长桥。目标长桥分组不存在时自动创建。

```bash
# 仅追加
stk sync ths pull --from 我的自选 --to A股持仓

# 全量覆盖
stk sync ths pull --from 我的自选 --to A股持仓 --replace
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--from` `-f` | 必填 | 同花顺分组名（源） |
| `--to` `-t` | 同 `--from` | 长桥分组名（目标） |
| `--replace` `-r` | `false` | 不加 = 仅追加（LP Add 模式天然去重）。加 = 使用原子 Replace API 全量替换长桥分组 |

**拉取规则**（与 push 反向映射）：
- 科创板自动映射：`688xxx.KC` → `688xxx.SH`
- 创业板自动映射：`300xxx/301xxx.CYB` → `300xxx/301xxx.SZ`

返回 `SyncResult`，结构同 push。
