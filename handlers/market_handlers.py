from astrbot.api.event import filter, AstrMessageEvent
from ..utils import format_rarity_display, parse_target_user_id

class MarketHandlers:
    @filter.command("一键出售", alias={"出售全部"})
    async def sell_all(self, event: AstrMessageEvent):
        """出售鱼塘中所有鱼"""
        user_id = self._get_effective_user_id(event)
        result = self.market_service.sell_all_fish(user_id)
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 出售失败：{result['message']}")

    @filter.command("保留出售", alias={"出售保留"})
    async def sell_keep(self, event: AstrMessageEvent):
        """保留每个品种的一条鱼，出售其余的"""
        user_id = self._get_effective_user_id(event)
        result = self.market_service.sell_all_fish_except_one_of_each(user_id)
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 出售失败：{result['message']}")

    @filter.command("清空鱼塘", alias={"全部出售"})
    async def sell_everything(self, event: AstrMessageEvent):
        """出售鱼塘中所有鱼，包括新品种"""
        user_id = self._get_effective_user_id(event)
        result = self.market_service.sell_all_fish(user_id, keep_one=False)
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 出售失败：{result['message']}")

    @filter.command("按稀有度出售", alias={"出售稀有度"})
    async def sell_by_rarity(self, event: AstrMessageEvent):
        """出售指定稀有度的所有鱼"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要出售的稀有度，例如：/按稀有度出售 3")
            return
        rarity = args[1]
        if not rarity.isdigit():
            yield event.plain_result("❌ 稀有度必须是数字，请检查后重试。")
            return
        result = self.market_service.sell_fish_by_rarity(user_id, int(rarity))
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 出售失败：{result['message']}")

    @filter.command("卖鱼竿", alias={"出售鱼竿"})
    async def sell_rod(self, event: AstrMessageEvent):
        """出售指定ID的鱼竿"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要出售的鱼竿 ID，例如：/卖鱼竿 12")
            return
        rod_instance_id = args[1]
        if not rod_instance_id.isdigit():
            yield event.plain_result("❌ 鱼竿 ID 必须是数字，请检查后重试。")
            return
        result = self.market_service.sell_rod_by_instance_id(user_id, int(rod_instance_id))
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 出售失败：{result['message']}")

    @filter.command("一键卖鱼竿", alias={"出售全部鱼竿"})
    async def sell_all_rods(self, event: AstrMessageEvent):
        """出售所有鱼竿（保留正在装备的）"""
        user_id = self._get_effective_user_id(event)
        result = self.market_service.sell_all_rods(user_id)
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 出售失败：{result['message']}")

    @filter.command("卖饰品", alias={"出售饰品"})
    async def sell_accessories(self, event: AstrMessageEvent):
        """出售指定ID的饰品"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要出售的饰品 ID，例如：/卖饰品 15")
            return
        accessory_instance_id = args[1]
        if not accessory_instance_id.isdigit():
            yield event.plain_result("❌ 饰品 ID 必须是数字，请检查后重试。")
            return
        result = self.market_service.sell_accessory_by_instance_id(user_id, int(accessory_instance_id))
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 出售失败：{result['message']}")

    @filter.command("一键卖饰品", alias={"出售全部饰品"})
    async def sell_all_accessories(self, event: AstrMessageEvent):
        """出售所有饰品（保留正在装备的）"""
        user_id = self._get_effective_user_id(event)
        result = self.market_service.sell_all_accessories(user_id)
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 出售失败：{result['message']}")

    @filter.command("商店")
    async def shop(self, event: AstrMessageEvent):
        """查看商店信息"""
        shop_info = self.shop_service.get_shop_info()
        if shop_info["success"]:
            message = "【🛒 商店】\n"
            message += "--- 鱼竿 ---\n"
            for rod in shop_info["rods"]:
                message += f" - {rod.name} (ID: {rod.id}) - {rod.price} 金币\n"
                message += f"   - 稀有度: {format_rarity_display(rod.rarity)}\n"
                message += f"   - 耐久度: {rod.durability}\n"
            message += "\n--- 鱼饵 ---\n"
            for bait in shop_info["baits"]:
                message += f" - {bait.name} (ID: {bait.id}) - {bait.price} 金币\n"
                message += f"   - 稀有度: {format_rarity_display(bait.rarity)}\n"
                message += f"   - 效果: {bait.effect_description}\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result("❌ 获取商店信息失败。")

    @filter.command("购买鱼竿", alias={"买鱼竿"})
    async def buy_rod(self, event: AstrMessageEvent):
        """购买鱼竿"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要购买的鱼竿 ID，例如：/购买鱼竿 1")
            return
        rod_template_id = args[1]
        if not rod_template_id.isdigit():
            yield event.plain_result("❌ 鱼竿 ID 必须是数字，请检查后重试。")
            return
        result = self.shop_service.buy_rod(user_id, int(rod_template_id))
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 购买失败：{result['message']}")

    @filter.command("购买鱼饵", alias={"买鱼饵"})
    async def buy_bait(self, event: AstrMessageEvent):
        """购买鱼饵"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要购买的鱼饵 ID，例如：/购买鱼饵 1")
            return
        bait_template_id = args[1]
        if not bait_template_id.isdigit():
            yield event.plain_result("❌ 鱼饵 ID 必须是数字，请检查后重试。")
            return
        result = self.shop_service.buy_bait(user_id, int(bait_template_id))
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 购买失败：{result['message']}")

    @filter.command("市场")
    async def market(self, event: AstrMessageEvent):
        """查看市场信息"""
        page = 1
        args = event.message_str.split(" ")
        if len(args) >= 2 and args[1].isdigit():
            page = int(args[1])

        market_info = self.market_service.get_market_listings(page)
        if market_info["success"]:
            message = f"【🏪 市场 (第{page}页)】\n"
            for item in market_info["items"]:
                if item["item_type"] == "rod" or item["item_type"] == "accessory":
                    message += f" - [{item['item_type']}] {item['item_name']} (ID: {item['listing_id']}) - {item['price']} 金币\n"
                    message += f"   - 稀有度: {format_rarity_display(item['rarity'])}\n"
                    message += f"   - 卖家: {item['seller_nickname']}\n"
                elif item["item_type"] == "item":
                    message += f" - [{item['item_type']}] {item['item_name']} (ID: {item['listing_id']}) - {item['price']} 金币\n"
                    message += f"   - 稀有度: {format_rarity_display(item['rarity'])}\n"
                    message += f"   - 卖家: {item['seller_nickname']}\n"
            message += f"总页数: {market_info['total_pages']}"
            yield event.plain_result(message)
        else:
            yield event.plain_result("❌ 获取市场信息失败。")

    @filter.command("上架鱼竿")
    async def list_rod(self, event: AstrMessageEvent):
        """上架鱼竿"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 3:
            yield event.plain_result("❌ 请指定要上架的鱼竿 ID 和价格，例如：/上架鱼竿 12 1000")
            return
        rod_instance_id = args[1]
        price = args[2]
        if not rod_instance_id.isdigit() or not price.isdigit():
            yield event.plain_result("❌ 鱼竿 ID 和价格都必须是数字，请检查后重试。")
            return
        result = self.market_service.list_item_for_sale(user_id, int(rod_instance_id), int(price), "rod")
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 上架失败：{result['message']}")

    @filter.command("上架饰品")
    async def list_accessories(self, event: AstrMessageEvent):
        """上架饰品"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 3:
            yield event.plain_result("❌ 请指定要上架的饰品 ID 和价格，例如：/上架饰品 15 1000")
            return
        accessory_instance_id = args[1]
        price = args[2]
        if not accessory_instance_id.isdigit() or not price.isdigit():
            yield event.plain_result("❌ 饰品 ID 和价格都必须是数字，请检查后重试。")
            return
        result = self.market_service.list_item_for_sale(user_id, int(accessory_instance_id), int(price), "accessory")
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 上架失败：{result['message']}")

    @filter.command("上架道具")
    async def list_item(self, event: AstrMessageEvent):
        """上架道具"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 3:
            yield event.plain_result("❌ 请指定要上架的道具 ID 和价格，例如：/上架道具 1 1000")
            return
        item_template_id = args[1]
        price = args[2]
        if not item_template_id.isdigit() or not price.isdigit():
            yield event.plain_result("❌ 道具 ID 和价格都必须是数字，请检查后重试。")
            return
        result = self.market_service.list_item_for_sale(user_id, int(item_template_id), int(price), "item")
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 上架失败：{result['message']}")

    @filter.command("购买", alias={"市场购买"})
    async def buy_item(self, event: AstrMessageEvent):
        """购买市场上的物品"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要购买的物品 ID，例如：/购买 1")
            return
        listing_id = args[1]
        if not listing_id.isdigit():
            yield event.plain_result("❌ 物品 ID 必须是数字，请检查后重试。")
            return
        result = self.market_service.buy_item_from_market(user_id, int(listing_id))
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 购买失败：{result['message']}")

    @filter.command("我的上架")
    async def my_listings(self, event: AstrMessageEvent):
        """查看自己上架的物品"""
        user_id = self._get_effective_user_id(event)
        result = self.market_service.get_user_listings(user_id)
        if result["success"]:
            message = "【🛍️ 我上架的物品】\n"
            for item in result["items"]:
                if item["item_type"] == "rod" or item["item_type"] == "accessory":
                    message += f" - [{item['item_type']}] {item['item_name']} (ID: {item['listing_id']}) - {item['price']} 金币\n"
                    message += f"   - 稀有度: {format_rarity_display(item['rarity'])}\n"
                elif item["item_type"] == "item":
                    message += f" - [{item['item_type']}] {item['item_name']} (ID: {item['listing_id']}) - {item['price']} 金币\n"
                    message += f"   - 稀有度: {format_rarity_display(item['rarity'])}\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result("❌ 获取上架信息失败。")

    @filter.command("下架", alias={"下架物品"})
    async def delist_item(self, event: AstrMessageEvent):
        """下架自己上架的物品"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要下架的物品 ID，例如：/下架 1")
            return
        listing_id = args[1]
        if not listing_id.isdigit():
            yield event.plain_result("❌ 物品 ID 必须是数字，请检查后重试。")
            return
        result = self.market_service.delist_item(user_id, int(listing_id))
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 下架失败：{result['message']}")
