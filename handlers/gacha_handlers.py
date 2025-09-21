from astrbot.api.event import filter, AstrMessageEvent
from ..utils import parse_target_user_id

class GachaHandlers:
    @filter.command("抽奖", alias={"单抽"})
    async def gacha(self, event: AstrMessageEvent):
        """抽奖"""
        user_id = self._get_effective_user_id(event)
        result = self.gacha_service.perform_gacha(user_id, False)
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 抽奖失败：{result['message']}")

    @filter.command("十连抽奖", alias={"十连"})
    async def ten_gacha(self, event: AstrMessageEvent):
        """十连抽奖"""
        user_id = self._get_effective_user_id(event)
        result = self.gacha_service.perform_gacha(user_id, True)
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 十连抽奖失败：{result['message']}")

    @filter.command("查看奖池", alias={"奖池"})
    async def view_gacha_pool(self, event: AstrMessageEvent):
        """查看奖池信息"""
        gacha_pools = self.gacha_service.get_gacha_pools()
        if gacha_pools:
            message = "【🎁 奖池信息】\n"
            for pool in gacha_pools:
                message += f"\n--- {pool.name} ---\n"
                message += f"{pool.description}\n"
                message += "【物品列表】\n"
                for item in pool.items:
                    message += f"  - {item.item_name} (稀有度: {item.rarity}) - 权重: {item.weight}\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result("❌ 获取奖池信息失败。")

    @filter.command("抽奖记录", alias={"抽奖历史"})
    async def gacha_history(self, event: AstrMessageEvent):
        """查看抽奖记录"""
        user_id = self._get_effective_user_id(event)
        result = self.gacha_service.get_gacha_history(user_id)
        if result["success"]:
            message = "【📜 抽奖记录】\n"
            for record in result["history"]:
                message += f" - {record.item_name} (稀有度: {record.rarity}) - {record.gacha_time.strftime('%Y-%m-%d %H:%M')}\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result("❌ 获取抽奖记录失败。")

    @filter.command("擦炮")
    async def wipe_bomb(self, event: AstrMessageEvent):
        """擦炮小游戏"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        
        target_user_id, error_msg = parse_target_user_id(event, args, 1)
        if error_msg:
            yield event.plain_result(error_msg)
            return
            
        result = self.game_mechanics_service.use_wipe_bomb(user_id, target_user_id)
        if result:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("擦炮记录", alias={"擦炮历史"})
    async def wipe_bomb_history(self, event: AstrMessageEvent):
        """查看擦炮记录"""
        user_id = self._get_effective_user_id(event)
        result = self.game_mechanics_service.get_wipe_bomb_history(user_id)
        if result["success"]:
            message = "【📜 擦炮记录】\n"
            for record in result["history"]:
                message += (f" - {record.timestamp.strftime('%Y-%m-%d %H:%M')}: "
                            f"对 {record.target_nickname} 使用了擦炮，"
                            f"{'成功' if record.is_success else '失败'}\n")
            yield event.plain_result(message)
        else:
            yield event.plain_result("❌ 获取擦炮记录失败。")
