import os
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.message.components import At
from ..draw.rank import draw_fishing_ranking
from ..utils import parse_target_user_id

async def ranking(self, event: AstrMessageEvent):
    """查看排行榜"""
    user_data = self.user_service.get_leaderboard_data().get("leaderboard", [])
    if not user_data:
        yield event.plain_result("❌ 当前没有排行榜数据。")
        return
    for user in user_data:
        if user["title"] is None:
            user["title"] = "无称号"
        if user["accessory"] is None:
            user["accessory"] = "无饰品"
        if user["fishing_rod"] is None:
            user["fishing_rod"] = "无鱼竿"
    # logger.info(f"用户数据: {user_data}")
    output_path = os.path.join(self.tmp_dir, "fishing_ranking.png")
    draw_fishing_ranking(user_data, output_path=output_path)
    yield event.image_result(output_path)

async def steal_fish(self, event: AstrMessageEvent):
    """偷鱼功能"""
    user_id = self._get_effective_user_id(event)
    message_obj = event.message_obj
    target_id = None
    if hasattr(message_obj, "message"):
        # 检查消息中是否有At对象
        for comp in message_obj.message:
            if isinstance(comp, At):
                target_id = comp.qq
                break
    if target_id is None:
        yield event.plain_result("请在消息中@要偷鱼的用户")
        return
    if int(target_id) == int(user_id):
        yield event.plain_result("不能偷自己的鱼哦！")
        return
    result = self.game_mechanics_service.steal_fish(user_id, target_id)
    if result:
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 偷鱼失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def steal_with_dispel(self, event: AstrMessageEvent):
    """使用驱灵香偷鱼功能"""
    user_id = self._get_effective_user_id(event)
    message_obj = event.message_obj
    target_id = None
    if hasattr(message_obj, "message"):
        # 检查消息中是否有At对象
        for comp in message_obj.message:
            if isinstance(comp, At):
                target_id = comp.qq
                break
    if target_id is None:
        yield event.plain_result("请在消息中@要偷鱼的用户")
        return
    if int(target_id) == int(user_id):
        yield event.plain_result("不能偷自己的鱼哦！")
        return
    
    # 检查是否有驱灵香
    user_inventory = self.inventory_service.get_user_item_inventory(user_id)
    dispel_items = [item for item in user_inventory.get("items", []) 
                   if item.get("effect_type") == "STEAL_PROTECTION_REMOVAL"]
    
    if not dispel_items:
        yield event.plain_result("❌ 你没有驱灵香，无法使用此功能！")
        return
    
    # 先检查目标是否有海灵守护效果
    dispel_result = self.game_mechanics_service.check_steal_protection(target_id)
    if not dispel_result.get("has_protection"):
        yield event.plain_result(f"❌ 【{dispel_result.get('target_name', '目标')}】没有海灵守护效果，无需驱散！")
        return
    
    # 直接扣除驱灵香
    dispel_item = dispel_items[0]
    result = self.user_service.remove_item_from_user_inventory(user_id, "item", dispel_item["item_id"], 1)
    if not result.get("success"):
        yield event.plain_result(f"❌ 扣除驱灵香失败：{result.get('message', '未知错误')}")
        return
    
    # 驱散目标的海灵守护buff
    dispel_result = self.game_mechanics_service.dispel_steal_protection(target_id)
    if dispel_result.get("success"):
        yield event.plain_result(f"🔥 驱灵香的力量驱散了【{dispel_result.get('target_name', '目标')}】的海灵守护！")
    else:
        yield event.plain_result(f"❌ 驱散失败：{dispel_result.get('message', '未知错误')}")

async def view_titles(self, event: AstrMessageEvent):
    """查看用户称号"""
    user_id = self._get_effective_user_id(event)
    titles = self.user_service.get_user_titles(user_id).get("titles", [])
    if titles:
        message = "【🏅 您的称号】\n"
        for title in titles:
            message += f"- {title['name']} (ID: {title['title_id']})\n- 描述: {title['description']}\n\n"
        yield event.plain_result(message)
    else:
        yield event.plain_result("❌ 您还没有任何称号，快去完成成就或参与活动获取吧！")

async def use_title(self, event: AstrMessageEvent):
    """使用称号"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result("❌ 请指定要使用的称号 ID，例如：/使用称号 1")
        return
    title_id = args[1]
    if not title_id.isdigit():
        yield event.plain_result("❌ 称号 ID 必须是数字，请检查后重试。")
        return
    result = self.user_service.use_title(user_id, int(title_id))
    if result:
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 使用称号失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def view_achievements(self, event: AstrMessageEvent):
    """查看用户成就"""
    from ..utils import safe_datetime_handler
    user_id = self._get_effective_user_id(event)
    achievements = self.achievement_service.get_user_achievements(user_id).get("achievements", [])
    if achievements:
        message = "【🏆 您的成就】\n"
        for achievement in achievements:
            message += f"- {achievement['name']} (ID: {achievement['id']})\n"
            message += f"  描述: {achievement['description']}\n"
            if achievement.get("completed_at"):
                message += f"  完成时间: {safe_datetime_handler(achievement['completed_at'])}\n"
            else:
                message += "  进度: {}/{}\n".format(achievement["progress"], achievement["target"])
        message += "请继续努力完成更多成就！"
        yield event.plain_result(message)
    else:
        yield event.plain_result("❌ 您还没有任何成就，快去完成任务或参与活动获取吧！")

async def tax_record(self, event: AstrMessageEvent):
    """查看税收记录"""
    from ..utils import safe_datetime_handler
    user_id = self._get_effective_user_id(event)
    result = self.user_service.get_tax_record(user_id)
    if result:
        if result["success"]:
            records = result.get("records", [])
            if not records:
                yield event.plain_result("📜 您还没有税收记录。")
                return
            message = "【📜 税收记录】\n\n"
            for record in records:
                message += f"⏱️ 时间: {safe_datetime_handler(record['timestamp'])}\n"
                message += f"💰 金额: {record['amount']} 金币\n"
                message += f"📊 描述: {record['tax_type']}\n\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result(f"❌ 查看税收记录失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")
