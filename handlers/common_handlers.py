import os
from astrbot.api.event import filter, AstrMessageEvent
from ..draw.help import draw_help_image
from ..draw.state import draw_state_image, get_user_state_data
from ..core.utils import get_now
from ..utils import safe_datetime_handler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import FishingPlugin


async def register_user(self: "FishingPlugin", event: AstrMessageEvent):
    """注册用户命令"""
    user_id = self._get_effective_user_id(event)
    nickname = event.get_sender_name() if event.get_sender_name() is not None else user_id
    if result := self.user_service.register(user_id, nickname):
        yield event.plain_result(result["message"])
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def sign_in(self: "FishingPlugin", event: AstrMessageEvent):
    """签到"""
    user_id = self._get_effective_user_id(event)
    result = self.user_service.daily_sign_in(user_id)
    if result["success"]:
        yield event.plain_result(result["message"])

async def state(self: "FishingPlugin", event: AstrMessageEvent):
    """查看用户状态"""
    user_id = self._get_effective_user_id(event)

    # 调用新的数据获取函数
    user_data = get_user_state_data(
        self.user_repo,
        self.inventory_repo,
        self.item_template_repo,
        self.log_repo,
        self.buff_repo,
        self.game_config,
        user_id,
    )
    
    if not user_data:
        yield event.plain_result('❌ 用户不存在，请先发送"注册"来开始游戏')
        return
    # 生成状态图像
    image = await draw_state_image(user_data, self.data_dir)
    # 保存图像到临时文件
    image_path = os.path.join(self.tmp_dir, "user_status.png")
    image.save(image_path)
    yield event.image_result(image_path)

async def fishing_log(self: "FishingPlugin", event: AstrMessageEvent):
    """查看钓鱼记录"""
    user_id = self._get_effective_user_id(event)
    if result := self.fishing_service.get_user_fish_log(user_id):
        if result["success"]:
            records = result["records"]
            if not records:
                yield event.plain_result("❌ 您还没有钓鱼记录。")
                return
            message = "【📜 钓鱼记录】：\n"
            for record in records:
                message += (f" - {record['fish_name']} ({'★' * record['fish_rarity']})\n"
                            f" - ⚖️重量: {record['fish_weight']} 克 - 💰价值: {record['fish_value']} 金币\n"
                            f" - 🔧装备： {record['accessory']} & {record['rod']} | 🎣鱼饵: {record['bait']}\n"
                            f" - 钓鱼时间: {safe_datetime_handler(record['timestamp'])}\n")
            yield event.plain_result(message)
        else:
            yield event.plain_result(f"❌ 获取钓鱼记录失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def fishing_help(self: "FishingPlugin", event: AstrMessageEvent):
    """显示钓鱼插件帮助信息"""
    image = draw_help_image()
    output_path = os.path.join(self.tmp_dir, "fishing_help.png")
    image.save(output_path)
    yield event.image_result(output_path)

async def transfer_coins(self: "FishingPlugin", event: AstrMessageEvent):
    """转账金币"""
    from ..utils import parse_target_user_id
    
    args = event.message_str.split(" ")
    
    # 解析目标用户ID（支持@和用户ID两种方式）
    target_user_id, error_msg = parse_target_user_id(event, args, 1)
    if error_msg:
        yield event.plain_result(error_msg)
        return
    
    # 检查转账金额参数
    if len(args) < 3:
        yield event.plain_result(
            "❌ 请指定转账金额，例如：/转账 @用户 1000 或 /转账 123456789 1000"
        )
        return
    
    amount_str = args[2]
    if not amount_str.isdigit():
        yield event.plain_result("❌ 转账金额必须是数字，请检查后重试。")
        return
    
    amount = int(amount_str)
    from_user_id = self._get_effective_user_id(event)
    
    # 调用转账服务
    result = self.user_service.transfer_coins(from_user_id, target_user_id, amount)
    yield event.plain_result(result["message"])


async def update_nickname(self: "FishingPlugin", event: AstrMessageEvent):
    """更新用户昵称"""
    args = event.message_str.split(" ")
    
    # 检查是否提供了新昵称
    if len(args) < 2:
        yield event.plain_result(
            "❌ 请提供新昵称，例如：/更新昵称 新的昵称\n"
            "💡 昵称要求：\n"
            "  - 不能为空\n"
            "  - 长度不超过32个字符\n"
            "  - 支持中文、英文、数字和常用符号"
        )
        return
    
    # 提取新昵称（支持包含空格的昵称）
    new_nickname = " ".join(args[1:])
    
    user_id = self._get_effective_user_id(event)
    
    # 调用用户服务更新昵称
    result = self.user_service.update_nickname(user_id, new_nickname)
    yield event.plain_result(result["message"])