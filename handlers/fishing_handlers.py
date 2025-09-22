from astrbot.api.event import filter, AstrMessageEvent
from ..core.utils import get_now
from ..utils import safe_datetime_handler, to_percentage


def _normalize_now_for(lst_time):
    """根据 lst_time 的时区信息，规范化当前时间的 tzinfo。"""
    now = get_now()
    if lst_time and lst_time.tzinfo is None and now.tzinfo is not None:
        return now.replace(tzinfo=None)
    if lst_time and lst_time.tzinfo is not None and now.tzinfo is None:
        return now.replace(tzinfo=lst_time.tzinfo)
    return now


def _compute_cooldown_seconds(base_seconds, equipped_accessory):
    """根据是否装备海洋之心动态计算冷却时间。"""
    if equipped_accessory and equipped_accessory.get("name") == "海洋之心":
        return base_seconds / 2
    return base_seconds


def _get_fishing_cost(self, user):
    zone = self.inventory_repo.get_zone_by_id(user.fishing_zone_id)
    return zone.fishing_cost if zone else 10


def _build_fish_message(result, fishing_cost):
    if result["success"]:
        message = (
            f"🎣 恭喜你钓到了：{result['fish']['name']}\n"
            f"✨品质：{'★' * result['fish']['rarity']} \n"
            f"⚖️重量：{result['fish']['weight']} 克\n"
            f"💰价值：{result['fish']['value']} 金币\n"
            f"💸消耗：{fishing_cost} 金币/次"
        )
        if "equipment_broken_messages" in result:
            for broken_msg in result["equipment_broken_messages"]:
                message += f"\n{broken_msg}"
        return message
    return f"{result['message']}\n💸消耗：{fishing_cost} 金币/次"

async def fish(self, event: AstrMessageEvent):
    """钓鱼"""
    user_id = self._get_effective_user_id(event)
    user = self.user_repo.get_by_id(user_id)
    if not user:
        yield event.plain_result("❌ 您还没有注册，请先使用 /注册 命令注册。")
        return
    # 检查用户钓鱼CD
    lst_time = user.last_fishing_time
    info = self.user_service.get_user_current_accessory(user_id)
    if info["success"] is False:
        yield event.plain_result(f"❌ 获取用户饰品信息失败：{info['message']}")
        return
    equipped_accessory = info.get("accessory")
    base_cooldown = self.game_config["fishing"]["cooldown_seconds"]
    cooldown_seconds = _compute_cooldown_seconds(base_cooldown, equipped_accessory)
    # 修复时区问题
    now = _normalize_now_for(lst_time)
    if lst_time and (now - lst_time).total_seconds() < cooldown_seconds:
        wait_time = cooldown_seconds - (now - lst_time).total_seconds()
        yield event.plain_result(f"⏳ 您还需要等待 {int(wait_time)} 秒才能再次钓鱼。")
        return
    fishing_cost = _get_fishing_cost(self, user)
    result = self.fishing_service.go_fish(user_id)
    if not result:
        yield event.plain_result("❌ 出错啦！请稍后再试。")
        return
    yield event.plain_result(_build_fish_message(result, fishing_cost))

async def auto_fish(self, event: AstrMessageEvent):
    """自动钓鱼"""
    user_id = self._get_effective_user_id(event)
    result = self.fishing_service.toggle_auto_fishing(user_id)
    yield event.plain_result(result["message"])

async def fishing_area(self, event: AstrMessageEvent):
    """查看当前钓鱼区域"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        result = self.fishing_service.get_user_fishing_zones(user_id)
        if not result:
            yield event.plain_result("❌ 出错啦！请稍后再试。")
            return
        if not result.get("success"):
            yield event.plain_result(f"❌ 查看钓鱼区域失败：{result['message']}")
            return
        zones = result.get("zones", [])
        message = "【🌊 钓鱼区域】\n"
        for zone in zones:
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
            if zone.get('available_from') or zone.get('available_until'):
                message += "⏰ 开放时间: "
                if zone.get('available_from') and zone.get('available_until'):
                    from_time = zone['available_from'].strftime('%Y-%m-%d %H:%M')
                    until_time = zone['available_until'].strftime('%Y-%m-%d %H:%M')
                    message += f"{from_time} 至 {until_time}\n"
                elif zone.get('available_from'):
                    from_time = zone['available_from'].strftime('%Y-%m-%d %H:%M')
                    message += f"{from_time} 开始\n"
                elif zone.get('available_until'):
                    until_time = zone['available_until'].strftime('%Y-%m-%d %H:%M')
                    message += f"至 {until_time} 结束\n"
            remaining_rare = max(0, zone['daily_rare_fish_quota'] - zone['rare_fish_caught_today'])
            if zone.get('daily_rare_fish_quota', 0) > 0:
                message += f"剩余稀有鱼类数量: {remaining_rare}\n"
            message += "\n"
        message += "使用「/钓鱼区域 ID」命令切换钓鱼区域。\n"
        yield event.plain_result(message)
        return
    zone_id = args[1]
    if not zone_id.isdigit():
        yield event.plain_result("❌ 钓鱼区域 ID 必须是数字，请检查后重试。")
        return
    zone_id = int(zone_id)
    
    # 动态获取所有有效的区域ID
    all_zones = self.fishing_zone_service.get_all_zones()
    valid_zone_ids = [zone['id'] for zone in all_zones]
    
    if zone_id not in valid_zone_ids:
        yield event.plain_result(f"❌ 无效的钓鱼区域 ID。有效ID为: {', '.join(map(str, valid_zone_ids))}")
        yield event.plain_result("💡 请使用「/钓鱼区域 <ID>」命令指定区域ID")
        return
    
    # 切换用户的钓鱼区域
    result = self.fishing_service.set_user_fishing_zone(user_id, zone_id)
    yield event.plain_result(result["message"] if result else "❌ 出错啦！请稍后再试。")

async def fish_pokedex(self, event: AstrMessageEvent):
    """查看鱼类图鉴"""
    user_id = self._get_effective_user_id(event)
    result = self.fishing_service.get_user_pokedex(user_id)

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
                message += f"🕰️ 首次捕获：{safe_datetime_handler(fish.get('first_caught_time'))}\n"
                if 'last_caught_time' in fish:
                    message += f"🕰️ 最近捕获：{safe_datetime_handler(fish.get('last_caught_time'))}\n"
                if 'min_weight' in fish and 'max_weight' in fish:
                    message += f"⚖️ 重量纪录：{fish['min_weight']}g ~ {fish['max_weight']}g\n"
                if 'total_caught' in fish and 'total_weight' in fish:
                    message += f"📈 累计：{fish['total_caught']} 条 / {fish['total_weight']}g\n"
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
