# ============================================================================
# stk-cli 工作流编排
# 安装:  stk scripts install     (复制到 ~/.stk/Makefile)
# 使用:  make -f ~/.stk/Makefile <target> [VAR=value]
# 别名:  alias stk='make -f ~/.stk/Makefile'
#        stk daily
#        stk push GROUP=重点关注
# ============================================================================

# ── 默认目标 ────────────────────────────────────────────────────────────────
.DEFAULT_GOAL := help

help: ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── 每日监控 ────────────────────────────────────────────────────────────────

daily: candidates scoop scan route sync-push  ## 每日监控全流程

candidates: ## 获取今日技术候选股
	uv run stk market candidates

scoop: ## 候选股入库到"候选股"分组
	uv run stk watchlist scoop 候选股

scan: ## 扫描"候选股"分组
	uv run stk watchlist scan 候选股

route: ## 信号分流：买入→观察，卖出→预警
	uv run stk watchlist route 候选股 观察 预警

# ── 分组扫描 ────────────────────────────────────────────────────────────────

scan-group: ## 扫描指定分组  make scan-group GROUP=重点关注
	uv run stk watchlist scan $(GROUP)

kline: ## 分组 K 线    make kline GROUP=重点关注 COUNT=30
	uv run stk watchlist kline $(GROUP) --count $(or $(COUNT),20)

zigzag: ## 检测 zigzag  make zigzag SRC=ETF池 DST=zigzag-picks
	uv run stk watchlist zigzag $(SRC) $(DST)

# ── 同花顺同步 ──────────────────────────────────────────────────────────────

push: ## 推送分组到同花顺  make push GROUP=重点关注
	uv run stk sync ths push -f '$(GROUP)'

push-replace: ## 全量覆盖  make push-replace GROUP=重点关注
	uv run stk sync ths push -f '$(GROUP)' --replace

pull: ## 从同花顺拉取    make pull GROUP=重点关注
	uv run stk sync ths pull -f '$(GROUP)'

pull-replace: ## 全量拉取    make pull-replace GROUP=重点关注
	uv run stk sync ths pull -f '$(GROUP)' --replace

sync-push: ## 推送所有常用分组
	uv run stk sync ths push -f '观察'
	uv run stk sync ths push -f '预警'
	uv run stk sync ths push -f '重点关注'

sync-pull: ## 拉取所有常用分组
	uv run stk sync ths pull -f '重点关注'
	uv run stk sync ths pull -f 'ETF'

diff: ## 对比差异        make diff GROUP=重点关注
	uv run stk sync ths diff -f '$(GROUP)'

ths-list: ## 列出同花顺分组
	uv run stk sync ths list

# ── 实用工具 ────────────────────────────────────────────────────────────────

quote: ## 查询报价        make quote SYM=600519
	uv run stk stock quote $(SYM)

indicator: ## 技术指标      make indicator SYM=600519 IND=MACD
	uv run stk stock indicator $(SYM) $(or $(IND),MACD)

comparison: ## 同业对比    make comparison SYM=600519 TYPE=valuation
	uv run stk stock comparison $(SYM) --type $(or $(TYPE),valuation)

doctor: ## 数据源健康检查
	uv run stk doctor check

cache-clear: ## 清除缓存
	uv run stk cache clear

# ── 分组管理 ────────────────────────────────────────────────────────────────

watchlist: ## 显示分组        make watchlist GROUP=重点关注
	uv run stk watchlist show $(GROUP)

watchlist-list: ## 列出所有分组
	uv run stk watchlist list
