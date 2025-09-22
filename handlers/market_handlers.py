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
        yield event.plain_result("❌ 请指定要出售的鱼竿 ID，例如：/出售鱼竿 12")
        return
    rod_instance_id = args[1]
    if not rod_instance_id.isdigit():
        yield event.plain_result("❌ 鱼竿 ID 必须是数字，请检查后重试。")
        return
    if result := self.inventory_service.sell_rod(user_id, int(rod_instance_id)):
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
        yield event.plain_result("❌ 请指定要出售的饰品 ID，例如：/出售饰品 15")
        return
    accessory_instance_id = args[1]
    if not accessory_instance_id.isdigit():
        yield event.plain_result("❌ 饰品 ID 必须是数字，请检查后重试。")
        return
    result = self.inventory_service.sell_accessory(user_id, int(accessory_instance_id))
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
    """查看商店"""
    from ..utils import to_percentage
    result = self.shop_service.get_shop_listings()
    if result:
        message = "【🛒 商店】\n\n"
        if result["baits"]:
            message += "【🐟 鱼饵】:\n"
            for bait in result["baits"]:
                message += f" - {bait.name} (ID: {bait.bait_id}) - 价格: {bait.cost} 金币\n - 描述：{bait.description}\n\n"
        else:
            message += "🐟 商店中没有鱼饵可供购买。\n\n"
        if result["rods"]:
            message += "\n【🎣 鱼竿】:\n"
            for rod in result["rods"]:
                message += f" - {rod.name} (ID: {rod.rod_id}) - 价格: {rod.purchase_cost} 金币\n"
                if rod.bonus_fish_quality_modifier != 1.0:
                    message += f"   - 质量加成⬆️: {to_percentage(rod.bonus_fish_quality_modifier)}\n"
                if rod.bonus_fish_quantity_modifier != 1.0:
                    message += f"   - 数量加成⬆️: {to_percentage(rod.bonus_fish_quantity_modifier)}\n"
                if rod.bonus_rare_fish_chance != 0.0:
                    message += f"   - 钓鱼加成⬆️: {to_percentage(rod.bonus_rare_fish_chance)}\n"
                message += "\n"
        else:
            message += "🎣 商店中没有鱼竿可供购买。\n"
        yield event.plain_result(message)
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def buy_rod(self, event: AstrMessageEvent):
    """购买鱼竿"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result("❌ 请指定要购买的鱼竿 ID，例如：/购买鱼竿 12")
        return
    rod_instance_id = args[1]
    if not rod_instance_id.isdigit():
        yield event.plain_result("❌ 鱼竿 ID 必须是数字，请检查后重试。")
        return
    result = self.shop_service.buy_item(user_id, "rod", int(rod_instance_id))
    if result:
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 购买鱼竿失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def buy_bait(self, event: AstrMessageEvent):
    """购买鱼饵"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result("❌ 请指定要购买的鱼饵 ID，例如：/购买鱼饵 13")
        return
    bait_instance_id = args[1]
    if not bait_instance_id.isdigit():
        yield event.plain_result("❌ 鱼饵 ID 必须是数字，请检查后重试。")
        return
    quantity = 1  # 默认购买数量为1
    if len(args) == 3:
        quantity = args[2]
        if not quantity.isdigit() or int(quantity) <= 0:
            yield event.plain_result("❌ 购买数量必须是正整数，请检查后重试。")
            return
    result = self.shop_service.buy_item(user_id, "bait", int(bait_instance_id), int(quantity))
    if result:
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 购买鱼饵失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def market(self, event: AstrMessageEvent):
    """查看市场"""
    result = self.market_service.get_market_listings()
    if result["success"]:
        message = "【🛒 市场】\n\n"
        if result["rods"]:
            message += "【🎣 鱼竿】:\n"
            for rod in result["rods"]:
                message += f" - {rod['item_name']} 精{rod['refine_level']} (ID: {rod['market_id']}) - 价格: {rod['price']} 金币\n"
                message += f" - 售卖人： {rod['seller_nickname']}\n\n"
        else:
            message += "🎣 市场中没有鱼竿可供购买。\n\n"
        if result["accessories"]:
            message += "【💍 饰品】:\n"
            for accessory in result["accessories"]:
                message += f" - {accessory['item_name']} 精{accessory['refine_level']} (ID: {accessory['market_id']}) - 价格: {accessory['price']} 金币\n"
                message += f" - 售卖人： {accessory['seller_nickname']}\n\n"
        else:
            message += "💍 市场中没有饰品可供购买。\n\n"
        if result["items"]:
            message += "【🎁 道具】:\n"
            for item in result["items"]:
                message += f" - {item['item_name']} (ID: {item['market_id']}) - 价格: {item['price']} 金币\n"
                message += f" - 售卖人： {item['seller_nickname']}\n\n"
        else:
            message += "🎁 市场中没有道具可供购买。\n"
        yield event.plain_result(message)
    else:
        yield event.plain_result(f"❌ 出错啦！{result['message']}")

async def list_rod(self, event: AstrMessageEvent):
    """上架鱼竿到市场"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 3:
        yield event.plain_result("❌ 请指定要上架的鱼竿 ID和价格，例如：/上架鱼竿 12 1000")
        return
    rod_instance_id = args[1]
    if not rod_instance_id.isdigit():
        yield event.plain_result("❌ 鱼竿 ID 必须是数字，请检查后重试。")
        return
    price = args[2]
    if not price.isdigit() or int(price) <= 0:
        yield event.plain_result("❌ 上架价格必须是正整数，请检查后重试。")
        return
    result = self.market_service.put_item_on_sale(user_id, "rod", int(rod_instance_id), int(price))
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
        yield event.plain_result("❌ 请指定要上架的饰品 ID和价格，例如：/上架饰品 15 1000")
        return
    accessory_instance_id = args[1]
    if not accessory_instance_id.isdigit():
        yield event.plain_result("❌ 饰品 ID 必须是数字，请检查后重试。")
        return
    price = args[2]
    if not price.isdigit() or int(price) <= 0:
        yield event.plain_result("❌ 上架价格必须是正整数，请检查后重试。")
        return
    result = self.market_service.put_item_on_sale(user_id, "accessory", int(accessory_instance_id), int(price))
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

async def buy_item(self, event: AstrMessageEvent):
    """购买市场上的物品"""
    user_id = self._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result("❌ 请指定要购买的物品 ID，例如：/购买 12")
        return
    item_instance_id = args[1]
    if not item_instance_id.isdigit():
        yield event.plain_result("❌ 物品 ID 必须是数字，请检查后重试。")
        return
    result = self.market_service.buy_market_item(user_id, int(item_instance_id))
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
        
        message = f"【🛒 我的上架商品】共 {result['count']} 件\n\n"
        for listing in listings:
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
        yield event.plain_result("❌ 请指定要下架的商品 ID，例如：/下架 12\n💡 使用「我的上架」命令查看您的商品列表")
        return
    market_id = args[1]
    if not market_id.isdigit():
        yield event.plain_result("❌ 商品 ID 必须是数字，请检查后重试。")
        return
    market_id = int(market_id)
    result = self.market_service.delist_item(user_id, market_id)
    if result:
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 下架失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")
