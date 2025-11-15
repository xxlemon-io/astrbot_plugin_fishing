import os
import time
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.message.components import At
from astrbot.api import logger
from ..draw.rank import draw_fishing_ranking
from ..utils import parse_target_user_id

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import FishingPlugin


async def ranking(plugin: "FishingPlugin", event: AstrMessageEvent):
    """
    查看排行榜。
    支持按不同标准排序，例如：/排行榜 数量 或 /排行榜 重量 或 /排行榜 历史
    默认按金币排名。
    """
    args = event.message_str.split()
    ranking_type = "coins"

    if len(args) > 1:
        sort_key = args[1]
        if sort_key in ["数量", "钓获", "fish"]:
            ranking_type = "fish_count"
        elif sort_key in ["重量", "weight"]:
            ranking_type = "total_weight_caught"
        elif sort_key in ["历史", "最高", "max", "history", "历史最高"]:
            ranking_type = "max_coins"

    # 1. 从服务层获取基础排行榜数据（现在已包含 user_id 和 current_title_id）
    user_data = plugin.user_service.get_leaderboard_data(sort_by=ranking_type).get(
        "leaderboard", []
    )

    if not user_data:
        yield event.plain_result("❌ 当前没有排行榜数据。")
        return

    # 2. 遍历列表，为每个用户查询并填充装备和称号的【名称】
    for user_dict in user_data:
        user_id = user_dict.get("user_id")

        # 如果（因为某些意外）没有 user_id，则跳过查询，使用默认值
        if not user_id:
            user_dict["title"] = "无称号"
            user_dict["fishing_rod"] = "无鱼竿"
            user_dict["accessory"] = "无饰品"
            user_dict["total_weight_caught"] = user_dict.get("total_weight_caught", 0)
            continue

        # 获取鱼竿名称
        rod_name = "无鱼竿"
        rod_instance = plugin.inventory_repo.get_user_equipped_rod(user_id)
        if rod_instance:
            rod_template = plugin.item_template_repo.get_rod_by_id(rod_instance.rod_id)
            if rod_template:
                rod_name = rod_template.name
        user_dict["fishing_rod"] = rod_name

        # 获取饰品名称
        accessory_name = "无饰品"
        accessory_instance = plugin.inventory_repo.get_user_equipped_accessory(user_id)
        if accessory_instance:
            accessory_template = plugin.item_template_repo.get_accessory_by_id(
                accessory_instance.accessory_id
            )
            if accessory_template:
                accessory_name = accessory_template.name
        user_dict["accessory"] = accessory_name

        # 获取称号名称
        title_name = "无称号"
        if current_title_id := user_dict.get("current_title_id"):
            title_info = plugin.item_template_repo.get_title_by_id(current_title_id)
            if title_info:
                title_name = title_info.name
        user_dict["title"] = title_name

        # 确保重量字段存在，以防万一
        user_dict["total_weight_caught"] = user_dict.get("total_weight_caught", 0)

    # 3. 绘制并发送图片
    user_id_for_filename = plugin._get_effective_user_id(event)
    unique_id = getattr(
        event, "message_id", f"{user_id_for_filename}_{int(time.time())}"
    )
    # 安全化文件名，移除特殊字符
    from ..utils import sanitize_filename
    safe_unique_id = sanitize_filename(str(unique_id))
    output_path = os.path.join(plugin.tmp_dir, f"fishing_ranking_{safe_unique_id}.png")

    draw_fishing_ranking(user_data, output_path=output_path, ranking_type=ranking_type)
    yield event.image_result(output_path)


async def steal_fish(plugin: "FishingPlugin", event: AstrMessageEvent):
    """偷鱼功能"""
    user_id = plugin._get_effective_user_id(event)
    message_obj = event.message_obj
    target_id = None
    if hasattr(message_obj, "message"):
        for comp in message_obj.message:
            if isinstance(comp, At):
                if comp.qq != message_obj.self_id:
                    target_id = str(comp.qq)
                    break

    if target_id is None:
        parts = event.message_str.strip().split()
        if len(parts) >= 2:
            target_id = parts[1].strip()

    if not target_id:
        yield event.plain_result(
            "❌ 请指定偷鱼的用户！\n用法：/偷鱼 @用户 或 /偷鱼 用户ID"
        )
        return
    if str(target_id) == str(user_id):
        yield event.plain_result("不能偷自己的鱼哦！")
        return

    result = plugin.game_mechanics_service.steal_fish(user_id, target_id)
    if result:
        yield event.plain_result(result["message"])
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")


async def electric_fish(plugin: "FishingPlugin", event: AstrMessageEvent):
    """电鱼功能"""
    # 检查电鱼功能是否启用
    electric_fish_config = plugin.game_config.get("electric_fish", {})
    if not electric_fish_config.get("enabled", True):
        yield event.plain_result("❌ 电鱼功能已被管理员禁用！")
        return
    
    user_id = plugin._get_effective_user_id(event)
    message_obj = event.message_obj
    target_id = None
    if hasattr(message_obj, "message"):
        for comp in message_obj.message:
            if isinstance(comp, At):
                # 排除机器人本身的id
                if comp.qq != message_obj.self_id:
                    target_id = str(comp.qq)
                    break

    if target_id is None:
        parts = event.message_str.strip().split()
        if len(parts) >= 2:
            target_id = parts[1].strip()

    if not target_id:
        yield event.plain_result("❌ 请指定电鱼的用户！\n用法：/电鱼 @用户 或 /电鱼 用户ID")
        return
    if str(target_id) == str(user_id):
        yield event.plain_result("不能电自己的鱼哦！")
        return

    result = plugin.game_mechanics_service.electric_fish(user_id, target_id)
    if result:
        yield event.plain_result(result["message"])
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")


async def dispel_protection(plugin: "FishingPlugin", event: AstrMessageEvent):
    """使用驱灵香驱散目标的海灵守护"""
    user_id = plugin._get_effective_user_id(event)
    args = event.message_str.split()
    target_id, error_msg = parse_target_user_id(event, args, 1)

    if error_msg:
        yield event.plain_result(error_msg)
        return
    if not target_id:
        yield event.plain_result("请在消息中@要驱散守护的用户")
        return
    if str(target_id) == str(user_id):
        yield event.plain_result("不能对自己使用驱灵香哦！")
        return

    # 查找驱灵香道具
    all_items = plugin.item_template_repo.get_all_items()
    dispel_item = None
    for item in all_items:
        if item.effect_type == "STEAL_PROTECTION_REMOVAL":
            dispel_item = item
            break
    
    if not dispel_item:
        yield event.plain_result("❌ 系统错误：找不到驱灵香道具")
        return
    
    # 检查用户是否持有驱灵香
    item_inventory = plugin.inventory_repo.get_user_item_inventory(user_id)
    if item_inventory.get(dispel_item.item_id, 0) < 1:
        yield event.plain_result(f"❌ 你没有【{dispel_item.name}】道具！")
        return
    
    # 尝试驱散
    result = plugin.game_mechanics_service.dispel_steal_protection(target_id)
    
    if result.get("success"):
        # 成功驱散，消耗道具
        plugin.inventory_repo.decrease_item_quantity(user_id, dispel_item.item_id, 1)
        yield event.plain_result(f"✅ 使用了【{dispel_item.name}】！{result['message']}")
    else:
        yield event.plain_result(result["message"])


async def view_titles(plugin: "FishingPlugin", event: AstrMessageEvent):
    """查看用户称号"""
    user_id = plugin._get_effective_user_id(event)
    titles = plugin.user_service.get_user_titles(user_id).get("titles", [])
    if titles:
        message = "【🏅 您的称号】\n"
        for title in titles:
            status = " (当前装备)" if title["is_current"] else ""
            message += f"- {title['name']} (ID: {title['title_id']}){status}\n- 描述: {title['description']}\n\n"
        yield event.plain_result(message)
    else:
        yield event.plain_result("❌ 您还没有任何称号，快去完成成就或参与活动获取吧！")


async def use_title(plugin: "FishingPlugin", event: AstrMessageEvent):
    """使用称号"""
    user_id = plugin._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result("❌ 请指定要使用的称号 ID，例如：/使用称号 1")
        return
    title_id_str = args[1]
    if not title_id_str.isdigit():
        yield event.plain_result("❌ 称号 ID 必须是数字，请检查后重试。")
        return
    result = plugin.user_service.use_title(user_id, int(title_id_str))
    yield event.plain_result(result["message"])


async def view_achievements(plugin: "FishingPlugin", event: AstrMessageEvent):
    """查看用户成就"""
    from ..utils import safe_datetime_handler

    user_id = plugin._get_effective_user_id(event)
    achievements = plugin.achievement_service.get_user_achievements(user_id).get(
        "achievements", []
    )
    if achievements:
        message = "【🏆 您的成就】\n"
        for ach in achievements:
            message += f"- {ach['name']} (ID: {ach['id']})\n"
            message += f"  描述: {ach['description']}\n"
            if ach.get("completed_at"):
                message += f"  完成时间: {safe_datetime_handler(ach['completed_at'])}\n"
            else:
                message += "  进度: {}/{}\n".format(
                    ach.get("progress", 0), ach.get("target", 1)
                )
        message += "请继续努力完成更多成就！"
        yield event.plain_result(message)
    else:
        yield event.plain_result("❌ 您还没有任何成就，快去完成任务或参与活动获取吧！")


async def tax_record(plugin: "FishingPlugin", event: AstrMessageEvent):
    """查看税收记录"""
    from ..utils import safe_datetime_handler

    user_id = plugin._get_effective_user_id(event)
    result = plugin.user_service.get_tax_record(user_id)
    if result and result["success"]:
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
        yield event.plain_result(f"❌ 查看税收记录失败：{result.get('message', '未知错误')}")