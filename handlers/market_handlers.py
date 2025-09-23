from astrbot.api.event import filter, AstrMessageEvent
from ..utils import format_rarity_display, parse_target_user_id

async def sell_all(self, event: AstrMessageEvent):
    """卖出用户所有鱼"""
    user_id = self._get_effective_user_id(event)
    if result := self.inventory_service.sell_all_fish(user_id):
        yield event.plain_result(result["message"])
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def sell_keep(self, event: AstrMessageEvent):
    """卖出用户鱼，但保留每种鱼一条"""
    user_id = self._get_effective_user_id(event)
    if result := self.inventory_service.sell_all_fish(user_id, keep_one=True):
        yield event.plain_result(result["message"])
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def sell_everything(self, event: AstrMessageEvent):
    """砸锅卖铁：出售所有未锁定且未装备的鱼竿、饰品和全部鱼类"""
    user_id = self._get_effective_user_id(event)
    if result := self.inventory_service.sell_everything_except_locked(user_id):
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 砸锅卖铁失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def sell_by_rarity(self, event: AstrMessageEvent):
    """按稀有度出售鱼"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result("❌ 请指定要出售的稀有度，例如：/出售稀有度 3")
        return
    rarity = args[1]
    if not rarity.isdigit() or int(rarity) < 1 or int(rarity) > 5:
        yield event.plain_result("❌ 稀有度必须是1到5之间的数字，请检查后重试。")
        return
    if result := self.inventory_service.sell_fish_by_rarity(user_id, int(rarity)):
        yield event.plain_result(result["message"])
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def sell_rod(self, event: AstrMessageEvent):
    """出售鱼竿"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result("❌ 请指定要出售的鱼竿 ID，例如：/出售鱼竿 R1A2B")
        return
    token = args[1]
    instance_id = self.inventory_service.resolve_rod_instance_id(user_id, token)
    if instance_id is None:
        yield event.plain_result("❌ 无效的鱼竿ID，请输入短码（如 R2N9C）。")
        return
    if result := self.inventory_service.sell_rod(user_id, int(instance_id)):
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 出售鱼竿失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def sell_all_rods(self, event: AstrMessageEvent):
    """出售用户所有鱼竿"""
    user_id = self._get_effective_user_id(event)
    result = self.inventory_service.sell_all_rods(user_id)
    if result:
        yield event.plain_result(result["message"])
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def sell_accessories(self, event: AstrMessageEvent):
    """出售饰品"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result("❌ 请指定要出售的饰品 ID，例如：/出售饰品 A3C4D")
        return
    token = args[1]
    instance_id = self.inventory_service.resolve_accessory_instance_id(user_id, token)
    if instance_id is None:
        yield event.plain_result("❌ 无效的饰品ID，请输入短码（如 A7K3Q）。")
        return
    result = self.inventory_service.sell_accessory(user_id, int(instance_id))
    if result:
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 出售饰品失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def sell_all_accessories(self, event: AstrMessageEvent):
    """出售用户所有饰品"""
    user_id = self._get_effective_user_id(event)
    result = self.inventory_service.sell_all_accessories(user_id)
    if result:
        yield event.plain_result(result["message"])
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def shop(self, event: AstrMessageEvent):
    """查看商店：/商店 [商店ID]"""
    args = event.message_str.split(" ")
    # /商店 → 列表
    if len(args) == 1:
        result = self.shop_service.get_shops()
        if not result or not result.get("success"):
            yield event.plain_result("❌ 出错啦！请稍后再试。")
            return
        shops = result.get("shops", [])
        if not shops:
            yield event.plain_result("🛒 当前没有开放的商店。")
            return
        msg = "【🛒 商店列表】\n"
        for s in shops:
            stype = s.get("shop_type", "normal")
            type_name = "普通" if stype == "normal" else ("高级" if stype == "premium" else "限时")
            status = "🟢 营业中" if s.get("is_active") else "🔴 已关闭"
            msg += f" - {s.get('name')} (ID: {s.get('shop_id')}) [{type_name}] {status}\n"
            if s.get("description"):
                msg += f"   - {s.get('description')}\n"
        msg += "\n💡 使用「商店 商店ID」查看详情；使用「商店购买 商店ID 商品ID [数量]」购买\n"
        
        # 检查消息长度，如果太长则分多次发送
        if len(msg) > 1500:
            # 分割消息
            lines = msg.split('\n')
            mid_point = len(lines) // 2
            
            first_part = '\n'.join(lines[:mid_point])
            second_part = '\n'.join(lines[mid_point:])
            
            yield event.plain_result(first_part)
            yield event.plain_result(second_part)
        else:
            yield event.plain_result(msg)
        return

    # /商店 <ID> → 详情
    shop_id = args[1]
    if not shop_id.isdigit():
        yield event.plain_result("❌ 商店ID必须是数字")
        return
    detail = self.shop_service.get_shop_details(int(shop_id))
    if not detail.get("success"):
        yield event.plain_result(f"❌ {detail.get('message','查询失败')}")
        return
    shop = detail["shop"]
    items = detail.get("items", [])
    msg = f"【🛒 {shop.get('name')}】(ID: {shop.get('shop_id')})\n"
    if shop.get("description"):
        msg += f"📖 {shop.get('description')}\n"
    if not items:
        msg += "\n📭 当前没有在售商品。"
        yield event.plain_result(msg)
        return
    msg += "\n🛍️ 【在售商品】\n"
    msg += "═" * 50 + "\n"
    for i, e in enumerate(items):
        item = e["item"]
        costs = e["costs"]
        rewards = e.get("rewards", [])
        
        # 获取商品稀有度和emoji
        rarity = 1
        item_emoji = "📦"
        rarity_stars = "⭐"
        
        if rewards:
            # 如果奖励物品超过2个，使用礼包emoji
            if len(rewards) > 2:
                item_emoji = "🎁"
                # 计算平均稀有度
                total_rarity = 0
                for reward in rewards:
                    if reward["reward_type"] == "rod":
                        rod_template = self.item_template_repo.get_rod_by_id(reward.get("reward_item_id"))
                        if rod_template:
                            total_rarity += rod_template.rarity
                    elif reward["reward_type"] == "bait":
                        bait_template = self.item_template_repo.get_bait_by_id(reward.get("reward_item_id"))
                        if bait_template:
                            total_rarity += bait_template.rarity
                    elif reward["reward_type"] == "accessory":
                        accessory_template = self.item_template_repo.get_accessory_by_id(reward.get("reward_item_id"))
                        if accessory_template:
                            total_rarity += accessory_template.rarity
                    elif reward["reward_type"] == "item":
                        item_template = self.item_template_repo.get_by_id(reward.get("reward_item_id"))
                        if item_template:
                            total_rarity += item_template.rarity
                rarity = max(1, total_rarity // len(rewards))  # 取平均稀有度，最少1星
            else:
                 # 单个或两个物品，使用第一个物品的类型和稀有度
                 reward = rewards[0]
                 if reward["reward_type"] == "rod":
                     rod_template = self.item_template_repo.get_rod_by_id(reward.get("reward_item_id"))
                     if rod_template:
                         rarity = rod_template.rarity
                         item_emoji = "🎣"
                 elif reward["reward_type"] == "bait":
                     bait_template = self.item_template_repo.get_bait_by_id(reward.get("reward_item_id"))
                     if bait_template:
                         rarity = bait_template.rarity
                         item_emoji = "🪱"
                 elif reward["reward_type"] == "accessory":
                     accessory_template = self.item_template_repo.get_accessory_by_id(reward.get("reward_item_id"))
                     if accessory_template:
                         rarity = accessory_template.rarity
                         item_emoji = "💍"
                 elif reward["reward_type"] == "item":
                     item_template = self.item_template_repo.get_by_id(reward.get("reward_item_id"))
                     if item_template:
                         rarity = item_template.rarity
                         # 根据道具名称选择合适的emoji
                         item_name = item_template.name.lower()
                         if "沙漏" in item_name or "时运" in item_name:
                             item_emoji = "⏳"
                         elif "令牌" in item_name or "通行证" in item_name:
                             item_emoji = "🎫"
                         elif "护符" in item_name or "神佑" in item_name:
                             item_emoji = "🛡️"
                         elif "钱袋" in item_name:
                             item_emoji = "💰"
                         elif "海图" in item_name or "地图" in item_name:
                             item_emoji = "🗺️"
                         elif "香" in item_name or "驱灵" in item_name:
                             item_emoji = "🕯️"
                         elif "许可证" in item_name or "擦弹" in item_name:
                             item_emoji = "📋"
                         elif "符" in item_name or "符文" in item_name:
                             item_emoji = "🔮"
                         elif "海灵" in item_name or "守护" in item_name:
                             item_emoji = "🌊"
                         elif "斗篷" in item_name or "暗影" in item_name:
                             item_emoji = "🪶"
                         elif "药水" in item_name or "幸运" in item_name:
                             item_emoji = "🧪"
                         elif "声呐" in item_name or "便携" in item_name:
                             item_emoji = "📡"
                         else:
                             item_emoji = "📦"  # 默认道具emoji 
        
        # 根据稀有度设置星星
        if rarity == 1:
            rarity_stars = "⭐"
        elif rarity == 2:
            rarity_stars = "⭐⭐"
        elif rarity == 3:
            rarity_stars = "⭐⭐⭐"
        elif rarity == 4:
            rarity_stars = "⭐⭐⭐⭐"
        elif rarity == 5:
            rarity_stars = "⭐⭐⭐⭐⭐"
        else:
            rarity_stars = "⭐" * min(rarity, 10)
            if rarity > 10:
                rarity_stars += "+"
        
        # 按组ID分组成本
        cost_groups = {}
        for c in costs:
            group_id = c.get("group_id", 1)  # 默认组ID为1
            if group_id not in cost_groups:
                cost_groups[group_id] = []
            cost_groups[group_id].append(c)
        
        # 构建成本字符串
        group_parts = []
        for group_id in sorted(cost_groups.keys()):
            group_costs = cost_groups[group_id]
            group_parts_inner = []
            
            for c in group_costs:
                cost_text = ""
                if c["cost_type"] == "coins":
                    cost_text = f"💰 {c['cost_amount']} 金币"
                elif c["cost_type"] == "premium":
                    cost_text = f"💎 {c['cost_amount']} 高级货币"
                elif c["cost_type"] == "item":
                    # 获取道具名称
                    item_template = self.item_template_repo.get_by_id(c.get("cost_item_id"))
                    item_name = item_template.name if item_template else f"道具#{c.get('cost_item_id')}"
                    cost_text = f"🎁 {item_name} x{c['cost_amount']}"
                elif c["cost_type"] == "fish":
                    # 获取鱼类名称
                    fish_template = self.item_template_repo.get_fish_by_id(c.get("cost_item_id"))
                    fish_name = fish_template.name if fish_template else f"鱼类#{c.get('cost_item_id')}"
                    cost_text = f"🐟 {fish_name} x{c['cost_amount']}"
                elif c["cost_type"] == "rod":
                    # 获取鱼竿名称
                    rod_template = self.item_template_repo.get_rod_by_id(c.get("cost_item_id"))
                    rod_name = rod_template.name if rod_template else f"鱼竿#{c.get('cost_item_id')}"
                    cost_text = f"🎣 {rod_name} x{c['cost_amount']}"
                elif c["cost_type"] == "accessory":
                    # 获取饰品名称
                    accessory_template = self.item_template_repo.get_accessory_by_id(c.get("cost_item_id"))
                    accessory_name = accessory_template.name if accessory_template else f"饰品#{c.get('cost_item_id')}"
                    cost_text = f"💍 {accessory_name} x{c['cost_amount']}"
                
                group_parts_inner.append(cost_text)
            
            # 根据组内关系连接
            if len(group_parts_inner) == 1:
                group_parts.append(group_parts_inner[0])
            else:
                # 检查组内关系
                relation = group_costs[0].get("cost_relation", "and")
                if relation == "or":
                    group_parts.append(f"({' OR '.join(group_parts_inner)})")
                else:  # and
                    group_parts.append(" + ".join(group_parts_inner))
        
        # 连接不同组（组间是AND关系）
        cost_str = " + ".join(group_parts) if group_parts else "免费"
        stock_str = "无限" if item.get("stock_total") is None else f"{item.get('stock_sold',0)}/{item.get('stock_total')}"
        
        # 获取限购信息
        per_user_limit = item.get("per_user_limit")
        per_user_daily_limit = item.get("per_user_daily_limit")
        
        # 获取限时信息
        start_time = item.get("start_time")
        end_time = item.get("end_time")
        
        # 美化输出格式
        msg += f"┌─ {item_emoji} {item['name']} {rarity_stars}\n"
        msg += f"├─ 价格: {cost_str}\n"
        msg += f"├─ 库存: {stock_str}\n"
        msg += f"├─ ID: {item['item_id']}\n"
        
        # 添加限购信息
        limit_info = []
        if per_user_limit is not None:
            limit_info.append(f"每人限购: {per_user_limit}")
        if per_user_daily_limit is not None:
            limit_info.append(f"每日限购: {per_user_daily_limit}")
        
        if limit_info:
            msg += f"├─ 限购: {' | '.join(limit_info)}\n"
        
        # 添加限时信息
        time_info = []
        current_time = None
        from datetime import datetime
        try:
            current_time = datetime.now()
        except:
            pass
        
        if start_time:
            if isinstance(start_time, str):
                try:
                    start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                except:
                    pass
            if isinstance(start_time, datetime):
                if current_time and current_time < start_time:
                    time_info.append(f"未开始: {start_time.strftime('%m-%d %H:%M')}")
                else:
                    time_info.append(f"开始: {start_time.strftime('%m-%d %H:%M')}")
        
        if end_time:
            if isinstance(end_time, str):
                try:
                    end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                except:
                    pass
            if isinstance(end_time, datetime):
                if current_time and current_time > end_time:
                    time_info.append(f"已结束: {end_time.strftime('%m-%d %H:%M')}")
                else:
                    time_info.append(f"结束: {end_time.strftime('%m-%d %H:%M')}")
        
        if time_info:
            msg += f"├─ 限时: {' | '.join(time_info)}\n"
        
        # 如果包含多个物品（≥2），显示礼包包含的物品
        if len(rewards) >= 2:
            msg += "├─ 包含物品:\n"
            for reward in rewards:
                item_name = "未知物品"
                item_emoji = "📦"
                
                if reward["reward_type"] == "rod":
                    rod_template = self.item_template_repo.get_rod_by_id(reward.get("reward_item_id"))
                    if rod_template:
                        item_name = rod_template.name
                        item_emoji = "🎣"
                elif reward["reward_type"] == "bait":
                    bait_template = self.item_template_repo.get_bait_by_id(reward.get("reward_item_id"))
                    if bait_template:
                        item_name = bait_template.name
                        item_emoji = "🪱"
                elif reward["reward_type"] == "accessory":
                    accessory_template = self.item_template_repo.get_accessory_by_id(reward.get("reward_item_id"))
                    if accessory_template:
                        item_name = accessory_template.name
                        item_emoji = "💍"
                elif reward["reward_type"] == "item":
                    item_template = self.item_template_repo.get_by_id(reward.get("reward_item_id"))
                    if item_template:
                        item_name = item_template.name
                        item_emoji = "🎁"
                elif reward["reward_type"] == "fish":
                    fish_template = self.item_template_repo.get_fish_by_id(reward.get("reward_item_id"))
                    if fish_template:
                        item_name = fish_template.name
                        item_emoji = "🐟"
                elif reward["reward_type"] == "coins":
                    item_name = "金币"
                    item_emoji = "💰"
                
                msg += f"│   • {item_emoji} {item_name}"
                if reward.get("reward_quantity", 1) > 1:
                    msg += f" x{reward['reward_quantity']}"
                msg += "\n"
        
        if item.get("description"):
            msg += f"└─ {item['description']}\n"
        else:
            msg += "└─\n"
        
        # 添加商品之间的分隔符（除了最后一个商品）
        if i < len(items) - 1:
            msg += "─" * 30 + "\n"
    msg += "═" * 50 + "\n"
    msg += "💡 购买：商店购买 商店ID 商品ID [数量]\n"
    msg += "示例：商店购买 1 2 5"
    yield event.plain_result(msg)

async def buy_in_shop(self, event: AstrMessageEvent):
    """按商店池购买：/商店购买 <商店ID> <商品ID> [数量]"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 3:
        yield event.plain_result("❌ 用法：商店购买 商店ID 商品ID [数量]")
        return
    shop_id, item_id = args[1], args[2]
    if not shop_id.isdigit() or not item_id.isdigit():
        yield event.plain_result("❌ 商店ID与商品ID必须是数字")
        return
    qty = 1
    if len(args) >= 4:
        if not args[3].isdigit() or int(args[3]) <= 0:
            yield event.plain_result("❌ 数量必须是正整数")
            return
        qty = int(args[3])
    result = self.shop_service.purchase_item(user_id, int(item_id), qty)
    if result.get("success"):
        yield event.plain_result(result["message"])
    else:
        error_message = result.get('message', '购买失败')
        # 检查错误消息是否已经包含❌符号，避免重复添加
        if error_message.startswith("❌"):
            yield event.plain_result(error_message)
        else:
            yield event.plain_result(f"❌ {error_message}")


async def market(self, event: AstrMessageEvent):
    """查看市场"""
    result = self.market_service.get_market_listings()
    if result["success"]:
        # 收集所有商品并限制总数
        all_items = []
        
        rods = result["rods"]
        accessories = result["accessories"]
        items = result["items"]
        fish = result.get("fish", [])

        if rods:
            for rod in rods[:15]:  # 限制鱼竿最多15件
                # 生成短码显示
                display_code = _get_display_code_for_market_item(rod)
                # 检查是否为匿名商品
                is_anonymous = rod.is_anonymous
                seller_display = "🎭 匿名卖家" if is_anonymous else rod.seller_nickname
                all_items.append({
                    "type": "鱼竿",
                    "emoji": "🎣",
                    "name": f"{rod.item_name} 精{rod.refine_level}",
                    "id": rod.market_id,
                    "display_code": display_code,
                    "price": rod.price,
                    "seller": seller_display,
                    "is_anonymous": is_anonymous
                })
        
        if accessories:
            for accessory in accessories[:15]:  # 限制饰品最多15件
                # 生成短码显示
                display_code = _get_display_code_for_market_item(accessory)
                # 检查是否为匿名商品
                is_anonymous = accessory.is_anonymous
                seller_display = "🎭 匿名卖家" if is_anonymous else accessory.seller_nickname
                all_items.append({
                    "type": "饰品",
                    "emoji": "💍",
                    "name": f"{accessory.item_name} 精{accessory.refine_level}",
                    "id": accessory.market_id,
                    "display_code": display_code,
                    "price": accessory.price,
                    "seller": seller_display,
                    "is_anonymous": is_anonymous
                })
        
        if items:
            for item in items[:15]:  # 限制道具最多15件
                # 道具没有实例ID，使用市场ID
                is_anonymous = item.is_anonymous
                seller_display = "🎭 匿名卖家" if is_anonymous else item.seller_nickname
                all_items.append({
                    "type": "道具",
                    "emoji": "🎁",
                    "name": item.item_name,
                    "id": item.market_id,
                    "display_code": f"M{item.market_id}",  # 道具市场使用市场ID
                    "price": item.price,
                    "seller": seller_display,
                    "is_anonymous": is_anonymous
                })

        if fish:
            for fish_item in fish[:15]:  # 限制鱼类最多15件
                # 生成鱼类短码显示（市场ID）
                is_anonymous = fish_item.is_anonymous
                seller_display = "🎭 匿名卖家" if is_anonymous else fish_item.seller_nickname
                all_items.append({
                    "type": "鱼类",
                    "emoji": "🐟",
                    "name": fish_item.item_name,
                    "id": fish_item.market_id,
                    "display_code": f"M{fish_item.market_id}",  # 鱼类市场使用市场ID
                    "price": fish_item.price,
                    "seller": seller_display,
                    "is_anonymous": is_anonymous
                })
        
        if not all_items:
            yield event.plain_result("🛒 市场中没有商品可供购买。")
            return

    # Helper function to format a list of items
    def format_item_list(item_list, item_type, emoji):
        message = ""
        for item in item_list:
            display_code = _get_display_code_for_market_item(item)
            is_anonymous = getattr(item, 'is_anonymous', False)
            seller_display = "🎭 匿名卖家" if is_anonymous else item.seller_nickname
            refine_level = getattr(item, 'refine_level', 1)
            refine_level_str = f" 精{refine_level}" if refine_level > 1 else ""
            
            message += f"【{emoji} {item_type}】：\n"
            message += f" - {item.item_name}{refine_level_str} (ID: {display_code}) - 价格: {item.price} 金币\n"
            message += f" - 售卖人： {seller_display}\n\n"
        return message

    # Process each category
    page_size = 15

    # Rods
    if rods:
        if len(rods) > page_size:
            total_pages = (len(rods) + page_size - 1) // page_size
            for page in range(total_pages):
                start_idx = page * page_size
                end_idx = min(start_idx + page_size, len(rods))
                page_items = rods[start_idx:end_idx]
                
                message = f"【🎣 市场 - 鱼竿】第 {page + 1}/{total_pages} 页\n\n"
                message += format_item_list(page_items, "鱼竿", "🎣")
                yield event.plain_result(message)
        else:
            message = "【🎣 市场 - 鱼竿】\n\n"
            message += format_item_list(rods, "鱼竿", "🎣")
            yield event.plain_result(message)

    # Accessories
    if accessories:
        if len(accessories) > page_size:
            total_pages = (len(accessories) + page_size - 1) // page_size
            for page in range(total_pages):
                start_idx = page * page_size
                end_idx = min(start_idx + page_size, len(accessories))
                page_items = accessories[start_idx:end_idx]
                
                message = f"【💍 市场 - 饰品】第 {page + 1}/{total_pages} 页\n\n"
                message += format_item_list(page_items, "饰品", "💍")
                yield event.plain_result(message)
        else:
            message = "【💍 市场 - 饰品】\n\n"
            message += format_item_list(accessories, "饰品", "💍")
            yield event.plain_result(message)

    # Items
    if items:
        if len(items) > page_size:
            total_pages = (len(items) + page_size - 1) // page_size
            for page in range(total_pages):
                start_idx = page * page_size
                end_idx = min(start_idx + page_size, len(items))
                page_items = items[start_idx:end_idx]
                
                message = f"【🎁 市场 - 道具】第 {page + 1}/{total_pages} 页\n\n"
                message += format_item_list(page_items, "道具", "🎁")
                yield event.plain_result(message)
        else:
            message = "【🎁 市场 - 道具】\n\n"
            message += format_item_list(items, "道具", "🎁")
            yield event.plain_result(message)

async def list_rod(self, event: AstrMessageEvent):
    """上架鱼竿到市场"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 3:
        yield event.plain_result("❌ 请指定要上架的鱼竿 ID和价格，例如：/上架鱼竿 R1A2B 1000")
        return
    token = args[1]
    instance_id = self.inventory_service.resolve_rod_instance_id(user_id, token)
    if instance_id is None:
        yield event.plain_result("❌ 无效的鱼竿ID，请输入短码（如 R2N9C）。")
        return
    price = args[2]
    if not price.isdigit() or int(price) <= 0:
        yield event.plain_result("❌ 上架价格必须是正整数，请检查后重试。")
        return
    result = self.market_service.put_item_on_sale(user_id, "rod", int(instance_id), int(price))
    if result:
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 上架鱼竿失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def list_accessories(self, event: AstrMessageEvent):
    """上架饰品到市场"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 3:
        yield event.plain_result("❌ 请指定要上架的饰品 ID和价格，例如：/上架饰品 A3C4D 1000")
        return
    token = args[1]
    instance_id = self.inventory_service.resolve_accessory_instance_id(user_id, token)
    if instance_id is None:
        yield event.plain_result("❌ 无效的饰品ID，请输入短码（如 A7K3Q）。")
        return
    price = args[2]
    if not price.isdigit() or int(price) <= 0:
        yield event.plain_result("❌ 上架价格必须是正整数，请检查后重试。")
        return
    result = self.market_service.put_item_on_sale(user_id, "accessory", int(instance_id), int(price))
    if result:
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 上架饰品失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def list_item(self, event: AstrMessageEvent):
    """上架道具到市场"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 3:
        yield event.plain_result("❌ 请指定要上架的道具 ID和价格，例如：/上架道具 1 1000")
        return
    item_id = args[1]
    if not item_id.isdigit():
        yield event.plain_result("❌ 道具 ID 必须是数字，请检查后重试。")
        return
    price = args[2]
    if not price.isdigit() or int(price) <= 0:
        yield event.plain_result("❌ 上架价格必须是正整数，请检查后重试。")
        return
    result = self.market_service.put_item_on_sale(user_id, "item", int(item_id), int(price))
    if result:
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 上架道具失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def list_any(self, event: AstrMessageEvent, is_anonymous: bool = False):
    """统一上架命令：/上架 <ID> <价格> [匿名]
    - Rxxxx: 鱼竿实例
    - Axxxx: 饰品实例
    - Dxxxx: 道具模板
    - Fxxxx: 鱼类模板
    """
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 3:
        yield event.plain_result("❌ 用法：/上架 ID 价格 [匿名]\n示例：/上架 R2N9C 1000、/上架 A7K3Q 2000 匿名")
        return
    token = args[1].strip().upper()
    price = args[2]
    
    # 检查是否有匿名参数
    if len(args) > 3 and args[3].strip().lower() in ['匿名', 'anonymous']:
        is_anonymous = True
    
    if not price.isdigit() or int(price) <= 0:
        yield event.plain_result("❌ 上架价格必须是正整数，请检查后重试。")
        return
    price = int(price)

    # 检查是否为数字ID（旧格式）
    if token.isdigit():
        yield event.plain_result("❌ 请使用正确的物品ID！\n\n📝 短码格式：\n• R开头：鱼竿（如 R2N9C）\n• A开头：饰品（如 A7K3Q）\n• D开头：道具（如 D1）\n• F开头：鱼类（如 F3）\n\n💡 提示：使用 /背包 查看您的物品短码")
        return

    def _from_base36(s: str) -> int:
        s = (s or "").strip().upper()
        return int(s, 36)

    # 判别类型并解析
    if token.startswith('R'):
        instance_id = self.inventory_service.resolve_rod_instance_id(user_id, token)
        if instance_id is None:
            yield event.plain_result("❌ 无效的鱼竿ID，请检查后重试。")
            return
        result = self.market_service.put_item_on_sale(user_id, "rod", int(instance_id), price, is_anonymous=is_anonymous)
    elif token.startswith('A'):
        instance_id = self.inventory_service.resolve_accessory_instance_id(user_id, token)
        if instance_id is None:
            yield event.plain_result("❌ 无效的饰品ID，请检查后重试。")
            return
        result = self.market_service.put_item_on_sale(user_id, "accessory", int(instance_id), price, is_anonymous=is_anonymous)
    elif token.startswith('D'):
        try:
            item_id = int(token[1:])
        except Exception:
            yield event.plain_result("❌ 无效的道具ID，请检查后重试。")
            return
        result = self.market_service.put_item_on_sale(user_id, "item", int(item_id), price, is_anonymous=is_anonymous)
    elif token.startswith('F'):
        try:
            fish_id = int(token[1:])
        except Exception:
            yield event.plain_result("❌ 无效的鱼类ID，请检查后重试。")
            return
        result = self.market_service.put_item_on_sale(user_id, "fish", int(fish_id), price, is_anonymous=is_anonymous)
    else:
        yield event.plain_result("❌ 无效ID，请使用以 R/A/D/F 开头的短码")
        return

    if result:
        if result.get("success"):
            message = result["message"]
            if is_anonymous:
                message = f"🎭 {message} (匿名上架)"
            yield event.plain_result(message)
        else:
            yield event.plain_result(f"❌ 上架失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def anonymous_list_any(self, event: AstrMessageEvent):
    """匿名上架命令：调用统一上架命令并设置匿名参数"""
    async for r in list_any(event, is_anonymous=True):
        yield r

async def anonymous_list_rod(self, event: AstrMessageEvent):
    """匿名上架鱼竿到市场"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 3:
        yield event.plain_result("❌ 请指定要上架的鱼竿 ID和价格，例如：/匿名上架鱼竿 R1A2B 1000")
        return
    token = args[1]
    instance_id = self.inventory_service.resolve_rod_instance_id(user_id, token)
    if instance_id is None:
        yield event.plain_result("❌ 无效的鱼竿ID，请输入短码（如 R2N9C）。")
        return
    price = args[2]
    if not price.isdigit() or int(price) <= 0:
        yield event.plain_result("❌ 上架价格必须是正整数，请检查后重试。")
        return
    result = self.market_service.put_item_on_sale(user_id, "rod", int(instance_id), int(price), is_anonymous=True)
    if result:
        if result["success"]:
            yield event.plain_result(f"🎭 {result['message']} (匿名上架)")
        else:
            yield event.plain_result(f"❌ 匿名上架鱼竿失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def anonymous_list_accessories(self, event: AstrMessageEvent):
    """匿名上架饰品到市场"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 3:
        yield event.plain_result("❌ 请指定要上架的饰品 ID和价格，例如：/匿名上架饰品 A3C4D 1000")
        return
    token = args[1]
    instance_id = self.inventory_service.resolve_accessory_instance_id(user_id, token)
    if instance_id is None:
        yield event.plain_result("❌ 无效的饰品ID，请输入数字或短码（如 A7K3Q）。")
        return
    price = args[2]
    if not price.isdigit() or int(price) <= 0:
        yield event.plain_result("❌ 上架价格必须是正整数，请检查后重试。")
        return
    result = self.market_service.put_item_on_sale(user_id, "accessory", int(instance_id), int(price), is_anonymous=True)
    if result:
        if result["success"]:
            yield event.plain_result(f"🎭 {result['message']} (匿名上架)")
        else:
            yield event.plain_result(f"❌ 匿名上架饰品失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def anonymous_list_item(self, event: AstrMessageEvent):
    """匿名上架道具到市场"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 3:
        yield event.plain_result("❌ 请指定要上架的道具 ID和价格，例如：/匿名上架道具 1 1000")
        return
    item_id = args[1]
    if not item_id.isdigit():
        yield event.plain_result("❌ 道具 ID 必须是数字，请检查后重试。")
        return
    price = args[2]
    if not price.isdigit() or int(price) <= 0:
        yield event.plain_result("❌ 上架价格必须是正整数，请检查后重试。")
        return
    result = self.market_service.put_item_on_sale(user_id, "item", int(item_id), int(price), is_anonymous=True)
    if result:
        if result["success"]:
            yield event.plain_result(f"🎭 {result['message']} (匿名上架)")
        else:
            yield event.plain_result(f"❌ 匿名上架道具失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def buy_item(self, event: AstrMessageEvent):
    """购买市场上的物品"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result("❌ 请指定要购买的商品ID，例如：/购买 R1A2B\n💡 使用「市场」命令查看商品列表")
        return
    
    try:
        market_id = _parse_market_code(args[1], self.market_service)
    except ValueError as e:
        yield event.plain_result(f"❌ {e}\n💡 使用「市场」命令查看商品列表")
        return
    
    result = self.market_service.buy_market_item(user_id, market_id)
    if result:
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 购买失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def my_listings(self, event: AstrMessageEvent):
    """查看我在市场上架的商品"""
    user_id = self._get_effective_user_id(event)
    result = self.market_service.get_user_listings(user_id)
    if result["success"]:
        listings = result["listings"]
        if not listings:
            yield event.plain_result("📦 您还没有在市场上架任何商品。")
            return
        
        total_count = len(listings)
        
        # 限制最多显示15件商品，超过则分多次发送
        display_count = min(total_count, 15)
        listings_to_show = listings[:display_count]
        
        # 分页显示，每页最多8件商品
        page_size = 8
        total_pages = (display_count + page_size - 1) // page_size
        
        for page in range(total_pages):
            start_idx = page * page_size
            end_idx = min(start_idx + page_size, display_count)
            page_listings = listings_to_show[start_idx:end_idx]
            
            message = f"【🛒 我的上架商品】第 {page + 1}/{total_pages} 页 (共 {total_count} 件，显示前 {display_count} 件)\n\n"
            
            for listing in page_listings:
                message += f"🆔 ID: {listing.market_id}\n"
                message += f"📦 {listing.item_name}"
                if listing.refine_level > 1:
                    message += f" 精{listing.refine_level}"
                message += f"\n💰 价格: {listing.price} 金币\n"
                message += f"📅 上架时间: {listing.listed_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            
            message += "💡 使用「下架 ID」命令下架指定商品"
            
            yield event.plain_result(message)
    else:
        yield event.plain_result(f"❌ 查询失败：{result['message']}")

async def delist_item(self, event: AstrMessageEvent):
    """下架市场上的商品"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result("❌ 请指定要下架的商品 ID或ID，例如：/下架 M12 或 /下架 R2N9C\n💡 使用「我的上架」命令查看您的商品列表")
        return
    code = args[1]
    # 支持 Mxxxx（市场）、Rxxxx/Axxxx（通过实例查当前用户上架）或纯数字
    if code.isdigit():
        market_id = int(code)
    else:
        try:
            market_id = _parse_market_code(code, self.market_service)
        except ValueError as e:
            yield event.plain_result(f"❌ {e}\n💡 使用「我的上架」命令查看您的商品列表")
            return
    result = self.market_service.delist_item(user_id, market_id)
    if result:
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 下架失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")


def _to_base36(n: int) -> str:
    """将数字转换为base36字符串"""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return "0"
    digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    out = []
    while n:
        n, rem = divmod(n, 36)
        out.append(digits[rem])
    return "".join(reversed(out))


def _get_display_code_for_market_item(item) -> str:
    """为市场商品生成显示ID"""
    item_type = item.item_type
    item_instance_id = item.item_instance_id
    
    if item_type == "rod" and item_instance_id:
        return f"R{_to_base36(item_instance_id)}"
    elif item_type == "accessory" and item_instance_id:
        return f"A{_to_base36(item_instance_id)}"
    elif item_type == "item":
        # 道具在市场中使用市场ID（因为没有实例ID）
        return f"M{item.market_id}"
    elif item_type == "fish":
        # 鱼类在市场中使用市场ID（因为没有实例ID）
        return f"M{item.market_id}"
    else:
        # 其他情况，使用市场ID
        return f"M{item.market_id}"


def _from_base36(s: str) -> int:
    """将base36字符串转换为数字"""
    if not s:
        raise ValueError("Empty string")
    s = s.upper()
    result = 0
    for char in s:
        if char.isdigit():
            result = result * 36 + int(char)
        elif 'A' <= char <= 'Z':
            result = result * 36 + ord(char) - ord('A') + 10
        else:
            raise ValueError(f"Invalid character: {char}")
    return result


def _parse_market_code(code: str, market_service=None) -> int:
    """解析市场ID，返回市场ID"""
    code = code.strip().upper()
    
    if code.startswith('M') and len(code) > 1:
        # M开头的ID，后面是市场ID
        try:
            return int(code[1:])
        except ValueError:
            raise ValueError(f"无效的市场ID: {code}")
    elif code.startswith('R') and len(code) > 1:
        # R开头的ID，需要根据实例ID查找市场ID
        try:
            instance_id = _from_base36(code[1:])
            if market_service:
                market_id = market_service.get_market_id_by_instance_id("rod", instance_id)
                if market_id is not None:
                    return market_id
                else:
                    raise ValueError(f"未找到鱼竿ID {code} 对应的市场商品")
            else:
                raise ValueError("无法解析鱼竿ID，请稍后重试")
        except ValueError as e:
            raise ValueError(f"无效的鱼竿ID: {code}")
    elif code.startswith('A') and len(code) > 1:
        # A开头的ID，需要根据实例ID查找市场ID
        try:
            instance_id = _from_base36(code[1:])
            if market_service:
                market_id = market_service.get_market_id_by_instance_id("accessory", instance_id)
                if market_id is not None:
                    return market_id
                else:
                    raise ValueError(f"未找到饰品ID {code} 对应的市场商品")
            else:
                raise ValueError("无法解析饰品ID，请稍后重试")
        except ValueError as e:
            raise ValueError(f"无效的饰品ID: {code}")
    else:
        raise ValueError(f"无效的市场ID: {code}，请使用短码（如 R1A2B、A3C4D、M123）")
