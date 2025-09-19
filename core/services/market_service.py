from typing import Dict, Any
from datetime import datetime

from astrbot.core.utils.pip_installer import logger
# 导入仓储接口和领域模型
from ..repositories.abstract_repository import (
    AbstractMarketRepository,
    AbstractInventoryRepository,
    AbstractUserRepository,
    AbstractLogRepository,
    AbstractItemTemplateRepository
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
        config: Dict[str, Any]
    ):
        self.market_repo = market_repo
        self.inventory_repo = inventory_repo
        self.user_repo = user_repo
        self.log_repo = log_repo
        self.item_template_repo = item_template_repo  # 修正：赋值给实例变量
        self.config = config

    def get_market_listings(self) -> Dict[str, Any]:
        """
        提供查看市场所有商品的功能。
        """
        try:
            # 获取所有商品（不分页）
            listings, _ = self.market_repo.get_all_listings()
            # 按物品类型分组，便于前端展示
            rods = [item for item in listings if item.item_type == "rod"]
            accessories = [item for item in listings if item.item_type == "accessory"]
            return {
                "success": True,
                "rods": rods,
                "accessories": accessories
            }
        except Exception as e:
            return {"success": False, "message": f"获取市场列表失败: {e}"}

    def put_item_on_sale(self, user_id: str, item_type: str, item_instance_id: int, price: int) -> Dict[str, Any]:
        """
        处理上架物品到市场的逻辑。
        """
        if price <= 0:
            return {"success": False, "message": "上架价格必须大于0"}

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
        if item_type == "rod":
            user_items = self.inventory_repo.get_user_rod_instances(user_id)
            item_to_list = next((i for i in user_items if i.rod_instance_id == item_instance_id), None)
            if not item_to_list:
                return {"success": False, "message": "鱼竿不存在或不属于你"}
            if item_to_list.is_equipped:
                return {"success": False, "message": "不能上架正在装备的鱼竿"}
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
            item_template_id = item_to_list.accessory_id
            accessory_template = self.item_template_repo.get_accessory_by_id(item_template_id)
            item_name = accessory_template.name if accessory_template else None
            item_description = accessory_template.description if accessory_template else None
            item_refine_level = item_to_list.refine_level
        else:
            return {"success": False, "message": "该类型的物品无法上架"}

        # 执行上架事务
        # 1. 从玩家背包移除物品
        if item_type == "rod":
            self.inventory_repo.delete_rod_instance(item_instance_id)
        elif item_type == "accessory":
            self.inventory_repo.delete_accessory_instance(item_instance_id)

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
            quantity=1,
            item_name=item_name,
            item_description=item_description,
            price=price,
            listed_at=datetime.now(),
            refine_level=item_refine_level
        )
        self.market_repo.add_listing(new_listing)

        return {"success": True, "message": f"成功将物品上架市场，价格为 {price} 金币 (手续费: {tax_cost} 金币)"}

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
        if listing.item_type == "rod":
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

        # 4. 从市场移除该商品
        self.market_repo.remove_listing(market_id)

        return {"success": True, "message": f"✅ 购买成功，花费 {listing.price} 金币！"}

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
            if listing.item_type == "rod":
                # 返还鱼竿
                rod_template = self.item_template_repo.get_rod_by_id(listing.item_id)
                self.inventory_repo.add_rod_instance(
                    user_id=user_id,
                    rod_id=listing.item_id,
                    durability=rod_template.durability if rod_template else None,
                    refine_level=listing.refine_level
                )
            elif listing.item_type == "accessory":
                # 返还饰品
                self.inventory_repo.add_accessory_instance(
                    user_id=user_id,
                    accessory_id=listing.item_id,
                    refine_level=listing.refine_level
                )
            else:
                return {"success": False, "message": "不支持的物品类型"}

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
                "accessory_count": len([item for item in all_listings if item.item_type == "accessory"])
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
                return {"success": False, "message": "卖家不存在，无法返还物品"}
            
            # 将物品返还给卖家
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
            
            # 从市场移除
            self.market_repo.remove_listing(market_id)
            
            return {
                "success": True, 
                "message": f"商品已下架，已返还给卖家 {seller.nickname}"
            }
        except Exception as e:
            logger.error(f"下架商品失败: {e}")
            return {"success": False, "message": f"下架商品失败: {e}"}