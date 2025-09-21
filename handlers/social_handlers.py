import os
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.message.components import At
from ..draw.rank import draw_fishing_ranking
from ..utils import parse_target_user_id

class SocialHandlers:
    @filter.command("排行榜")
    async def ranking(self, event: AstrMessageEvent):
        """显示钓鱼排行榜"""
        user_id = self._get_effective_user_id(event)
        image = await draw_fishing_ranking(self.user_repo, self.inventory_repo, user_id, self.data_dir)
        yield event.image_result(image)

    @filter.command("偷鱼")
    async def steal_fish(self, event: AstrMessageEvent):
        """偷鱼"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        
        target_user_id, error_msg = parse_target_user_id(event, args, 1)
        if error_msg:
            yield event.plain_result(error_msg)
            return

        result = self.fishing_service.steal_fish(user_id, target_user_id)
        if result:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("高级偷鱼")
    async def steal_with_dispel(self, event: AstrMessageEvent):
        """高级偷鱼，消耗一个驱散卷轴，无视对方护盾（如果有）"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        
        target_user_id, error_msg = parse_target_user_id(event, args, 1)
        if error_msg:
            yield event.plain_result(error_msg)
            return

        result = self.fishing_service.steal_fish_with_dispel(user_id, target_user_id)
        if result:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("查看称号", alias={"我的称号"})
    async def view_titles(self, event: AstrMessageEvent):
        """查看用户称号"""
        user_id = self._get_effective_user_id(event)
        result = self.user_service.get_user_titles(user_id)
        if result["success"]:
            message = "【👑 我的称号】\n"
            for title in result["titles"]:
                message += f" - {title.name} (ID: {title.id}) {'(当前佩戴)' if title.is_equipped else ''}\n"
                message += f"   - 效果: {title.description}\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result("❌ 获取称号信息失败。")

    @filter.command("佩戴称号", alias={"使用称号"})
    async def use_title(self, event: AstrMessageEvent):
        """佩戴称号"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要佩戴的称号 ID，例如：/佩戴称号 1")
            return
        title_id = args[1]
        if not title_id.isdigit():
            yield event.plain_result("❌ 称号 ID 必须是数字，请检查后重试。")
            return
        result = self.user_service.set_user_title(user_id, int(title_id))
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 佩戴称号失败：{result['message']}")

    @filter.command("查看成就", alias={"我的成就"})
    async def view_achievements(self, event: AstrMessageEvent):
        """查看用户成就"""
        user_id = self._get_effective_user_id(event)
        result = self.achievement_service.get_user_achievements(user_id)
        if result["success"]:
            message = "【🏆 我的成就】\n"
            for achievement in result["achievements"]:
                message += f" - {achievement.name} {'(已完成)' if achievement.is_completed else ''}\n"
                message += f"   - 描述: {achievement.description}\n"
                message += f"   - 进度: {achievement.progress}/{achievement.target}\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result("❌ 获取成就信息失败。")

    @filter.command("税收记录")
    async def tax_record(self, event: AstrMessageEvent):
        """查看最近的税收记录"""
        user_id = self._get_effective_user_id(event)
        logs = self.log_repo.get_user_logs(user_id, "TAX_RECORD", 5)
        if not logs:
            yield event.plain_result("暂无税收记录。")
            return
        message = "【💰 最近5条税收记录】\n"
        for log in logs:
            message += f" - 时间: {log.timestamp.strftime('%Y-%m-%d %H:%M')}\n"
            message += f" - {log.message}\n"
        yield event.plain_result(message)
