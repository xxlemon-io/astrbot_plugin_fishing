from astrbot.api.event import filter, AstrMessageEvent
from ..utils import parse_target_user_id, to_percentage, safe_datetime_handler

async def gacha(self, event: AstrMessageEvent):
    """抽卡"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        # 展示所有的抽奖池信息并显示帮助
        pools = self.gacha_service.get_all_pools()
        if not pools:
            yield event.plain_result("❌ 当前没有可用的抽奖池。")
            return
        message = "【🎰 抽奖池列表】\n\n"
        for pool in pools.get("pools", []):
            cost_text = f"💰 金币 {pool['cost_coins']} / 次"
            if pool['cost_premium_currency']:
                cost_text = f"💎 高级货币 {pool['cost_premium_currency']} / 次"
            message += f"ID: {pool['gacha_pool_id']} - {pool['name']} - {pool['description']}\n {cost_text}\n\n"
        # 添加卡池详细信息
        message += "【📋 卡池详情】使用「查看卡池 ID」命令查看详细物品概率\n"
        message += "【🎲 抽卡命令】使用「抽卡 ID」命令选择抽卡池进行单次抽卡\n"
        message += "【🎯 十连命令】使用「十连 ID」命令进行十连抽卡"
        yield event.plain_result(message)
        return
    pool_id = args[1]
    if not pool_id.isdigit():
        yield event.plain_result("❌ 抽奖池 ID 必须是数字，请检查后重试。")
        return
    pool_id = int(pool_id)
    result = self.gacha_service.perform_draw(user_id, pool_id, num_draws=1)
    if result:
        if result["success"]:
            items = result.get("results", [])
            message = f"🎉 抽卡成功！您抽到了 {len(items)} 件物品：\n"
            for item in items:
                # 构造输出信息
                if item.get("type") == "coins":
                    # 金币类型的物品
                    message += f"⭐ {item['quantity']} 金币！\n"
                else:
                    message += f"{'⭐' * item.get('rarity', 1)} {item['name']}\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result(f"❌ 抽卡失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def ten_gacha(self, event: AstrMessageEvent):
    """十连抽卡"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result("❌ 请指定要进行十连抽卡的抽奖池 ID，例如：/十连 1")
        return
    pool_id = args[1]
    if not pool_id.isdigit():
        yield event.plain_result("❌ 抽奖池 ID 必须是数字，请检查后重试。")
        return
    pool_id = int(pool_id)
    result = self.gacha_service.perform_draw(user_id, pool_id, num_draws=10)
    if result:
        if result["success"]:
            items = result.get("results", [])
            message = f"🎉 十连抽卡成功！您抽到了 {len(items)} 件物品：\n"
            for item in items:
                # 构造输出信息
                if item.get("type") == "coins":
                    # 金币类型的物品
                    message += f"⭐ {item['quantity']} 金币！\n"
                else:
                    message += f"{'⭐' * item.get('rarity', 1)} {item['name']}\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result(f"❌ 抽卡失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def view_gacha_pool(self, event: AstrMessageEvent):
    """查看当前卡池"""
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result("❌ 请指定要查看的卡池 ID，例如：/查看卡池 1")
        return
    pool_id = args[1]
    if not pool_id.isdigit():
        yield event.plain_result("❌ 卡池 ID 必须是数字，请检查后重试。")
        return
    pool_id = int(pool_id)
    result = self.gacha_service.get_pool_details(pool_id)
    if result:
        if result["success"]:
            pool = result.get("pool", {})
            message = "【🎰 卡池详情】\n\n"
            message += f"ID: {pool['gacha_pool_id']} - {pool['name']}\n"
            message += f"描述: {pool['description']}\n"
            # 限时开放信息展示
            try:
                if pool['is_limited_time']:
                    open_until = pool['open_until']
                    if open_until:
                        # 格式化为 YYYY/MM/DD HH:MM
                        display_time = open_until.replace('T', ' ').replace('-', '/')
                        if len(display_time) > 16:
                            display_time = display_time[:16]
                        message += f"限时开放 至: {display_time}\n"
            except Exception:
                pass
            if pool['cost_premium_currency']:
                message += f"花费: {pool['cost_premium_currency']} 高级货币 / 次\n\n"
            else:
                message += f"花费: {pool['cost_coins']} 金币 / 次\n\n"
            message += "【📋 物品概率】\n"

            if result["probabilities"]:
                for item in result["probabilities"]:
                    message += f" - {'⭐' * item.get('item_rarity', 0)} {item['item_name']} (概率: {to_percentage(item['probability'])})\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result(f"❌ 查看卡池失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def gacha_history(self, event: AstrMessageEvent):
    """查看抽卡记录"""
    user_id = self._get_effective_user_id(event)
    result = self.gacha_service.get_user_gacha_history(user_id)
    if result:
        if result["success"]:
            history = result.get("records", [])
            if not history:
                yield event.plain_result("📜 您还没有抽卡记录。")
                return
            message = "【📜 抽卡记录】\n\n"
            for record in history:
                message += f"物品名称: {record['item_name']} (稀有度: {'⭐' * record['rarity']})\n"
                message += f"时间: {safe_datetime_handler(record['timestamp'])}\n\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result(f"❌ 查看抽卡记录失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def wipe_bomb(self, event: AstrMessageEvent):
    """擦弹功能"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result("💸 请指定要擦弹的数量 ID，例如：/擦弹 123456789")
        return
    contribution_amount = args[1]
    if contribution_amount in ['allin', 'halfin', '梭哈', '梭一半']:
        # 查询用户当前金币数量
        user = self.user_repo.get_by_id(user_id)
        if user:
            coins = user.coins
        else:
            yield event.plain_result("❌ 您还没有注册，请先使用 /注册 命令注册。")
            return
        if contribution_amount in ('allin', '梭哈'):
            contribution_amount = coins
        elif contribution_amount in ('halfin', '梭一半'):
            contribution_amount = coins // 2
        contribution_amount = str(contribution_amount)
    # 判断是否为int或数字字符串
    if not contribution_amount.isdigit():
        yield event.plain_result("❌ 擦弹数量必须是数字，请检查后重试。")
        return
    result = self.game_mechanics_service.perform_wipe_bomb(user_id, int(contribution_amount))
    if result:
        if result["success"]:
            message = ""
            contribution = result["contribution"]
            multiplier = result["multiplier"]
            reward = result["reward"]
            profit = result["profit"]
            remaining_today = result["remaining_today"]
            
            # 格式化倍率，保留两位小数
            multiplier_formatted = f"{multiplier:.2f}"

            if multiplier >= 3:
                message += f"🎰 大成功！你投入 {contribution} 金币，获得了 {multiplier_formatted} 倍奖励！\n 💰 奖励金额：{reward} 金币（盈利：+ {profit}）\n"
            elif multiplier >= 1:
                message += f"🎲 你投入 {contribution} 金币，获得了 {multiplier_formatted} 倍奖励！\n 💰 奖励金额：{reward} 金币（盈利：+ {profit}）\n"
            else:
                message += f"💥 你投入 {contribution} 金币，获得了 {multiplier_formatted} 倍奖励！\n 💰 奖励金额：{reward} 金币（亏损：- {abs(profit)})\n"
            message += f"剩余擦弹次数：{remaining_today} 次\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result(f"⚠️ 擦弹失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def wipe_bomb_history(self, event: AstrMessageEvent):
    """查看擦弹记录"""
    user_id = self._get_effective_user_id(event)
    result = self.game_mechanics_service.get_wipe_bomb_history(user_id)
    if result:
        if result["success"]:
            history = result.get("logs", [])
            if not history:
                yield event.plain_result("📜 您还没有擦弹记录。")
                return
            message = "【📜 擦弹记录】\n\n"
            for record in history:
                # 添加一点emoji
                message += f"⏱️ 时间: {safe_datetime_handler(record['timestamp'])}\n"
                message += f"💸 投入: {record['contribution']} 金币, 🎁 奖励: {record['reward']} 金币\n"
                # 计算盈亏
                profit = record["reward"] - record["contribution"]
                profit_text = f"盈利: +{profit}" if profit >= 0 else f"亏损: {profit}"
                profit_emoji = "📈" if profit >= 0 else "📉"

                if record["multiplier"] >= 3:
                    message += f"🔥 倍率: {record['multiplier']} ({profit_emoji} {profit_text})\n\n"
                elif record["multiplier"] >= 1:
                    message += f"✨ 倍率: {record['multiplier']} ({profit_emoji} {profit_text})\n\n"
                else:
                    message += f"💔 倍率: {record['multiplier']} ({profit_emoji} {profit_text})\n\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result(f"❌ 查看擦弹记录失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")
