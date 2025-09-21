import os
from astrbot.api.event import filter, AstrMessageEvent
from ..utils import to_percentage, format_accessory_or_rod, format_rarity_display

def register_inventory_handlers(plugin):
    @filter.command("背包", alias={"查看背包", "我的背包"})
    async def user_backpack(event: AstrMessageEvent):
        """查看用户背包"""
        user_id = plugin._get_effective_user_id(event)
        user = plugin.user_repo.get_by_id(user_id)
        if user:
            # 导入绘制函数
            from ..draw.backpack import draw_backpack_image, get_user_backpack_data
            
            # 获取用户背包数据
            backpack_data = get_user_backpack_data(plugin.inventory_service, user_id)
            
            # 设置用户昵称
            backpack_data['nickname'] = user.nickname or user_id
            
            # 生成背包图像
            image = await draw_backpack_image(backpack_data, plugin.data_dir)
            # 保存图像到临时文件
            image_path = os.path.join(plugin.tmp_dir, "user_backpack.png")
            image.save(image_path)
            yield event.image_result(image_path)
        else:
            yield event.plain_result("❌ 您还没有注册，请先使用 /注册 命令注册。")

    @filter.command("鱼塘")
    async def pond(event: AstrMessageEvent):
        """查看用户鱼塘内的鱼"""
        user_id = plugin._get_effective_user_id(event)
        pond_fish = plugin.inventory_service.get_user_fish_pond(user_id)
        if pond_fish:
            fishes = pond_fish["fishes"]
            # 把fishes按稀有度分组
            fished_by_rarity = {}
            for fish in fishes:
                rarity = fish.get("rarity", "未知")
                if rarity not in fished_by_rarity:
                    fished_by_rarity[rarity] = []
                fished_by_rarity[rarity].append(fish)
            # 构造输出信息
            message = "【🐠 鱼塘】：\n"
            for rarity in sorted(fished_by_rarity.keys(), reverse=True):
                fish_list = fished_by_rarity[rarity]
                if fish_list:
                    message += f"\n {format_rarity_display(rarity)} 稀有度 {rarity}：\n"
                    for fish in fish_list:
                        message += f"  - {fish['name']} x  {fish['quantity']} （{fish['base_value']}金币 / 个） \n"
            message += f"\n🐟 总鱼数：{pond_fish['stats']['total_count']} 条\n"
            message += f"💰 总价值：{pond_fish['stats']['total_value']} 金币\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result("🐟 您的鱼塘是空的，快去钓鱼吧！")

    @filter.command("鱼塘容量")
    async def pond_capacity(event: AstrMessageEvent):
        """查看用户鱼塘容量"""
        user_id = plugin._get_effective_user_id(event)
        pond_capacity = plugin.inventory_service.get_user_fish_pond_capacity(user_id)
        if pond_capacity["success"]:
            message = f"🐠 您的鱼塘容量为 {pond_capacity['current_fish_count']} / {pond_capacity['fish_pond_capacity']} 条鱼。"
            yield event.plain_result(message)
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("升级鱼塘", alias={"鱼塘升级"})
    async def upgrade_pond(event: AstrMessageEvent):
        """升级鱼塘容量"""
        user_id = plugin._get_effective_user_id(event)
        result = plugin.inventory_service.upgrade_fish_pond(user_id)
        if result["success"]:
            yield event.plain_result(f"🐠 鱼塘升级成功！新容量为 {result['new_capacity']} 条鱼。")
        else:
            yield event.plain_result(f"❌ 升级失败：{result['message']}")

    @filter.command("鱼竿")
    async def rod(event: AstrMessageEvent):
        """查看用户鱼竿信息"""
        user_id = plugin._get_effective_user_id(event)
        rod_info = plugin.inventory_service.get_user_rod_inventory(user_id)
        if rod_info and rod_info["rods"]:
            # 构造输出信息,附带emoji
            message = "【🎣 鱼竿】：\n"
            for rod in rod_info["rods"]:
                message += format_accessory_or_rod(rod)
                if rod.get("bonus_rare_fish_chance", 1) != 1 and rod.get("bonus_fish_weight", 1.0) != 1.0:
                    message += f"   - 钓上鱼鱼类几率加成: {to_percentage(rod['bonus_rare_fish_chance'])}\n"
                message += f"   -精炼等级: {rod.get('refine_level', 1)}\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result("🎣 您还没有鱼竿，快去商店购买或抽奖获得吧！")

    @filter.command("精炼鱼竿", alias={"鱼竿精炼"})
    async def refine_rod(event: AstrMessageEvent):
        """精炼鱼竿"""
        user_id = plugin._get_effective_user_id(event)
        rod_info = plugin.inventory_service.get_user_rod_inventory(user_id)
        if not rod_info or not rod_info["rods"]:
            yield event.plain_result("❌ 您还没有鱼竿，请先购买或抽奖获得。")
            return
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要精炼的鱼竿 ID，例如：/精炼鱼竿 12")
            return
        rod_instance_id = args[1]
        if not rod_instance_id.isdigit():
            yield event.plain_result("❌ 鱼竿 ID 必须是数字，请检查后重试。")
            return
        result = plugin.inventory_service.refine(user_id, int(rod_instance_id), "rod")
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 精炼鱼竿失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("鱼饵")
    async def bait(event: AstrMessageEvent):
        """查看用户鱼饵信息"""
        user_id = plugin._get_effective_user_id(event)
        bait_info = plugin.inventory_service.get_user_bait_inventory(user_id)
        if bait_info and bait_info["baits"]:
            # 构造输出信息,附带emoji
            message = "【🐟 鱼饵】：\n"
            for bait in bait_info["baits"]:
                message += f" - {bait['name']} x {bait['quantity']} (稀有度: {format_rarity_display(bait['rarity'])})\n"
                message += f"   - ID: {bait['bait_id']}\n"
                if bait["duration_minutes"] > 0:
                    message += f"   - 持续时间: {bait['duration_minutes']} 分钟\n"
                if bait["effect_description"]:
                    message += f"   - 效果: {bait['effect_description']}\n"
                message += "\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result("🐟 您还没有鱼饵，快去商店购买或抽奖获得吧！")

    @filter.command("道具", alias={"我的道具", "查看道具"})
    async def items(event: AstrMessageEvent):
        """查看用户道具信息（文本版）"""
        user_id = plugin._get_effective_user_id(event)
        item_info = plugin.inventory_service.get_user_item_inventory(user_id)
        if item_info and item_info.get("items"):
            message = "【📦 道具】：\n"
            for it in item_info["items"]:
                consumable_text = "消耗品" if it.get("is_consumable") else "非消耗"
                message += f" - {it['name']} x {it['quantity']} (稀有度: {format_rarity_display(it['rarity'])}，{consumable_text})\n"
                message += f"   - ID: {it['item_id']}\n"
                if it.get("effect_description"):
                    message += f"   - 效果: {it['effect_description']}\n"
                message += "\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result("📦 您还没有道具。")

    @filter.command("使用道具", alias={"使用"})
    async def use_item(event: AstrMessageEvent):
        """使用一个或多个道具"""
        user_id = plugin._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要使用的道具 ID，例如：/使用道具 1")
            return
        
        item_id_str = args[1]
        if not item_id_str.isdigit():
            yield event.plain_result("❌ 道具 ID 必须是数字。")
            return
        
        item_id = int(item_id_str)
        
        quantity = 1
        if len(args) > 2 and args[2].isdigit():
            quantity = int(args[2])
            if quantity <= 0:
                yield event.plain_result("❌ 数量必须是正整数。")
                return

        result = plugin.inventory_service.use_item(user_id, item_id, quantity)
        
        if result and result.get("success"):
            yield event.plain_result(f"✅ {result['message']}")
        else:
            error_message = result.get('message', '未知错误') if result else '未知错误'
            yield event.plain_result(f"❌ 使用道具失败：{error_message}")

    @filter.command("卖道具", alias={"出售道具", "卖出道具"})
    async def sell_item(event: AstrMessageEvent):
        """卖出道具：/卖道具 <ID> [数量]，数量缺省为1"""
        user_id = plugin._get_effective_user_id(event)
        parts = event.message_str.strip().split()
        if len(parts) < 2:
            yield event.plain_result("❌ 用法：/卖道具 <道具ID> [数量]")
            return
        if not parts[1].isdigit():
            yield event.plain_result("❌ 道具ID必须是数字")
            return
        item_id = int(parts[1])
        qty = 1
        if len(parts) >= 3 and parts[2].isdigit():
            qty = int(parts[2])
        result = plugin.inventory_service.sell_item(user_id, item_id, qty)
        if result.get("success"):
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(result.get("message", "操作失败"))

    @filter.command("饰品")
    async def accessories(event: AstrMessageEvent):
        """查看用户饰品信息"""
        user_id = plugin._get_effective_user_id(event)
        accessories_info = plugin.inventory_service.get_user_accessory_inventory(user_id)
        if accessories_info and accessories_info["accessories"]:
            # 构造输出信息,附带emoji
            message = "【💍 饰品】：\n"
            for accessory in accessories_info["accessories"]:
                message += format_accessory_or_rod(accessory)
                message += f"   -精炼等级: {accessory.get('refine_level', 1)}\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result("💍 您还没有饰品，快去商店购买或抽奖获得吧！")

    @filter.command("精炼饰品", alias={"饰品精炼"})
    async def refine_accessory(event: AstrMessageEvent):
        """精炼饰品"""
        user_id = plugin._get_effective_user_id(event)
        accessories_info = plugin.inventory_service.get_user_accessory_inventory(user_id)
        if not accessories_info or not accessories_info["accessories"]:
            yield event.plain_result("❌ 您还没有饰品，请先购买或抽奖获得。")
            return
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要精炼的饰品 ID，例如：/精炼饰品 15")
            return
        accessory_instance_id = args[1]
        if not accessory_instance_id.isdigit():
            yield event.plain_result("❌ 饰品 ID 必须是数字，请检查后重试。")
            return
        result = plugin.inventory_service.refine(user_id, int(accessory_instance_id), "accessory")
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 精炼饰品失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("精炼帮助", alias={"精炼说明", "精炼"})
    async def refine_help(event: AstrMessageEvent):
        """精炼系统帮助（当前版本）"""
        help_message = """🔨 精炼系统指南（当前版本）

═══════════════════════════════════
📖 核心规则
═══════════════════════════════════

• 精炼对象：鱼竿、饰品（同模板之间精炼）
• 等级范围：1级 → 10级（目前的满级）
• 消耗条件：同模板材料 + 金币
• 每次只升1级：精N → 精N+1
• 材料选择：优先使用"未装备、精炼等级最低"的同模板实例；永不使用正在装备的作为材料

成功：
• 目标等级+1，消耗1件材料与对应金币

失败（三种）：
• 普通失败：装备本体不变，但会消耗1件材料与对应金币
• 降级失败：装备等级-1，消耗1件材料与对应金币（10%概率）
• 毁坏失败（高等级概率触发）：消耗1件材料与对应金币，并摧毁本体装备

═══════════════════════════════════
🌟 稀有度与费用/成功率
═══════════════════════════════════

🎲 成功率（关键档位）：
• 1-4星：前期成功率高，后期逐步下降（更易满精）
• 5星：6→10级约为 50%、40%、35%、30%、25%
• 6星：6→10级约为 45%、35%、30%、25%、20%
• 7星及以上：挑战性高，6→10级约为 60%、50%、40%、30%、20%

提示：成功率按"目标新等级"计算（例如精2→精3，用精3的成功率）。

═══════════════════════════════════
⚡ 属性成长与加成
═══════════════════════════════════

• 1-3星：≈+15%/级
• 4星：≈+12%/级
• 5星：≈+8%/级
• 6星：≈+5%/级
• 7星+：≈+3%/级

═══════════════════════════════════
💰 精炼收益（系统回收价）
═══════════════════════════════════

• 售价 = 基础价(按稀有度) × 精炼等级乘数
• 基础价（示例）：1★=100，2★=500，3★=2000，4★=5000，5★=10000
• 精炼乘数（示例）：1→10级：1.0, 1.6, 3.0, 6.0, 12.0, 25.0, 55.0, 125.0, 280.0, 660.0
• 设计目标：收益随等级近指数增长，高精炼装备可覆盖成本并获得显著利润
• 批量出售会逐件按该规则计价，跳过正在装备的物品
• 玩家市场价格由卖家自定，不受该公式限制

═══════════════════════════════════
🏆 耐久度（仅鱼竿）
═══════════════════════════════════

• 每次钓鱼：鱼竿耐久 -1，降至0自动卸下
• 精炼成功：耐久恢复至当前最大值
• 每升1级：最大耐久度 ×1.5（累计）
• 神器奖励：5星及以上鱼竿精炼到10级 → 获得"无限耐久"（∞）
• 饰品无耐久度，不受上述规则影响

═══════════════════════════════════
📉 失败类型与概率
═══════════════════════════════════

🎲 降级概率（固定）：
• 所有等级：10%概率降级

💥 毁坏概率（5级及以上）：
• 1-2星：30%概率毁坏
• 3-4星：35%概率毁坏
• 5-6星：40%概率毁坏
• 7星+：50%概率毁坏

💔 普通失败：剩余概率（装备保持不变）

═══════════════════════════════════
📝 命令用法
═══════════════════════════════════

• /精炼鱼竿 [鱼竿实例ID]
• /精炼饰品 [饰品实例ID]
• 需要至少两件同模板装备（目标 + 材料）
• 查看背包以确认实例ID：/背包、/鱼竿、/饰品

"""

        yield event.plain_result(help_message)

    @filter.command("锁定鱼竿", alias={"鱼竿锁定"})
    async def lock_rod(event: AstrMessageEvent):
        """锁定鱼竿，防止被当作精炼材料、卖出、上架（仍可作为主装备精炼）"""
        user_id = plugin._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要锁定的鱼竿 ID，例如：/锁定鱼竿 15")
            return
        
        rod_instance_id = args[1]
        if not rod_instance_id.isdigit():
            yield event.plain_result("❌ 鱼竿 ID 必须是数字，请检查后重试。")
            return
        
        result = plugin.inventory_service.lock_rod(user_id, int(rod_instance_id))
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 锁定失败：{result['message']}")

    @filter.command("解锁鱼竿", alias={"鱼竿解锁"})
    async def unlock_rod(event: AstrMessageEvent):
        """解锁鱼竿，允许正常操作"""
        user_id = plugin._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要解锁的鱼竿 ID，例如：/解锁鱼竿 15")
            return
        
        rod_instance_id = args[1]
        if not rod_instance_id.isdigit():
            yield event.plain_result("❌ 鱼竿 ID 必须是数字，请检查后重试。")
            return
        
        result = plugin.inventory_service.unlock_rod(user_id, int(rod_instance_id))
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 解锁失败：{result['message']}")

    @filter.command("锁定饰品", alias={"饰品锁定"})
    async def lock_accessory(event: AstrMessageEvent):
        """锁定饰品，防止被当作精炼材料、卖出、上架（仍可作为主装备精炼）"""
        user_id = plugin._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要锁定的饰品 ID，例如：/锁定饰品 15")
            return
        
        accessory_instance_id = args[1]
        if not accessory_instance_id.isdigit():
            yield event.plain_result("❌ 饰品 ID 必须是数字，请检查后重试。")
            return
        
        result = plugin.inventory_service.lock_accessory(user_id, int(accessory_instance_id))
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 锁定失败：{result['message']}")

    @filter.command("解锁饰品", alias={"饰品解锁"})
    async def unlock_accessory(event: AstrMessageEvent):
        """解锁饰品，允许正常操作"""
        user_id = plugin._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要解锁的饰品 ID，例如：/解锁饰品 15")
            return
        
        accessory_instance_id = args[1]
        if not accessory_instance_id.isdigit():
            yield event.plain_result("❌ 饰品 ID 必须是数字，请检查后重试。")
            return
        
        result = plugin.inventory_service.unlock_accessory(user_id, int(accessory_instance_id))
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 解锁失败：{result['message']}")

    @filter.command("使用鱼竿 ", alias={"装备鱼竿"})
    async def use_rod(event: AstrMessageEvent):
        """使用鱼竿"""
        user_id = plugin._get_effective_user_id(event)
        rod_info = plugin.inventory_service.get_user_rod_inventory(user_id)
        if not rod_info or not rod_info["rods"]:
            yield event.plain_result("❌ 您还没有鱼竿，请先购买或抽奖获得。")
            return
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要使用的鱼竿 ID，例如：/使用鱼竿 12")
            return

        rod_instance_id = args[1]
        if not rod_instance_id.isdigit():
            yield event.plain_result("❌ 鱼竿 ID 必须是数字，请检查后重试。")
            return
        result = plugin.inventory_service.equip_item(user_id, int(rod_instance_id), "rod")
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 使用鱼竿失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("使用鱼饵", alias={"装备鱼饵"})
    async def use_bait(event: AstrMessageEvent):
        """使用鱼饵"""
        user_id = plugin._get_effective_user_id(event)
        bait_info = plugin.inventory_service.get_user_bait_inventory(user_id)
        if not bait_info or not bait_info["baits"]:
            yield event.plain_result("❌ 您还没有鱼饵，请先购买或抽奖获得。")
            return
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要使用的鱼饵 ID，例如：/使用鱼饵 13")
            return
        bait_instance_id = args[1]
        if not bait_instance_id.isdigit():
            yield event.plain_result("❌ 鱼饵 ID 必须是数字，请检查后重试。")
            return
        result = plugin.inventory_service.use_bait(user_id, int(bait_instance_id))
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 使用鱼饵失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("使用饰品", alias={"装备饰品"})
    async def use_accessories(event: AstrMessageEvent):
        """使用饰品"""
        user_id = plugin._get_effective_user_id(event)
        accessories_info = plugin.inventory_service.get_user_accessory_inventory(user_id)
        if not accessories_info or not accessories_info["accessories"]:
            yield event.plain_result("❌ 您还没有饰品，请先购买或抽奖获得。")
            return
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要使用的饰品 ID，例如：/使用饰品 15")
            return
        accessory_instance_id = args[1]
        if not accessory_instance_id.isdigit():
            yield event.plain_result("❌ 饰品 ID 必须是数字，请检查后重试。")
            return
        result = plugin.inventory_service.equip_item(user_id, int(accessory_instance_id), "accessory")
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 使用饰品失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("金币")
    async def coins(event: AstrMessageEvent):
        """查看用户金币信息"""
        user_id = plugin._get_effective_user_id(event)
        user = plugin.user_repo.get_by_id(user_id)
        if user:
            yield event.plain_result(f"💰 您的金币余额：{user.coins} 金币")
        else:
            yield event.plain_result("❌ 您还没有注册，请先使用 /注册 命令注册。")

    @filter.command("高级货币", alias={"钻石", "星石"})
    async def premium(event: AstrMessageEvent):
        """查看用户高级货币信息"""
        user_id = plugin._get_effective_user_id(event)
        user = plugin.user_repo.get_by_id(user_id)
        if user:
            yield event.plain_result(f"💎 您的高级货币余额：{user.premium_currency}")
        else:
            yield event.plain_result("❌ 您还没有注册，请先使用 /注册 命令注册。")

    plugin.add_handler(user_backpack)
    plugin.add_handler(pond)
    plugin.add_handler(pond_capacity)
    plugin.add_handler(upgrade_pond)
    plugin.add_handler(rod)
    plugin.add_handler(refine_rod)
    plugin.add_handler(bait)
    plugin.add_handler(items)
    plugin.add_handler(use_item)
    plugin.add_handler(sell_item)
    plugin.add_handler(accessories)
    plugin.add_handler(refine_accessory)
    plugin.add_handler(refine_help)
    plugin.add_handler(lock_rod)
    plugin.add_handler(unlock_rod)
    plugin.add_handler(lock_accessory)
    plugin.add_handler(unlock_accessory)
    plugin.add_handler(use_rod)
    plugin.add_handler(use_bait)
    plugin.add_handler(use_accessories)
    plugin.add_handler(coins)
    plugin.add_handler(premium)
