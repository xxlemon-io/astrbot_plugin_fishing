from astrbot.api.event import AstrMessageEvent
from ..utils import format_rarity_display


async def aquarium(self, event: AstrMessageEvent):
    """查看用户水族箱"""
    user_id = self._get_effective_user_id(event)
    result = self.aquarium_service.get_user_aquarium(user_id)
    
    if not result["success"]:
        yield event.plain_result(f"❌ {result['message']}")
        return

    fishes = result["fishes"]
    stats = result["stats"]
    
    if not fishes:
        yield event.plain_result("🐠 您的水族箱是空的，快去钓鱼吧！")
        return

    # 按稀有度分组
    fishes_by_rarity = {}
    for fish in fishes:
        rarity = fish.get("rarity", "未知")
        if rarity not in fishes_by_rarity:
            fishes_by_rarity[rarity] = []
        fishes_by_rarity[rarity].append(fish)

    # 构造输出信息
    message = "【🐠 水族箱】：\n"
    
    for rarity in sorted(fishes_by_rarity.keys(), reverse=True):
        fish_list = fishes_by_rarity[rarity]
        if fish_list:
            message += f"\n {format_rarity_display(rarity)}：\n"
            for fish in fish_list:
                fish_id = int(fish.get('fish_id', 0) or 0)
                fcode = f"F{fish_id}" if fish_id else "F0"
                message += f"  - {fish['name']} x  {fish['quantity']} （{fish['base_value']}金币 / 个） ID: {fcode}\n"
    
    message += f"\n🐟 总鱼数：{stats['total_count']} / {stats['capacity']} 条\n"
    message += f"💰 总价值：{stats['total_value']} 金币\n"
    message += f"📦 剩余空间：{stats['available_space']} 条\n"
    
    yield event.plain_result(message)


async def add_to_aquarium(self, event: AstrMessageEvent):
    """将鱼从鱼塘添加到水族箱"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    
    if len(args) < 2:
        yield event.plain_result("❌ 用法：/放入水族箱 <鱼ID> [数量]\n💡 使用「水族箱」命令查看水族箱中的鱼")
        return

    try:
        fish_id = int(args[1])
        quantity = 1
        if len(args) >= 3:
            quantity = int(args[2])
            if quantity <= 0:
                yield event.plain_result("❌ 数量必须是正整数")
                return
    except ValueError:
        yield event.plain_result("❌ 鱼ID和数量必须是数字")
        return

    result = self.aquarium_service.add_fish_to_aquarium(user_id, fish_id, quantity)
    
    if result["success"]:
        yield event.plain_result(f"✅ {result['message']}")
    else:
        yield event.plain_result(f"❌ {result['message']}")


async def remove_from_aquarium(self, event: AstrMessageEvent):
    """将鱼从水族箱移回鱼塘"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    
    if len(args) < 2:
        yield event.plain_result("❌ 用法：/移出水族箱 <鱼ID> [数量]\n💡 使用「水族箱」命令查看水族箱中的鱼")
        return

    try:
        fish_id = int(args[1])
        quantity = 1
        if len(args) >= 3:
            quantity = int(args[2])
            if quantity <= 0:
                yield event.plain_result("❌ 数量必须是正整数")
                return
    except ValueError:
        yield event.plain_result("❌ 鱼ID和数量必须是数字")
        return

    result = self.aquarium_service.remove_fish_from_aquarium(user_id, fish_id, quantity)
    
    if result["success"]:
        yield event.plain_result(f"✅ {result['message']}")
    else:
        yield event.plain_result(f"❌ {result['message']}")


async def upgrade_aquarium(self, event: AstrMessageEvent):
    """升级水族箱容量"""
    user_id = self._get_effective_user_id(event)
    
    # 先检查是否可以升级
    check_result = self.aquarium_service.can_afford_upgrade(user_id)
    if not check_result["success"]:
        yield event.plain_result(f"❌ {check_result['message']}")
        return

    if not check_result["can_afford"]:
        message = "❌ 无法升级水族箱：\n"
        if not check_result["can_afford_coins"]:
            message += f"💰 金币不足：需要 {check_result['required_coins']}，当前 {check_result['user_coins']}\n"
        if not check_result["can_afford_premium"]:
            message += f"💎 钻石不足：需要 {check_result['required_premium']}，当前 {check_result['user_premium']}\n"
        yield event.plain_result(message)
        return

    # 执行升级
    result = self.aquarium_service.upgrade_aquarium(user_id)
    
    if result["success"]:
        yield event.plain_result(f"✅ {result['message']}")
    else:
        yield event.plain_result(f"❌ {result['message']}")


async def aquarium_upgrade_info(self, event: AstrMessageEvent):
    """查看水族箱升级信息"""
    user_id = self._get_effective_user_id(event)
    result = self.aquarium_service.get_aquarium_upgrade_info(user_id)
    
    if not result["success"]:
        yield event.plain_result(f"❌ {result['message']}")
        return

    current_level = result["current_level"]
    current_capacity = result["current_capacity"]
    next_upgrade = result["next_upgrade"]

    message = f"【🐠 水族箱升级信息】：\n"
    message += f"当前等级：{current_level}\n"
    message += f"当前容量：{current_capacity} 条\n"

    if next_upgrade:
        message += f"\n下一级升级：\n"
        message += f"等级：{next_upgrade.level}\n"
        message += f"容量：{next_upgrade.capacity} 条\n"
        message += f"费用：{next_upgrade.cost_coins} 金币"
        if next_upgrade.cost_premium > 0:
            message += f" + {next_upgrade.cost_premium} 钻石"
        message += f"\n描述：{next_upgrade.description}"
    else:
        message += "\n🎉 恭喜！您的水族箱已达到最高等级！"

    yield event.plain_result(message)


async def aquarium_help(self, event: AstrMessageEvent):
    """水族箱帮助信息"""
    message = """【🐠 水族箱系统帮助】：

🔹 水族箱是一个安全的存储空间，鱼放在里面不会被偷
🔹 默认容量50条，可以通过升级增加容量
🔹 从市场购买的鱼默认放入水族箱
🔹 可以正常上架和购买

📋 可用命令：
• /水族箱 - 查看水族箱中的鱼
• /放入水族箱 <鱼ID> [数量] - 将鱼从鱼塘放入水族箱
• /移出水族箱 <鱼ID> [数量] - 将鱼从水族箱移回鱼塘
• /升级水族箱 - 升级水族箱容量
• /水族箱升级信息 - 查看升级信息
• /水族箱帮助 - 显示此帮助信息

💡 提示：使用「水族箱」命令查看鱼ID"""
    
    yield event.plain_result(message)