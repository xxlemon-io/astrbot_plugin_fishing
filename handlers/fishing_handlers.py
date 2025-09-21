from astrbot.api.event import filter, AstrMessageEvent
from ..core.utils import get_now
from ..utils import safe_datetime_handler, to_percentage

def register_fishing_handlers(plugin):
    @filter.command("钓鱼")
    async def fish(event: AstrMessageEvent):
        """钓鱼"""
        user_id = plugin._get_effective_user_id(event)
        user = plugin.user_repo.get_by_id(user_id)
        if not user:
            yield event.plain_result("❌ 您还没有注册，请先使用 /注册 命令注册。")
            return
        # 检查用户钓鱼CD
        lst_time = user.last_fishing_time
        # 检查是否装备了海洋之心饰品
        info = plugin.user_service.get_user_current_accessory(user_id)
        if info["success"] is False:
            yield event.plain_result(f"❌ 获取用户饰品信息失败：{info['message']}")
            return
        equipped_accessory = info.get("accessory")
        cooldown_seconds = plugin.game_config["fishing"]["cooldown_seconds"]
        if equipped_accessory and equipped_accessory.get("name") == "海洋之心":
            # 如果装备了海洋之心，CD时间减半
            cooldown_seconds = plugin.game_config["fishing"]["cooldown_seconds"] / 2
            # logger.info(f"用户 {user_id} 装备了海洋之心，钓鱼CD时间减半。")
        # 修复时区问题
        now = get_now()
        if lst_time and lst_time.tzinfo is None and now.tzinfo is not None:
            # 如果 lst_time 没有时区而 now 有时区，移除 now 的时区信息
            now = now.replace(tzinfo=None)
        elif lst_time and lst_time.tzinfo is not None and now.tzinfo is None:
            # 如果 lst_time 有时区而 now 没有时区，将 now 转换为有时区
            now = now.replace(tzinfo=lst_time.tzinfo)
        if lst_time and (now - lst_time).total_seconds() < cooldown_seconds:
            wait_time = cooldown_seconds - (now - lst_time).total_seconds()
            yield event.plain_result(f"⏳ 您还需要等待 {int(wait_time)} 秒才能再次钓鱼。")
            return
        result = plugin.fishing_service.go_fish(user_id)
        if result:
            if result["success"]:
                # 获取当前区域的钓鱼消耗
                zone = plugin.inventory_repo.get_zone_by_id(user.fishing_zone_id)
                fishing_cost = zone.fishing_cost if zone else 10
                
                message = f"🎣 恭喜你钓到了：{result['fish']['name']}\n✨品质：{'★' * result['fish']['rarity']} \n⚖️重量：{result['fish']['weight']} 克\n💰价值：{result['fish']['value']} 金币\n💸消耗：{fishing_cost} 金币/次"
                
                # 添加装备损坏消息
                if "equipment_broken_messages" in result:
                    for broken_msg in result["equipment_broken_messages"]:
                        message += f"\n{broken_msg}"
                
                yield event.plain_result(message)
            else:
                # 即使钓鱼失败，也显示消耗的金币
                zone = plugin.inventory_repo.get_zone_by_id(user.fishing_zone_id)
                fishing_cost = zone.fishing_cost if zone else 10
                message = f"{result['message']}\n💸消耗：{fishing_cost} 金币/次"
                yield event.plain_result(message)
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("自动钓鱼")
    async def auto_fish(event: AstrMessageEvent):
        """自动钓鱼"""
        user_id = plugin._get_effective_user_id(event)
        result = plugin.fishing_service.toggle_auto_fishing(user_id)
        yield event.plain_result(result["message"])

    @filter.command("钓鱼区域", alias={"区域"})
    async def fishing_area(event: AstrMessageEvent):
        """查看当前钓鱼区域"""
        user_id = plugin._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            result = plugin.fishing_service.get_user_fishing_zones(user_id)
            if result:
                if result["success"]:
                    zones = result.get("zones", [])
                    message = f"【🌊 钓鱼区域】\n"
                    for zone in zones:
                        # 区域状态标识
                        status_icons = []
                        if zone['whether_in_use']:
                            status_icons.append("✅")
                        if not zone['is_active']:
                            status_icons.append("🚫")
                        if zone.get('requires_pass'):
                            status_icons.append("🔑")
                        
                        status_text = " ".join(status_icons) if status_icons else ""
                        
                        message += f"区域名称: {zone['name']} (ID: {zone['zone_id']}) {status_text}\n"
                        message += f"描述: {zone['description']}\n"
                        message += f"💰 钓鱼消耗: {zone.get('fishing_cost', 10)} 金币/次\n"
                        
                        if zone.get('requires_pass'):
                            required_item_name = zone.get('required_item_name', '通行证')
                            message += f"🔑 需要 {required_item_name} 才能进入\n"
                        
                        # 显示限时信息（只有当有具体时间限制时才显示）
                        if zone.get('available_from') or zone.get('available_until'):
                            message += "⏰ 开放时间: "
                            if zone.get('available_from') and zone.get('available_until'):
                                # 有开始和结束时间
                                from_time = zone['available_from'].strftime('%Y-%m-%d %H:%M')
                                until_time = zone['available_until'].strftime('%Y-%m-%d %H:%M')
                                message += f"{from_time} 至 {until_time}\n"
                            elif zone.get('available_from'):
                                # 只有开始时间
                                from_time = zone['available_from'].strftime('%Y-%m-%d %H:%M')
                                message += f"{from_time} 开始\n"
                            elif zone.get('available_until'):
                                # 只有结束时间
                                until_time = zone['available_until'].strftime('%Y-%m-%d %H:%M')
                                message += f"至 {until_time} 结束\n"
                        
                        # 显示稀有鱼余量（4星及以上计入配额），对所有区域生效
                        remaining_rare = max(0, zone['daily_rare_fish_quota'] - zone['rare_fish_caught_today'])
                        if zone.get('daily_rare_fish_quota', 0) > 0:
                            message += f"剩余稀有鱼类数量: {remaining_rare}\n"
                        message += "\n"
                    
                    message += "使用「/钓鱼区域 ID」命令切换钓鱼区域。\n"
                    yield event.plain_result(message)
                else:
                    yield event.plain_result(f"❌ 查看钓鱼区域失败：{result['message']}")
            else:
                yield event.plain_result("❌ 出错啦！请稍后再试。")
            return
        zone_id = args[1]
        if not zone_id.isdigit():
            yield event.plain_result("❌ 钓鱼区域 ID 必须是数字，请检查后重试。")
            return
        zone_id = int(zone_id)
        
        # 动态获取所有有效的区域ID
        all_zones = plugin.fishing_zone_service.get_all_zones()
        valid_zone_ids = [zone['id'] for zone in all_zones]
        
        if zone_id not in valid_zone_ids:
            yield event.plain_result(f"❌ 无效的钓鱼区域 ID。有效ID为: {', '.join(map(str, valid_zone_ids))}")
            yield event.plain_result("💡 请使用「/钓鱼区域 <ID>」命令指定区域ID")
            return
        
        # 切换用户的钓鱼区域
        result = plugin.fishing_service.set_user_fishing_zone(user_id, zone_id)
        yield event.plain_result(result["message"] if result else "❌ 出错啦！请稍后再试。")

    @filter.command("鱼类图鉴")
    async def fish_pokedex(event: AstrMessageEvent):
        """查看鱼类图鉴"""
        user_id = plugin._get_effective_user_id(event)
        result = plugin.fishing_service.get_user_pokedex(user_id)

        if result:
            if result["success"]:
                pokedex = result.get("pokedex", [])
                if not pokedex:
                    yield event.plain_result("❌ 您还没有捕捉到任何鱼类，快去钓鱼吧！")
                    return

                message = "【🐟 🌊 鱼类图鉴 📖 🎣】\n"
                message += f"🏆 解锁进度：{to_percentage(result['unlocked_percentage'])}\n"
                message += f"📊 收集情况：{result['unlocked_fish_count']} / {result['total_fish_count']} 种\n"

                for fish in pokedex:
                    rarity = fish["rarity"]

                    message += f" - {fish['name']} ({'✨' * rarity})\n"
                    message += f"💎 价值：{fish['value']} 金币\n"
                    message += f"🕰️ 首次捕获：{safe_datetime_handler(fish['first_caught_time'])}\n"
                    message += f"📜 描述：{fish['description']}\n"

                if len(message) <= 500:
                    yield event.plain_result(message)
                    return

                text_chunk_size = 1000  # 每个Plain文本块的最大字数
                node_chunk_size = 4  # 每个Node中最多包含的Plain文本块数量
                text_chunks = [message[i:i + text_chunk_size] for i in
                               range(0, len(message), text_chunk_size)]

                if not text_chunks:
                    yield event.plain_result("❌ 内容为空，无法发送。")
                    return

                grouped_chunks = [text_chunks[i:i + node_chunk_size] for i in
                                  range(0, len(text_chunks), node_chunk_size)]

                from astrbot.api.message_components import Node, Plain
                nodes_to_send = []
                for i, group in enumerate(grouped_chunks):
                    plain_components = [Plain(text=chunk) for chunk in group]

                    node = Node(
                        uin=event.get_self_id(),
                        name=f"鱼类图鉴 - 第 {i + 1} 页",
                        content=plain_components
                    )
                    nodes_to_send.append(node)

                try:
                    yield event.chain_result(nodes_to_send)
                except Exception as e:
                    yield event.plain_result(f"❌ 发送转发消息失败：{e}")

            else:
                yield event.plain_result(f"❌ 查看鱼类图鉴失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    plugin.context.add_handler(fish)
    plugin.context.add_handler(auto_fish)
    plugin.context.add_handler(fishing_area)
    plugin.context.add_handler(fish_pokedex)
