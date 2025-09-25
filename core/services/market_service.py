from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import random

from astrbot.api import logger
# 导入仓储接口和领域模型
from ..repositories.abstract_repository import (
    AbstractMarketRepository,
    AbstractInventoryRepository,
    AbstractUserRepository,
    AbstractLogRepository,
    AbstractItemTemplateRepository,
    AbstractExchangeRepository,
)
from ..domain.models import MarketListing, TaxRecord


class MarketService:
    """封装与玩家交易市场相关的业务逻辑"""

    def __init__(
        self,
        market_repo: AbstractMarketRepository,
        inventory_repo: AbstractInventoryRepository,
        user_repo: AbstractUserRepository,
        log_repo: AbstractLogRepository,
        item_template_repo: AbstractItemTemplateRepository,
        exchange_repo: AbstractExchangeRepository,
        config: Dict[str, Any]
    ):
        self.market_repo = market_repo
        self.inventory_repo = inventory_repo
        self.user_repo = user_repo
        self.log_repo = log_repo
        self.item_template_repo = item_template_repo
        self.exchange_repo = exchange_repo
        self.config = config

    def cleanup_expired_listings(self):
        """
        清理过期的市场挂单。
        - 挂单超过5天的将返还给物主。
        - 在市场上腐败的大宗商品将被直接移除。
        """
        try:
            listings, _ = self.market_repo.get_all_listings()
            now = datetime.now()
            five_days_ago = now - timedelta(days=5)

            for listing in listings:
                # 检查1: 大宗商品是否在市场上腐败
                if listing.item_type == "commodity" and listing.expires_at and listing.expires_at < now:
                    self.market_repo.remove_listing(listing.market_id)
                    logger.info(f"市场上的腐败商品已被清除: Market ID {listing.market_id}")
                    continue  # 继续处理下一个

                # 检查2: 挂单是否超过5天
                if listing.listed_at < five_days_ago:
                    try:
                        self._return_listing_to_seller(listing)
                        self.market_repo.remove_listing(listing.market_id)
                        logger.info(f"过期挂单已自动下架并返还: Market ID {listing.market_id} -> User {listing.user_id}")
                    except Exception as e:
                        logger.error(f"自动下架 Market ID {listing.market_id} 失败: {e}")
        except Exception as e:
            logger.error(f"市场清理任务失败: {e}")

    def get_market_listings(self) -> Dict[str, Any]:
        """
        提供查看市场所有商品的功能。
        """
        try:
            # 每次查看市场前，先执行清理
            self.cleanup_expired_listings()

            # 获取所有商品（不分页）
            listings, _ = self.market_repo.get_all_listings()
            # 按物品类型分组，便于前端展示
            rods = [item for item in listings if item.item_type == "rod"]
            accessories = [item for item in listings if item.item_type == "accessory"]
            items = [item for item in listings if item.item_type == "item"]
            fish = [item for item in listings if item.item_type == "fish"]
            commodities = [item for item in listings if item.item_type == "commodity"]
            return {
                "success": True,
                "rods": rods,
                "accessories": accessories,
                "items": items,
                "fish": fish,
                "commodities": commodities
            }
        except Exception as e:
            return {"success": False, "message": f"获取市场列表失败: {e}"}

    def put_item_on_sale(self, user_id: str, item_type: str, item_instance_id: int, price: int, is_anonymous: bool = False, quantity: int = 1) -> Dict[str, Any]:
        """
        处理上架物品到市场的逻辑。
        
        Args:
            user_id: 用户ID
            item_type: 物品类型 ("rod", "accessory", "item", "fish", "commodity")
            item_instance_id: 物品实例ID（对于道具、鱼类和商品，这是模板ID或实例ID）
            price: 单价
            is_anonymous: 是否匿名上架
            quantity: 上架数量（默认1）
        """
        if price <= 0:
            return {"success": False, "message": "上架价格必须大于0"}
        
        if quantity <= 0:
            return {"success": False, "message": "上架数量必须大于0"}

        seller = self.user_repo.get_by_id(user_id)
        if not seller:
            return {"success": False, "message": "用户不存在"}

        # 计算并检查上架税
        tax_rate = self.config.get("market", {}).get("listing_tax_rate", 0.02) # 默认2%
        tax_cost = int(price * tax_rate)
        if not seller.can_afford(tax_cost):
            return {"success": False, "message": f"金币不足以支付上架手续费: {tax_cost} 金币"}

        # 验证物品所有权并获取模板ID
        item_template_id = None
        item_name = None
        item_description = None
        item_refine_level = 1
        expires_at = None  # 为大宗商品设置
        if item_type == "rod":
            user_items = self.inventory_repo.get_user_rod_instances(user_id)
            item_to_list = next((i for i in user_items if i.rod_instance_id == item_instance_id), None)
            if not item_to_list:
                return {"success": False, "message": "鱼竿不存在或不属于你"}
            if item_to_list.is_equipped:
                return {"success": False, "message": "不能上架正在装备的鱼竿"}
            if item_to_list.is_locked:
                return {"success": False, "message": "该鱼竿已锁定，无法上架"}
            item_template_id = item_to_list.rod_id
            rod_template = self.item_template_repo.get_rod_by_id(item_template_id)
            item_name = rod_template.name if rod_template else None
            item_description = rod_template.description if rod_template else None
            item_refine_level = item_to_list.refine_level
        elif item_type == "accessory":
            user_items = self.inventory_repo.get_user_accessory_instances(user_id)
            item_to_list = next((i for i in user_items if i.accessory_instance_id == item_instance_id), None)
            if not item_to_list:
                return {"success": False, "message": "饰品不存在或不属于你"}
            if item_to_list.is_equipped:
                 return {"success": False, "message": "不能上架正在装备的饰品"}
            if item_to_list.is_locked:
                return {"success": False, "message": "该饰品已锁定，无法上架"}
            item_template_id = item_to_list.accessory_id
            accessory_template = self.item_template_repo.get_accessory_by_id(item_template_id)
            item_name = accessory_template.name if accessory_template else None
            item_description = accessory_template.description if accessory_template else None
            item_refine_level = item_to_list.refine_level
        elif item_type == "item":
            # 道具上架逻辑
            user_item_inventory = self.inventory_repo.get_user_item_inventory(user_id)
            if item_instance_id not in user_item_inventory or user_item_inventory[item_instance_id] <= 0:
                return {"success": False, "message": "道具不存在或数量不足"}
            
            # 检查道具数量
            current_quantity = user_item_inventory[item_instance_id]
            if current_quantity < quantity:
                return {"success": False, "message": f"道具数量不足，当前有 {current_quantity} 个，需要 {quantity} 个"}
            
            item_template_id = item_instance_id  # 对于道具，instance_id就是template_id
            item_template = self.item_template_repo.get_item_by_id(item_template_id)
            item_name = item_template.name if item_template else None
            item_description = item_template.description if item_template else None
            item_refine_level = 1  # 道具没有精炼等级
        elif item_type == "fish":
            # 鱼类上架逻辑 - 检查鱼塘和水族箱的总数量
            total_fish_quantity = self.inventory_repo.get_user_total_fish_count(user_id, item_instance_id)
            if total_fish_quantity < quantity:
                return {"success": False, "message": f"鱼类数量不足，当前有 {total_fish_quantity} 条，需要 {quantity} 条"}
            
            item_template_id = item_instance_id  # 对于鱼类，instance_id就是template_id
            fish_template = self.item_template_repo.get_fish_by_id(item_template_id)
            item_name = fish_template.name if fish_template else None
            item_description = fish_template.description if fish_template else None
            item_refine_level = 1  # 鱼类没有精炼等级
        elif item_type == "commodity":
            user_commodity = self.exchange_repo.get_user_commodity_by_instance_id(item_instance_id)
            if not user_commodity or user_commodity.user_id != user_id:
                return {"success": False, "message": "大宗商品不存在或不属于你"}
            if user_commodity.quantity < quantity:
                return {"success": False, "message": f"数量不足，您只有 {user_commodity.quantity} 份"}
            
            # 检查上架后是否会超出交易所容量限制
            # 计算上架后剩余的交易所库存
            remaining_quantity = user_commodity.quantity - quantity
            if remaining_quantity > 0:
                # 如果还有剩余，检查剩余数量是否会导致容量超限
                capacity = self.config.get("capacity", 1000)
                user_commodities = self.exchange_repo.get_user_commodities(user_id)
                current_total_quantity = sum(item.quantity for item in user_commodities)
                # 减去即将上架的数量，加上剩余数量
                new_total_quantity = current_total_quantity - quantity + remaining_quantity
                if new_total_quantity > capacity:
                    return {"success": False, "message": f"上架后交易所容量将超限！当前容量: {capacity}，上架后总库存: {new_total_quantity}"}
            
            commodity_template = self.exchange_repo.get_commodity_by_id(user_commodity.commodity_id)
            item_template_id = user_commodity.commodity_id
            item_name = commodity_template.name
            item_description = commodity_template.description
            item_refine_level = 1
            expires_at = user_commodity.expires_at  # 传递腐败时间

            # 从用户库存中扣除
            if remaining_quantity > 0:
                self.exchange_repo.update_user_commodity_quantity(item_instance_id, remaining_quantity)
            else:
                self.exchange_repo.delete_user_commodity(item_instance_id)
        else:
            return {"success": False, "message": "该类型的物品无法上架"}

        # 执行上架事务
        # 1. 从玩家背包移除物品
        if item_type == "rod":
            self.inventory_repo.delete_rod_instance(item_instance_id)
        elif item_type == "accessory":
            self.inventory_repo.delete_accessory_instance(item_instance_id)
        elif item_type == "item":
            # 减少道具数量
            self.inventory_repo.update_item_quantity(user_id, item_instance_id, -quantity)
        elif item_type == "fish":
            # 智能扣除鱼类数量（优先从鱼塘，然后从水族箱）
            self.inventory_repo.deduct_fish_smart(user_id, item_instance_id, quantity)
        elif item_type == "commodity":
            # 从交易所移除大宗商品
            self.exchange_repo.delete_user_commodity(item_instance_id)

        # 2. 扣除税费
        seller.coins -= tax_cost
        self.user_repo.update(seller)

        # 3. 记录税收日志
        tax_log = TaxRecord(tax_id=0, user_id=user_id, tax_amount=tax_cost, tax_rate=tax_rate,
                            original_amount=price, balance_after=seller.coins, tax_type="市场交易税",
                            timestamp=datetime.now())
        self.log_repo.add_tax_record(tax_log)


        # 4. 创建市场条目
        new_listing = MarketListing(
            market_id=0, # DB自增
            user_id=user_id,
            seller_nickname=seller.nickname,
            item_type=item_type,
            item_id=item_template_id,
            item_instance_id=item_instance_id if item_type not in ["item", "fish"] else None,
            quantity=quantity,
            item_name=item_name,
            item_description=item_description,
            price=price,
            listed_at=datetime.now(),
            expires_at=expires_at,  # 保存腐败时间
            refine_level=item_refine_level,
            is_anonymous=is_anonymous
        )
        self.market_repo.add_listing(new_listing)

        if quantity > 1:
            total_price = price * quantity
            return {"success": True, "message": f"成功将【{item_name}】上架市场 x{quantity}，总价 {total_price} 金币 (手续费: {tax_cost} 金币)"}
        else:
            return {"success": True, "message": f"成功将【{item_name}】上架市场，单价 {price} 金币 (手续费: {tax_cost} 金币)"}

    def get_market_id_by_instance_id(self, item_type: str, instance_id: int) -> Optional[int]:
        """
        根据实例ID查找市场ID
        
        Args:
            item_type: 物品类型 ("rod", "accessory", "commodity")
            instance_id: 实例ID
            
        Returns:
            市场ID，如果未找到返回None
        """
        try:
            listings, _ = self.market_repo.get_all_listings()
            for listing in listings:
                if (listing.item_type == item_type and 
                    listing.item_instance_id == instance_id):
                    return listing.market_id
            return None
        except Exception as e:
            logger.error(f"查找市场ID失败: {e}")
            return None

    def get_market_id_by_fish_id(self, fish_id: int) -> Optional[int]:
        """
        根据鱼类ID查找市场ID
        
        Args:
            fish_id: 鱼类ID
            
        Returns:
            市场ID，如果未找到返回None
        """
        try:
            listings, _ = self.market_repo.get_all_listings()
            for listing in listings:
                if (listing.item_type == "fish" and 
                    listing.item_id == fish_id):
                    return listing.market_id
            return None
        except Exception as e:
            logger.error(f"查找鱼类市场ID失败: {e}")
            return None

    def get_market_id_by_item_id(self, item_id: int) -> Optional[int]:
        """
        根据道具ID查找市场ID
        
        Args:
            item_id: 道具ID
            
        Returns:
            市场ID，如果未找到返回None
        """
        try:
            listings, _ = self.market_repo.get_all_listings()
            for listing in listings:
                if (listing.item_type == "item" and 
                    listing.item_id == item_id):
                    return listing.market_id
            return None
        except Exception as e:
            logger.error(f"查找道具市场ID失败: {e}")
            return None

    def buy_market_item(self, buyer_id: str, market_id: int) -> Dict[str, Any]:
        """
        处理从市场购买物品的逻辑。
        """
        buyer = self.user_repo.get_by_id(buyer_id)
        if not buyer:
            return {"success": False, "message": "购买者用户不存在"}

        listing = self.market_repo.get_listing_by_id(market_id)
        if not listing:
            return {"success": False, "message": "该商品不存在或已被购买"}


        seller = self.user_repo.get_by_id(listing.user_id)
        if not seller:
            return {"success": False, "message": "卖家信息丢失，交易无法进行"}

        if not buyer.can_afford(listing.price):
            return {"success": False, "message": f"金币不足，需要 {listing.price} 金币"}

        # 执行交易
        # 1. 从买家扣款
        buyer.coins -= listing.price
        self.user_repo.update(buyer)

        # 2. 给卖家打款
        seller.coins += listing.price
        self.user_repo.update(seller)

        # 3. 将物品发给买家
        if listing.item_type == "commodity":
            # 检查买家是否有交易所账户
            if not buyer.exchange_account_status:
                return {"success": False, "message": "您需要先开通交易所账户才能购买大宗商品"}

            # 如果没有腐败时间，使用默认值（兼容旧数据）
            expires_at = listing.expires_at or datetime.now() + timedelta(days=3)

            from ..domain.models import UserCommodity
            new_commodity = UserCommodity(
                instance_id=0,
                user_id=buyer_id,
                commodity_id=listing.item_id,
                quantity=listing.quantity,
                purchase_price=listing.price, # Use market price as purchase price
                purchased_at=datetime.now(),
                expires_at=expires_at # 继承腐败时间
            )
            self.exchange_repo.add_user_commodity(new_commodity)

        elif listing.item_type == "rod":
            rod_template = self.item_template_repo.get_rod_by_id(listing.item_id)
            self.inventory_repo.add_rod_instance(
                user_id=buyer_id,
                rod_id=listing.item_id,
                durability=rod_template.durability if rod_template else None,
                refine_level=listing.refine_level
            )
        elif listing.item_type == "accessory":
            self.inventory_repo.add_accessory_instance(
                user_id=buyer_id,
                accessory_id=listing.item_id,
                refine_level=listing.refine_level
            )
        elif listing.item_type == "item":
            # 给买家添加道具
            self.inventory_repo.update_item_quantity(buyer_id, listing.item_id, listing.quantity)
        elif listing.item_type == "fish":
            # 给买家添加鱼类到水族箱（默认放入水族箱）
            self.inventory_repo.add_fish_to_aquarium(buyer_id, listing.item_id, listing.quantity)

        # 4. 从市场移除该商品
        self.market_repo.remove_listing(market_id)

        quantity_text = f" x{listing.quantity}" if listing.quantity > 1 else ""
        
        # 如果是鱼类，提示用户去水族箱查收
        if listing.item_type == "fish":
            return {"success": True, "message": f"✅ 成功购买【{listing.item_name}】{quantity_text}，花费 {listing.price} 金币！\n🐠 请前往水族箱查收您的鱼类！"}
        else:
            return {"success": True, "message": f"✅ 成功购买【{listing.item_name}】{quantity_text}，花费 {listing.price} 金币！"}

    def _return_listing_to_seller(self, listing):
        """将挂单物品返还给卖家"""
        if listing.item_type == "rod":
            rod_template = self.item_template_repo.get_rod_by_id(listing.item_id)
            self.inventory_repo.add_rod_instance(
                user_id=listing.user_id,
                rod_id=listing.item_id,
                durability=rod_template.durability if rod_template else None,
                refine_level=listing.refine_level
            )
        elif listing.item_type == "accessory":
            self.inventory_repo.add_accessory_instance(
                user_id=listing.user_id,
                accessory_id=listing.item_id,
                refine_level=listing.refine_level
            )
        elif listing.item_type == "item":
            self.inventory_repo.update_item_quantity(listing.user_id, listing.item_id, listing.quantity)
        elif listing.item_type == "fish":
            self.inventory_repo.add_fish_to_inventory(listing.user_id, listing.item_id, listing.quantity)
        elif listing.item_type == "commodity":
            from ..domain.models import UserCommodity
            # 检查卖家交易所容量
            capacity = self.config.get("capacity", 1000)
            user_commodities = self.exchange_repo.get_user_commodities(listing.user_id)
            current_total_quantity = sum(item.quantity for item in user_commodities)
            if current_total_quantity + listing.quantity > capacity:
                raise Exception("卖家交易所容量不足，无法返还物品")
            
            new_commodity = UserCommodity(
                instance_id=0,
                user_id=listing.user_id,
                commodity_id=listing.item_id,
                quantity=listing.quantity,
                purchase_price=0,  # 返还时买入价重置
                purchased_at=datetime.now(),
                expires_at=listing.expires_at or datetime.now() + timedelta(days=3)  # 如果没有腐败时间，默认3天
            )
            self.exchange_repo.add_user_commodity(new_commodity)
        else:
            raise ValueError(f"不支持的物品类型: {listing.item_type}")

    def delist_item(self, user_id: str, market_id: int) -> Dict[str, Any]:
        """
        用户下架自己的商品
        """
        # 检查用户是否存在
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        # 获取商品信息
        listing = self.market_repo.get_listing_by_id(market_id)
        if not listing:
            return {"success": False, "message": "该商品不存在或已被下架"}

        # 检查是否为物品所有者
        if listing.user_id != user_id:
            return {"success": False, "message": "你只能下架自己的商品"}

        # 将物品返还给用户
        try:
            self._return_listing_to_seller(listing)
            # 从市场移除商品
            self.market_repo.remove_listing(market_id)
            return {"success": True, "message": f"✅ 成功下架 {listing.item_name}，物品已返还到背包"}
        except Exception as e:
            logger.error(f"下架物品时发生错误: {e}")
            return {"success": False, "message": f"下架失败: {str(e)}"}

    def get_user_listings(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户在市场上架的所有商品
        """
        try:
            # 获取用户所有商品列表
            all_listings, _ = self.market_repo.get_all_listings()
            user_listings = [listing for listing in all_listings if listing.user_id == user_id]
            
            return {
                "success": True,
                "listings": user_listings,
                "count": len(user_listings)
            }
        except Exception as e:
            logger.error(f"获取用户商品列表时发生错误: {e}")
            return {"success": False, "message": f"获取商品列表失败: {str(e)}"}

    # --- 管理员功能 ---

    def get_all_market_listings_for_admin(self, page: int = 1, per_page: int = 20, 
                                         item_type: str = None, min_price: int = None, 
                                         max_price: int = None, search: str = None) -> Dict[str, Any]:
        """
        为管理员提供分页的市场商品列表，支持筛选和搜索。
        """
        try:
            # 验证分页参数
            if page < 1:
                page = 1
            if per_page < 1:
                per_page = 20
            
            # 从数据库层获取筛选和分页后的数据
            listings, total_items = self.market_repo.get_all_listings(
                page=page,
                per_page=per_page,
                item_type=item_type,
                min_price=min_price,
                max_price=max_price,
                search=search
            )
            
            # 计算分页信息
            total_pages = (total_items + per_page - 1) // per_page if total_items > 0 else 1
            
            # 验证页面范围
            if page > total_pages and total_pages > 0:
                page = total_pages
                # 重新获取数据
                listings, total_items = self.market_repo.get_all_listings(
                    page=page,
                    per_page=per_page,
                    item_type=item_type,
                    min_price=min_price,
                    max_price=max_price,
                    search=search
                )
            
            # 获取统计信息
            all_listings, total_count = self.market_repo.get_all_listings()
            stats = {
                "total_listings": total_count,
                "filtered_listings": total_items,
                "total_value": sum(item.price for item in listings),
                "rod_count": len([item for item in all_listings if item.item_type == "rod"]),
                "accessory_count": len([item for item in all_listings if item.item_type == "accessory"]),
                "item_count": len([item for item in all_listings if item.item_type == "item"]),
                "fish_count": len([item for item in all_listings if item.item_type == "fish"]),
                "commodity_count": len([item for item in all_listings if item.item_type == "commodity"])
            }
            
            return {
                "success": True,
                "listings": listings,
                "pagination": {
                    "current_page": page,
                    "total_pages": total_pages,
                    "total_items": total_items,
                    "per_page": per_page,
                    "has_prev": page > 1,
                    "has_next": page < total_pages
                },
                "stats": stats
            }
        except Exception as e:
            logger.error(f"获取管理员市场列表失败: {e}")
            return {"success": False, "message": f"获取市场列表失败: {e}"}

    def update_market_item_price(self, market_id: int, new_price: int) -> Dict[str, Any]:
        """
        管理员修改市场商品价格。
        """
        try:
            if new_price <= 0:
                return {"success": False, "message": "价格必须大于0"}
                
            listing = self.market_repo.get_listing_by_id(market_id)
            if not listing:
                return {"success": False, "message": "商品不存在"}
            
            old_price = listing.price
            listing.price = new_price
            self.market_repo.update_listing(listing)
            
            return {
                "success": True, 
                "message": f"商品价格已从 {old_price} 金币修改为 {new_price} 金币"
            }
        except Exception as e:
            logger.error(f"修改商品价格失败: {e}")
            return {"success": False, "message": f"修改价格失败: {e}"}

    def remove_market_item_by_admin(self, market_id: int) -> Dict[str, Any]:
        """
        管理员下架商品，物品返还给卖家。
        """
        try:
            listing = self.market_repo.get_listing_by_id(market_id)
            if not listing:
                return {"success": False, "message": "商品不存在"}
            
            seller = self.user_repo.get_by_id(listing.user_id)
            if not seller:
                # 即使卖家不存在，也应该能移除商品，但无法返还
                self.market_repo.remove_listing(market_id)
                return {"success": True, "message": "商品已下架（卖家不存在，物品已清除）"}
            
            # 将物品返还给卖家
            self._return_listing_to_seller(listing)
            
            # 从市场移除
            self.market_repo.remove_listing(market_id)
            
            return {
                "success": True, 
                "message": f"商品已下架，已返还给卖家 {seller.nickname}"
            }
        except Exception as e:
            logger.error(f"下架商品失败: {e}")
            return {"success": False, "message": f"下架商品失败: {e}"}