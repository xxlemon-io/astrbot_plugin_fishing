from astrbot.api.event import AstrMessageEvent
from typing import Optional, Dict, Any, TYPE_CHECKING, List
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from ..main import FishingPlugin


class ExchangeHandlers:
    def __init__(self, plugin: "FishingPlugin"):
        self.plugin = plugin
        self.exchange_service = plugin.exchange_service
        self.user_repo = plugin.user_repo

    def _get_effective_user_id(self, event: AstrMessageEvent) -> str:
        return self.plugin._get_effective_user_id(event)

    def _get_sentiment_emoji(self, sentiment: str) -> str:
        """获取市场情绪对应的表情符号"""
        sentiment_map = {
            "bullish": "🐂",
            "bearish": "🐻",
            "neutral": "😐",
            "optimistic": "😊",
            "pessimistic": "😟",
            "volatile": "🌪️",
        }
        return sentiment_map.get(sentiment.lower(), "❓")

    def _get_trend_emoji(self, trend: str) -> str:
        """获取价格趋势对应的表情符号"""
        trend_map = {
            "rising": "📈",
            "falling": "📉",
            "stable": "➖",
            "volatile": "🌊",
            "sideways": "↔️",
        }
        return trend_map.get(trend.lower(), "❓")

    def _get_formatted_update_schedule(self) -> str:
        """获取格式化的价格更新时间描述"""
        schedule = self.exchange_service.price_service.get_update_schedule()
        if not schedule:
            return "未配置"
        return "、".join(t.strftime("%H:%M") for t in schedule)

    def _get_price_history_help(self) -> str:
        """获取价格历史帮助信息"""
        return """【📈 价格历史帮助】
══════════════════════════════
📊 历史数据功能
• 交易所 历史: 查看7天价格历史
• 交易所 历史 [天数]: 查看指定天数历史
• 交易所 历史 [商品]: 查看指定商品历史

📈 图表信息
• 价格走势图: 显示价格变化趋势
• 涨跌幅统计: 计算期间涨跌情况
• 波动性分析: 评估价格波动程度
• 支撑阻力位: 识别关键价格点位

💡 使用技巧
• 观察价格趋势，判断买卖时机
• 关注成交量变化，分析市场活跃度
• 识别价格模式，预测未来走势
• 结合技术指标，提高分析准确性

══════════════════════════════
💬 示例: 【交易所 历史 3】查看3天价格历史
        """

    def _get_market_analysis_help(self) -> str:
        """获取市场分析帮助信息"""
        return """【📈 市场分析帮助】
══════════════════════════════
📊 分析指标
• 市场情绪: 反映投资者心理状态
• 价格趋势: 显示价格发展方向
• 供需状态: 分析市场供需平衡
• 波动性: 评估价格波动程度

📈 技术分析
• 移动平均线: 平滑价格波动
• 相对强弱指数: 判断超买超卖
• 布林带: 识别价格通道
• 成交量分析: 验证价格走势

💡 投资建议
• 趋势跟踪: 跟随主要趋势方向
• 反转策略: 在极端位置反向操作
• 分散投资: 降低单一商品风险
• 止损止盈: 控制风险和锁定利润

══════════════════════════════
💬 使用【交易所 分析】查看详细分析报告
        """

    def _get_trading_stats_help(self) -> str:
        """获取交易统计帮助信息"""
        return """【📈 交易统计帮助】
══════════════════════════════
📊 个人统计
• 总交易次数: 累计买卖操作次数
• 总交易金额: 累计交易金币数量
• 盈亏统计: 总体盈亏情况
• 胜率分析: 盈利交易占比

📈 持仓分析
• 当前持仓: 各商品持有数量
• 持仓价值: 按当前价格计算总价值
• 持仓成本: 购买时的总成本
• 浮动盈亏: 未实现盈亏情况

💡 风险控制
• 仓位管理: 控制单次交易规模
• 止损设置: 设定最大亏损限额
• 分散投资: 避免集中持仓
• 定期评估: 定期检查投资组合

══════════════════════════════
💬 使用【交易所 统计】查看个人交易统计
        """

    def _to_base36(self, n: int) -> str:
        """将数字转换为Base36字符串"""
        if n == 0:
            return "0"
        out = []
        while n > 0:
            n, remainder = divmod(n, 36)
            out.append("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[remainder])
        return "".join(reversed(out))

    def _get_commodity_display_code(self, instance_id: int) -> str:
        """生成大宗商品的显示ID"""
        return f"C{self._to_base36(instance_id)}"

    def _calculate_inventory_profit_loss(
        self, inventory: Dict[str, Any], current_prices: Dict[str, int]
    ) -> Dict[str, Any]:
        """计算库存盈亏分析 - 统一的数据流方法"""
        try:
            total_cost = 0
            total_current_value = 0

            for commodity_id, commodity_data in inventory.items():
                total_cost += commodity_data.get("total_cost", 0)
                current_price = current_prices.get(commodity_id, 0)

                # 检查每个商品实例是否腐败
                commodity_value = 0
                for item in commodity_data.get("items", []):
                    if not isinstance(item, dict):
                        continue

                    expires_at = item.get("expires_at")
                    quantity = item.get("quantity", 0)

                    if expires_at and isinstance(expires_at, datetime):
                        now = datetime.now()
                        is_expired = expires_at <= now

                        if is_expired:
                            # 腐败商品按0价值计算
                            commodity_value += 0
                        else:
                            # 未腐败商品按当前市场价格计算
                            commodity_value += current_price * quantity
                    else:
                        # 如果没有过期时间信息，按当前市场价格计算
                        commodity_value += current_price * quantity

                total_current_value += commodity_value

            profit_loss = total_current_value - total_cost
            profit_rate = (profit_loss / total_cost * 100) if total_cost > 0 else 0

            return {
                "total_cost": total_cost,
                "total_current_value": total_current_value,
                "profit_loss": profit_loss,
                "profit_rate": profit_rate,
                "is_profit": profit_loss > 0,
            }
        except Exception as e:
            from astrbot.api import logger

            logger.error(f"计算库存盈亏分析失败: {e}")
            return {
                "total_cost": 0,
                "total_current_value": 0,
                "profit_loss": 0,
                "profit_rate": 0,
                "is_profit": False,
            }

    def _from_base36(self, s: str) -> int:
        """将base36字符串转换为数字"""
        return int(s, 36)

    def _parse_commodity_display_code(self, code: str) -> Optional[int]:
        """解析大宗商品的显示ID，返回instance_id"""
        code = code.strip().upper()
        if code.startswith("C") and len(code) > 1:
            try:
                return self._from_base36(code[1:])
            except ValueError:
                return None
        return None

    def _sparkline(self, values: List[int]) -> str:
        """将数值列表转换为简单的 Unicode sparkline。"""
        if not values:
            return ""
        ticks = "▁▂▃▄▅▆▇█"
        mn, mx = min(values), max(values)
        if mx == mn:
            return ticks[0] * len(values)
        def scale(v: int) -> int:
            idx = int((v - mn) / (mx - mn) * (len(ticks) - 1))
            return max(0, min(len(ticks) - 1, idx))
        return "".join(ticks[scale(v)] for v in values)

    async def _view_price_history(self, event: AstrMessageEvent):
        """查看价格历史曲线：
        - 交易所 历史 -> 默认7天，显示所有商品
        - 交易所 历史 [天数] -> 显示指定天数，所有商品
        - 交易所 历史 [商品] -> 默认7天，仅该商品
        - 交易所 历史 [商品] [天数] -> 指定商品与天数
        """
        args = event.message_str.split()
        # 解析参数
        target_commodity_name: Optional[str] = None
        days = 7
        # 支持的商品名映射
        market_status = self.exchange_service.get_market_status()
        if not market_status.get("success"):
            yield event.plain_result(f"❌ 获取市场信息失败: {market_status.get('message','未知错误')}")
            return
        name_to_id = {info["name"]: cid for cid, info in market_status.get("commodities", {}).items()}

        # 参数形态判断
        # 交易所 历史
        # 交易所 历史 X
        # 交易所 历史 商品
        # 交易所 历史 商品 X
        if len(args) >= 3:
            p = args[2]
            # 若是数字，解析为天数
            if p.isdigit():
                days = max(1, min(30, int(p)))
            else:
                # 解析商品名
                if p in name_to_id:
                    target_commodity_name = p
                else:
                    # 不是数字也不是商品名——回显帮助
                    yield event.plain_result(self._get_price_history_help())
                    return
                # 若还有第四个参数作为天数
                if len(args) >= 4 and args[3].isdigit():
                    days = max(1, min(30, int(args[3])))

        # 获取历史数据
        hist = self.exchange_service.get_price_history(days=days)
        if not hist.get("success"):
            yield event.plain_result(f"❌ 获取历史失败: {hist.get('message','未知错误')}")
            return

        history: Dict[str, List[int]] = hist.get("history", {})
        labels: List[str] = hist.get("labels", [])

        # 根据商品过滤
        if target_commodity_name:
            cid = name_to_id.get(target_commodity_name)
            if not cid:
                yield event.plain_result(f"❌ 找不到商品: {target_commodity_name}")
                return
            history = {cid: history.get(cid, [])}

        # 没有任何数据
        if not history:
            yield event.plain_result("暂无历史数据。")
            return

        # 构造输出
        msg = "【📈 价格历史】\n"
        msg += f"区间: 近{days}天\n"
        msg += "═" * 30 + "\n"

        # 反查 id->name
        id_to_name = {cid: info["name"] for cid, info in market_status.get("commodities", {}).items()}

        for cid, series in history.items():
            name = id_to_name.get(cid, cid)
            if not series:
                continue
            spark = self._sparkline(series)
            start = series[0]
            end = series[-1]
            change = end - start
            pct = (change / start * 100) if start > 0 else 0
            msg += f"{name}: {spark}\n"
            msg += f"  起始 {start:,} → 当前 {end:,} 变化 {change:+,} ({pct:+.1f}%)\n"

        # 附上少量时间刻度（最多显示首末和中间几个）
        if labels:
            picked: List[str] = []
            if len(labels) <= 5:
                picked = labels
            else:
                idxs = [0, len(labels)//4, len(labels)//2, 3*len(labels)//4, len(labels)-1]
                seen = set()
                for i in idxs:
                    if 0 <= i < len(labels) and i not in seen:
                        picked.append(labels[i])
                        seen.add(i)
            if picked:
                msg += "─" * 30 + "\n"
                msg += "时间刻度: " + " | ".join(picked) + "\n"

        msg += "═" * 30 + "\n"
        msg += "💡 用法：交易所 历史 [商品] [天数]；最多30天。"

        yield event.plain_result(msg)

    async def _view_market_analysis(self, event: AstrMessageEvent):
        """市场分析：
        - 交易所 分析 -> 默认分析全部商品，7天窗口
        - 交易所 分析 [商品] -> 分析单商品，7天窗口
        - 交易所 分析 [商品] [天数] -> 分析单商品，指定窗口（1-30）
        - 交易所 分析 [天数] -> 分析全部商品，指定窗口
        """
        from math import sqrt
        args = event.message_str.split()
        target_commodity_name: Optional[str] = None
        days = 7

        market_status = self.exchange_service.get_market_status()
        if not market_status.get("success"):
            yield event.plain_result(f"❌ 获取市场信息失败: {market_status.get('message','未知错误')}")
            return
        commodities = market_status.get("commodities", {})
        name_to_id = {info["name"]: cid for cid, info in commodities.items()}
        id_to_name = {cid: info["name"] for cid, info in commodities.items()}

        # 解析参数：可能是（分析）、（分析 X）、（分析 商品）、（分析 商品 X）
        if len(args) >= 3:
            p = args[2]
            if p.isdigit():
                days = max(1, min(30, int(p)))
            else:
                if p in name_to_id:
                    target_commodity_name = p
                else:
                    yield event.plain_result(self._get_market_analysis_help())
                    return
                if len(args) >= 4 and args[3].isdigit():
                    days = max(1, min(30, int(args[3])))

        hist = self.exchange_service.get_price_history(days=days)
        if not hist.get("success"):
            yield event.plain_result(f"❌ 获取历史失败: {hist.get('message','未知错误')}")
            return
        history: Dict[str, List[int]] = hist.get("history", {})

        # 过滤商品
        if target_commodity_name:
            cid = name_to_id.get(target_commodity_name)
            if not cid:
                yield event.plain_result(f"❌ 找不到商品: {target_commodity_name}")
                return
            history = {cid: history.get(cid, [])}

        if not history:
            yield event.plain_result("暂无可分析的数据。")
            return

        def sma(series: List[int], n: int) -> float:
            if not series or n <= 0:
                return 0.0
            n = min(n, len(series))
            return sum(series[-n:]) / n

        def volatility(series: List[int]) -> float:
            if len(series) < 2:
                return 0.0
            # 简单标准差近似：与均值的偏差
            m = sum(series) / len(series)
            var = sum((x - m) ** 2 for x in series) / (len(series) - 1)
            epsilon = 1e-6
            denom = m if abs(m) >= epsilon else epsilon
            return sqrt(var) / denom * 100

        def simple_rsi(series: List[int]) -> float:
            # 简易RSI：最近N-1日涨幅与跌幅的比率
            if len(series) < 3:
                return 50.0
            window = min(15, len(series) - 1)
            if window < 1:
                return 50.0
            gains = 0.0
            losses = 0.0
            for a, b in zip(series[-(window+1):-1], series[-window:]):
                diff = b - a
                if diff > 0:
                    gains += diff
                elif diff < 0:
                    losses -= diff
            if gains + losses == 0:
                return 50.0
            rs = gains / max(1e-9, losses)
            rsi = 100 - (100 / (1 + rs))
            return max(0.0, min(100.0, rsi))

        def trend(series: List[int]) -> str:
            MIN_WINDOW = 5
            if len(series) < MIN_WINDOW:
                # For very short series, trend is unreliable
                return "stable"
            # Use at least MIN_WINDOW or len(series)//3, whichever is larger
            window = max(MIN_WINDOW, len(series)//3)
            start_idx = max(0, len(series) - window)
            start = series[start_idx]
            end = series[-1]
            if end > start * 1.02:
                return "rising"
            return "falling" if end < start * 0.98 else "stable"

        def suggestion(trend_val: str, rsi_val: float, vol_val: float) -> str:
            if trend_val == "rising" and rsi_val < 70:
                return "趋势向上，可考虑顺势少量买入"
            if trend_val == "falling" and rsi_val > 30:
                return "趋势向下，谨慎观望或逢反弹减仓"
            if vol_val > 15:
                return "波动较大，建议降低仓位控制风险"
            return "以观望为主，等待更明确信号"

        msg = "【📊 市场分析】\n"
        msg += f"窗口: 近{days}天\n"
        msg += "═" * 30 + "\n"

        for cid, series in history.items():
            if not series:
                continue
            name = id_to_name.get(cid, cid)
            last = series[-1]
            ma3 = sma(series, 3)
            ma5 = sma(series, 5)
            ma7 = sma(series, 7)
            vol = volatility(series)
            rsi = simple_rsi(series)
            tr = trend(series)
            sug = suggestion(tr, rsi, vol)

            msg += f"{name}\n"
            msg += f"  当前价: {last:,}\n"
            msg += f"  均线: MA3={ma3:.0f}  MA5={ma5:.0f}  MA7={ma7:.0f}\n"
            msg += f"  波动率: {vol:.1f}%  RSI: {rsi:.0f}\n"
            msg += f"  趋势: {tr}  建议: {sug}\n"
            msg += "─" * 20 + "\n"

        msg += "💡 提示：指标仅供参考，注意风险控制。\n"
        msg += "用法: 交易所 分析 [商品] [天数]"

        yield event.plain_result(msg)

    async def exchange_main(self, event: AstrMessageEvent):
        """交易所主命令，根据参数分发到不同功能"""
        args = event.message_str.split()

        if len(args) == 1:
            # 无参数，显示交易所状态
            async for r in self.exchange_status(event):
                yield r
        elif len(args) >= 2:
            command = args[1].lower()
            if command in ["开户", "account"]:
                async for r in self.open_exchange_account(event):
                    yield r
            elif command in ["买入", "buy", "purchase"]:
                async for r in self.buy_commodity(event):
                    yield r
            elif command in ["卖出", "sell"]:
                async for r in self.sell_commodity(event):
                    yield r
            elif command in ["帮助", "help"]:
                yield event.plain_result(self._get_exchange_help())
            elif command in ["历史", "history"]:
                async for r in self._view_price_history(event):
                    yield r
            elif command in ["分析", "analysis"]:
                async for r in self._view_market_analysis(event):
                    yield r
            elif command in ["统计", "stats"]:
                yield event.plain_result(self._get_trading_stats_help())
            elif command in ["状态", "status"]:
                async for r in self.exchange_status(event):
                    yield r
            else:
                yield event.plain_result(
                    "❌ 未知命令。使用【交易所 帮助】查看可用命令。"
                )

    def _get_exchange_help(self) -> str:
        """获取交易所帮助信息"""
        schedule_display = self._get_formatted_update_schedule()
        return f"""【📈 交易所帮助】
══════════════════════════════
📊 市场信息
• 交易所: 查看市场状态和价格
• 交易所 历史: 查看价格历史图表
• 交易所 分析: 查看市场分析报告

💼 账户管理
• 交易所 开户: 开通交易所账户
• 交易所 状态: 查看账户状态
• 交易所 统计: 查看交易统计

💰 交易操作
• 交易所 买入 [商品] [数量]: 购买大宗商品
• 交易所 卖出 [商品] [数量]: 卖出大宗商品
• 交易所 卖出 [库存ID] [数量]: 按库存ID卖出

📦 库存管理
• /持仓: 查看我的库存详情
• /清仓: 卖出所有库存
• /清仓 [商品]: 卖出指定商品
• /清仓 [库存ID]: 卖出指定库存

📈 投资分析
• /盈亏: 查看持仓盈亏分析
• /推荐: 获取投资建议
• /风险: 查看风险评估

⏰ 时间信息
• 价格更新: 每日{schedule_display}
• 商品保质期: 鱼干3天、鱼卵2天、鱼油1-3天
• 交易时间: 24小时开放

💡 交易提示
• 关注价格涨跌幅，把握买卖时机
• 注意商品保质期，及时卖出避免腐败
• 合理控制仓位，分散投资风险
• 关注市场情绪和供需状态

══════════════════════════════
💬 使用【交易所 帮助 [分类]】查看详细说明
    """

    async def exchange_status(self, event: AstrMessageEvent):
        """查看交易所当前状态"""
        try:
            user_id = self._get_effective_user_id(event)
            user = self.user_repo.get_by_id(user_id)

            if not user or not user.exchange_account_status:
                yield event.plain_result(
                    "您尚未开通交易所账户，请使用【交易所 开户】命令开户。"
                )
                return

            result = self.exchange_service.get_market_status()
            if not result["success"]:
                yield event.plain_result(
                    f"❌ 查询失败: {result.get('message', '未知错误')}"
                )
                return

            prices = result["prices"]
            commodities = result["commodities"]

            # 获取价格历史用于计算涨跌幅（使用“上一次价格”而非“昨天”）
            price_history = self.exchange_service.get_price_history(days=2)
            previous_prices = {}
            if price_history.get("success"):
                updates = price_history.get("updates", []) or []
                # 将更新按商品分组（updates 已按时间排序）
                updates_by_comm: Dict[str, list] = {}
                for u in updates:
                    cid = u.get("commodity_id")
                    if not cid:
                        continue
                    updates_by_comm.setdefault(cid, []).append(u)

                # 取每个商品的倒数第二条作为“上一次价格”
                for cid, ulist in updates_by_comm.items():
                    if len(ulist) >= 2:
                        previous_prices[cid] = ulist[-2].get("price")

            msg = "【📈 交易所行情】\n"
            msg += f"更新时间: {result.get('date', 'N/A')}\n"
            msg += "═" * 30 + "\n"

            # 显示市场情绪和趋势（移到商品价格上面）
            market_sentiment = result.get("market_sentiment", "neutral")
            price_trend = result.get("price_trend", "stable")
            supply_demand = result.get("supply_demand", "平衡")

            msg += f"📊 市场情绪: {self._get_sentiment_emoji(market_sentiment)} {market_sentiment}\n"
            msg += f"📈 价格趋势: {self._get_trend_emoji(price_trend)} {price_trend}\n"
            msg += f"⚖️ 供需状态: {supply_demand}\n"
            msg += "─" * 20 + "\n"

            # 显示每个商品的详细信息
            for comm_id, price in prices.items():
                commodity = commodities.get(comm_id)
                if commodity:
                    msg += f"商品: {commodity['name']}\n"
                    msg += f"价格: {price:,} 金币"

                    # 计算涨跌幅
                    if comm_id in previous_prices:
                        prev_price = previous_prices[comm_id]
                        change = price - prev_price
                        change_percent = (
                            (change / prev_price) * 100 if prev_price > 0 else 0
                        )

                        if change > 0:
                            msg += f" 📈 +{change:,} (+{change_percent:.1f}%)"
                        elif change < 0:
                            msg += f" 📉 {change:,} ({change_percent:.1f}%)"
                        else:
                            msg += f" ➖ 0 (0.0%)"
                    else:
                        msg += " 🆕 新价格"

                    msg += "\n"
                    msg += f"描述: {commodity['description']}\n"
                    msg += "─" * 20 + "\n"

            # 显示持仓容量和盈亏分析
            capacity = self.plugin.exchange_service.config.get("exchange", {}).get("capacity", 1000)

            inventory_result = self.plugin.exchange_service.get_user_inventory(user_id)
            if inventory_result["success"]:
                inventory = inventory_result["inventory"]
                current_total_quantity = sum(
                    data.get("total_quantity", 0) for data in inventory.values()
                )
                capacity_percent = (
                    (current_total_quantity / capacity) * 100 if capacity > 0 else 0
                )

                msg += f"📦 当前持仓: {current_total_quantity} / {capacity} ({capacity_percent:.1f}%)\n"

                if inventory:
                    analysis = self._calculate_inventory_profit_loss(inventory, prices)
                    profit_status = (
                        "📈盈利"
                        if analysis["is_profit"]
                        else "📉亏损" if analysis["profit_loss"] < 0 else "➖持平"
                    )
                    msg += f"💰 持仓盈亏: {analysis['profit_loss']:+,} 金币 ({analysis['profit_rate']:+.1f}%) {profit_status}\n"

                    # 显示各商品持仓详情
                    if len(inventory) > 0:
                        msg += "📋 持仓详情:\n"
                        for comm_id, data in inventory.items():
                            if data.get("total_quantity", 0) > 0:
                                commodity = commodities.get(comm_id, {})
                                current_price = prices.get(comm_id, 0)
                                total_value = data.get("total_quantity", 0) * current_price
                                msg += f"  • {commodity.get('name', comm_id)}: {data.get('total_quantity', 0)}个 (价值 {total_value:,} 金币)\n"
                else:
                    msg += "📋 持仓详情: 暂无持仓\n"
            else:
                msg += f"📦 当前持仓: 无法获取 / {capacity}\n"

            # 显示下次更新时间
            schedule = self.exchange_service.price_service.get_update_schedule()
            now = datetime.now()
            next_update = None
            for scheduled_time in schedule:
                update_time = now.replace(
                    hour=scheduled_time.hour,
                    minute=scheduled_time.minute,
                    second=0,
                    microsecond=0,
                )
                if update_time > now:
                    next_update = update_time
                    break

            if not next_update and schedule:
                first_time = schedule[0]
                next_update = (now + timedelta(days=1)).replace(
                    hour=first_time.hour,
                    minute=first_time.minute,
                    second=0,
                    microsecond=0,
                )

            if next_update:
                time_diff = next_update - now
                hours = int(time_diff.total_seconds() // 3600)
                minutes = int((time_diff.total_seconds() % 3600) // 60)
                msg += f"⏰ 下次更新: {next_update.strftime('%H:%M')} (约{hours}小时{minutes}分钟后)\n"
            else:
                msg += "⏰ 下次更新: 未配置\n"

            msg += "═" * 30 + "\n"
            msg += "💡 使用【交易所 帮助】查看更多命令。"

            yield event.plain_result(msg)
        except Exception as e:
            from astrbot.api import logger
            logger.error(f"交易所状态查询失败: {e}")
            yield event.plain_result(f"❌ 查询失败: {str(e)}")

    async def open_exchange_account(self, event: AstrMessageEvent):
        """开通交易所账户"""
        user_id = self._get_effective_user_id(event)
        result = self.exchange_service.open_exchange_account(user_id)
        yield event.plain_result(
            f"✅ {result['message']}"
            if result["success"]
            else f"❌ {result['message']}"
        )

    async def view_inventory(self, event: AstrMessageEvent):
        """查看大宗商品库存"""
        try:
            from astrbot.api import logger

            user_id = self._get_effective_user_id(event)

            result = self.exchange_service.get_user_inventory(user_id)
            if not result["success"]:
                yield event.plain_result(f"❌ {result.get('message', '查询失败')}")
                return

            inventory = result["inventory"]
            if not inventory:
                yield event.plain_result("您的交易所库存为空。")
                return

            market_status = self.exchange_service.get_market_status()
            current_prices = market_status.get("prices", {})

            analysis = self._calculate_inventory_profit_loss(inventory, current_prices)

            msg = "【📦 我的交易所库存】\n"
            msg += "═" * 30 + "\n"

            profit_status = (
                "📈盈利"
                if analysis["is_profit"]
                else "📉亏损" if analysis["profit_loss"] < 0 else "➖持平"
            )
            msg += f"📊 总体盈亏：{analysis['profit_loss']:+} 金币 {profit_status}\n"
            msg += f"💰 总成本：{analysis['total_cost']:,} 金币\n"
            msg += f"💎 当前价值：{analysis['total_current_value']:,} 金币\n"
            msg += f"📈 盈利率：{analysis['profit_rate']:+.1f}%\n"
            msg += "─" * 30 + "\n"

            for commodity_id, commodity_data in inventory.items():
                try:
                    commodity_name = commodity_data.get("name", "未知商品")
                    total_quantity = commodity_data.get("total_quantity", 0)

                    current_price = current_prices.get(commodity_id, 0)

                    # 计算商品总价值，考虑腐败状态
                    commodity_value = 0
                    for item in commodity_data.get("items", []):
                        if not isinstance(item, dict):
                            continue

                        expires_at = item.get("expires_at")
                        quantity = item.get("quantity", 0)

                        if expires_at and isinstance(expires_at, datetime):
                            now = datetime.now()
                            is_expired = expires_at <= now

                            if is_expired:
                                # 腐败商品按0价值计算
                                commodity_value += 0
                            else:
                                # 未腐败商品按当前市场价格计算
                                commodity_value += current_price * quantity
                        else:
                            # 如果没有过期时间信息，按当前市场价格计算
                            commodity_value += current_price * quantity

                    profit_loss = commodity_value - commodity_data.get("total_cost", 0)
                    profit_status = (
                        "📈" if profit_loss > 0 else "📉" if profit_loss < 0 else "➖"
                    )
                    msg += f"{commodity_name} ({total_quantity}个) - 盈亏: {profit_loss:+}金币 {profit_status}\n"

                    for item in commodity_data.get("items", []):
                        if not isinstance(item, dict):
                            continue

                        expires_at = item.get("expires_at")
                        instance_id = item.get("instance_id")
                        quantity = item.get("quantity", 0)

                        if (
                            expires_at
                            and isinstance(expires_at, datetime)
                            and instance_id is not None
                        ):
                            time_left = expires_at - datetime.now()
                            display_id = self._get_commodity_display_code(instance_id)

                            if time_left.total_seconds() <= 0:
                                time_str = "💀 已腐败"
                            elif time_left.total_seconds() < 86400:
                                hours = int(time_left.total_seconds() // 3600)
                                time_str = f"⚠️剩{hours}小时"
                            else:
                                days = int(time_left.total_seconds() // 86400)
                                remaining_hours = int(
                                    (time_left.total_seconds() % 86400) // 3600
                                )
                                if remaining_hours > 0:
                                    time_str = f"✅剩{days}天{remaining_hours}小时"
                                else:
                                    time_str = f"✅剩{days}天"

                            msg += f"  └─ {display_id}: {quantity}个 ({time_str})\n"

                except Exception as e:
                    logger.error(f"处理库存项失败: {e}")
                    continue

            msg += "═" * 30 + "\n"

            capacity = self.exchange_service.config.get("exchange", {}).get("capacity", 1000)
            current_total_quantity = sum(
                data.get("total_quantity", 0) for data in inventory.values()
            )
            msg += f"📦 当前持仓: {current_total_quantity} / {capacity}\n"

            yield event.plain_result(msg)

        except Exception as e:
            from astrbot.api import logger

            logger.error(f"持仓命令执行失败: {e}")
            yield event.plain_result(f"❌ 持仓命令执行失败: {e}")

    async def buy_commodity(self, event: AstrMessageEvent):
        """购买大宗商品"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split()

        if len(args) != 4:
            yield event.plain_result(
                "❌ 命令格式错误，请使用：交易所 买入 [商品名称] [数量]"
            )
            return

        commodity_name = args[2]
        try:
            quantity = int(args[3])
            if quantity <= 0:
                yield event.plain_result("❌ 数量必须是正整数")
                return
        except ValueError:
            yield event.plain_result("❌ 数量必须是有效的数字")
            return

        market_status = self.exchange_service.get_market_status()
        if not market_status["success"]:
            yield event.plain_result(
                f"❌ 获取价格失败: {market_status.get('message', '未知错误')}"
            )
            return

        commodity_id = None
        for cid, info in market_status["commodities"].items():
            if info["name"] == commodity_name:
                commodity_id = cid
                break

        if not commodity_id:
            yield event.plain_result(f"❌ 找不到商品: {commodity_name}")
            return

        current_price = market_status["prices"].get(commodity_id, 0)
        if current_price <= 0:
            yield event.plain_result(f"❌ 商品 {commodity_name} 价格异常")
            return

        result = self.exchange_service.purchase_commodity(
            user_id, commodity_id, quantity, current_price
        )
        yield event.plain_result(
            f"✅ {result['message']}"
            if result["success"]
            else f"❌ {result['message']}"
        )

    async def sell_commodity(self, event: AstrMessageEvent):
        """卖出大宗商品"""
        try:
            user_id = self._get_effective_user_id(event)
            args = event.message_str.split()

            market_status = self.exchange_service.get_market_status()
            if not market_status["success"]:
                yield event.plain_result(
                    f"❌ 获取价格失败: {market_status.get('message', '未知错误')}"
                )
                return

            if len(args) == 3:
                commodity_name = args[2]

                commodity_id = None
                for cid, info in market_status["commodities"].items():
                    if info["name"] == commodity_name:
                        commodity_id = cid
                        break

                if not commodity_id:
                    yield event.plain_result(f"❌ 找不到商品: {commodity_name}")
                    return

                current_price = market_status["prices"].get(commodity_id, 0)
                if current_price <= 0:
                    yield event.plain_result(f"❌ 商品 {commodity_name} 价格异常")
                    return

                inventory = self.exchange_service.get_user_commodities(user_id)
                commodity_items = [
                    item for item in inventory if item.commodity_id == commodity_id
                ]

                if not commodity_items:
                    yield event.plain_result(f"❌ 您没有 {commodity_name}")
                    return

                total_quantity = sum(item.quantity for item in commodity_items)

                result = self.exchange_service.sell_commodity(
                    user_id, commodity_id, total_quantity, current_price
                )
                yield event.plain_result(
                    f"✅ {result['message']}"
                    if result["success"]
                    else f"❌ {result['message']}"
                )

            elif len(args) == 4:
                inventory_id_str = args[2]

                instance_id = self._parse_commodity_display_code(inventory_id_str)
                if instance_id is None:
                    yield event.plain_result("❌ 库存ID格式错误，请使用C开头的ID")
                    return

                try:
                    quantity = int(args[3])
                    if quantity <= 0:
                        yield event.plain_result("❌ 数量必须是正整数")
                        return
                except ValueError:
                    yield event.plain_result("❌ 数量必须是有效的数字")
                    return

                inventory = self.exchange_service.get_user_commodities(user_id)
                commodity_item = next(
                    (item for item in inventory if item.instance_id == instance_id), None
                )

                if not commodity_item:
                    yield event.plain_result("❌ 找不到指定的库存项目")
                    return

                current_price = market_status["prices"].get(commodity_item.commodity_id, 0)
                if current_price <= 0:
                    yield event.plain_result(f"❌ 商品价格异常")
                    return

                result = self.exchange_service.sell_commodity_by_instance(
                    user_id, instance_id, quantity, current_price
                )
                yield event.plain_result(
                    f"✅ {result['message']}"
                    if result["success"]
                    else f"❌ {result['message']}"
                )
            else:
                yield event.plain_result("❌ 命令格式错误，请使用帮助查看。")
        except Exception as e:
            from astrbot.api import logger
            logger.error(f"卖出大宗商品失败: {e}")
            yield event.plain_result(f"❌ 卖出失败: {str(e)}")

    async def clear_inventory(self, event: AstrMessageEvent):
        """清仓功能"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split()

        if len(args) == 1 or (len(args) == 2 and args[1].lower() == "all"):
            result = self.exchange_service.clear_all_inventory(user_id)
            yield event.plain_result(
                f"✅ {result['message']}"
                if result["success"]
                else f"❌ {result['message']}"
            )
        elif len(args) == 2:
            commodity_name = args[1]

            market_status = self.exchange_service.get_market_status()
            if not market_status["success"]:
                yield event.plain_result(
                    f"❌ 获取价格失败: {market_status.get('message', '未知错误')}"
                )
                return

            commodity_id = None
            for cid, info in market_status["commodities"].items():
                if info["name"] == commodity_name:
                    commodity_id = cid
                    break

            if not commodity_id:
                yield event.plain_result(f"❌ 找不到商品: {commodity_name}")
                return

            result = self.exchange_service.clear_commodity_inventory(
                user_id, commodity_id
            )
            yield event.plain_result(
                f"✅ {result['message']}"
                if result["success"]
                else f"❌ {result['message']}"
            )
        else:
            yield event.plain_result(
                "❌ 命令格式错误，请使用：/清仓 或 /清仓 [商品名称]"
            )
