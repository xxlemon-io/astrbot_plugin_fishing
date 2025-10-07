from quart import Blueprint, render_template, request, session, jsonify, current_app
from astrbot.api import logger

from .auth_routes import login_required

# 创建游戏相关的Blueprint
game_bp = Blueprint("game_bp", __name__)


@game_bp.route("/game/")
@login_required
async def game_home():
    """游戏主页"""
    return await render_template("game/home.html")


@game_bp.route("/game/fishing")
@login_required
async def game_fishing():
    """钓鱼页面"""
    return await render_template("game/fishing.html")


@game_bp.route("/game/inventory")
@login_required
async def game_inventory():
    """背包页面"""
    return await render_template("game/inventory.html")


@game_bp.route("/game/shop")
@login_required
async def game_shop():
    """商店页面"""
    return await render_template("game/shop.html")


@game_bp.route("/game/market")
@login_required
async def game_market():
    """市场页面"""
    return await render_template("game/market.html")


@game_bp.route("/game/gacha")
@login_required
async def game_gacha():
    """抽卡页面"""
    return await render_template("game/gacha.html")


@game_bp.route("/game/social")
@login_required
async def game_social():
    """社交页面"""
    return await render_template("game/social.html")


@game_bp.route("/game/exchange")
@login_required
async def game_exchange():
    """交易所页面"""
    return await render_template("game/exchange.html")


@game_bp.route("/game/profile")
@login_required
async def game_profile():
    """个人中心页面"""
    return await render_template("game/profile.html")


# ========== API 路由 ==========

@game_bp.route("/game/api/profile", methods=["GET"])
@login_required
async def api_get_profile():
    """获取用户个人信息"""
    try:
        user_id = session.get("game_user_id")
        user_service = current_app.config.get("USER_SERVICE")
        
        if not user_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        user = user_service.user_repo.get_by_id(user_id)
        if not user:
            return jsonify({"success": False, "message": "用户不存在"})
        
        # 获取用户详细信息
        user_data = {
            "user_id": user.user_id,
            "nickname": user.nickname,
            "coins": user.coins,
            "premium_currency": user.premium_currency,
            "total_fishing_count": user.total_fishing_count,
            "total_weight_caught": user.total_weight_caught,
            "total_coins_earned": user.total_coins_earned,
            "consecutive_login_days": user.consecutive_login_days,
            "fish_pond_capacity": user.fish_pond_capacity,
            "aquarium_capacity": user.aquarium_capacity,
            "fishing_zone_id": user.fishing_zone_id,
            "auto_fishing_enabled": user.auto_fishing_enabled,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login_time": user.last_login_time.isoformat() if user.last_login_time else None
        }
        
        return jsonify({"success": True, "data": user_data})
        
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        return jsonify({"success": False, "message": "获取用户信息失败"})


@game_bp.route("/game/api/fishing/cast", methods=["POST"])
@login_required
async def api_fishing_cast():
    """钓鱼API"""
    try:
        user_id = session.get("game_user_id")
        fishing_service = current_app.config.get("FISHING_SERVICE")
        
        if not fishing_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        # 调用钓鱼服务
        result = fishing_service.go_fish(user_id)
        
        if result and result.get("success"):
            return jsonify({
                "success": True,
                "data": {
                    "fish": result.get("fish"),
                    "message": result.get("message"),
                    "equipment_broken_messages": result.get("equipment_broken_messages", [])
                }
            })
        else:
            return jsonify({
                "success": False,
                "message": result.get("message", "钓鱼失败")
            })
            
    except Exception as e:
        logger.error(f"钓鱼失败: {e}")
        return jsonify({"success": False, "message": "钓鱼失败，请稍后重试"})


@game_bp.route("/game/api/fishing/toggle-auto", methods=["POST"])
@login_required
async def api_fishing_toggle_auto():
    """切换自动钓鱼"""
    try:
        user_id = session.get("game_user_id")
        fishing_service = current_app.config.get("FISHING_SERVICE")
        
        if not fishing_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = fishing_service.toggle_auto_fishing(user_id)
        
        return jsonify({
            "success": True,
            "data": {
                "message": result.get("message"),
                "auto_fishing_enabled": result.get("auto_fishing_enabled", False)
            }
        })
        
    except Exception as e:
        logger.error(f"切换自动钓鱼失败: {e}")
        return jsonify({"success": False, "message": "操作失败，请稍后重试"})


@game_bp.route("/game/api/zones", methods=["GET"])
@login_required
async def api_get_zones():
    """获取钓鱼区域列表"""
    try:
        fishing_zone_service = current_app.config.get("FISHING_ZONE_SERVICE")
        
        if not fishing_zone_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        zones = fishing_zone_service.get_all_zones()
        
        return jsonify({
            "success": True,
            "data": zones
        })
        
    except Exception as e:
        logger.error(f"获取区域列表失败: {e}")
        return jsonify({"success": False, "message": "获取区域列表失败"})


@game_bp.route("/game/api/zones/switch", methods=["POST"])
@login_required
async def api_switch_zone():
    """切换钓鱼区域"""
    try:
        data = await request.get_json()
        zone_id = data.get("zone_id")
        
        if not zone_id:
            return jsonify({"success": False, "message": "请选择区域"})
        
        user_id = session.get("game_user_id")
        fishing_zone_service = current_app.config.get("FISHING_ZONE_SERVICE")
        
        if not fishing_zone_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        # 调用区域切换服务
        result = fishing_zone_service.switch_user_zone(user_id, zone_id)
        
        if result.get("success"):
            return jsonify({
                "success": True,
                "data": result
            })
        else:
            return jsonify({
                "success": False,
                "message": result.get("message", "切换区域失败")
            })
            
    except Exception as e:
        logger.error(f"切换区域失败: {e}")
        return jsonify({"success": False, "message": "切换区域失败，请稍后重试"})


@game_bp.route("/game/api/inventory/<item_type>", methods=["GET"])
@login_required
async def api_get_inventory(item_type):
    """获取背包数据"""
    try:
        user_id = session.get("game_user_id")
        inventory_service = current_app.config.get("INVENTORY_SERVICE")
        
        if not inventory_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        # 根据类型获取不同的背包数据
        if item_type == "fish":
            result = inventory_service.get_user_fish_inventory(user_id)
        elif item_type == "rods":
            result = inventory_service.get_user_rods(user_id)
        elif item_type == "accessories":
            result = inventory_service.get_user_accessories(user_id)
        elif item_type == "items":
            result = inventory_service.get_user_items(user_id)
        elif item_type == "baits":
            result = inventory_service.get_user_baits(user_id)
        else:
            return jsonify({"success": False, "message": "无效的物品类型"})
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取背包数据失败: {e}")
        return jsonify({"success": False, "message": "获取背包数据失败"})


@game_bp.route("/game/api/inventory/equip", methods=["POST"])
@login_required
async def api_equip_item():
    """装备/卸下物品"""
    try:
        data = await request.get_json()
        item_type = data.get("item_type")
        item_id = data.get("item_id")
        action = data.get("action", "equip")  # equip 或 unequip
        
        user_id = session.get("game_user_id")
        inventory_service = current_app.config.get("INVENTORY_SERVICE")
        
        if not inventory_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        # 调用装备服务
        if action == "equip":
            result = inventory_service.equip_item(user_id, item_type, item_id)
        else:
            result = inventory_service.unequip_item(user_id, item_type)
        
        if result.get("success"):
            return jsonify({
                "success": True,
                "data": result
            })
        else:
            return jsonify({
                "success": False,
                "message": result.get("message", "操作失败")
            })
            
    except Exception as e:
        logger.error(f"装备操作失败: {e}")
        return jsonify({"success": False, "message": "操作失败，请稍后重试"})


@game_bp.route("/game/api/inventory/refine", methods=["POST"])
@login_required
async def api_refine_item():
    """精炼物品"""
    try:
        data = await request.get_json()
        item_type = data.get("item_type")
        item_id = data.get("item_id")
        
        user_id = session.get("game_user_id")
        inventory_service = current_app.config.get("INVENTORY_SERVICE")
        
        if not inventory_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        # 调用精炼服务
        result = inventory_service.refine_item(user_id, item_type, item_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"精炼失败: {e}")
        return jsonify({"success": False, "message": "精炼失败，请稍后重试"})


@game_bp.route("/game/api/inventory/sell", methods=["POST"])
@login_required
async def api_sell_item():
    """出售物品"""
    try:
        data = await request.get_json()
        item_type = data.get("item_type")
        item_id = data.get("item_id")
        quantity = data.get("quantity", 1)
        
        user_id = session.get("game_user_id")
        inventory_service = current_app.config.get("INVENTORY_SERVICE")
        
        if not inventory_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        # 调用出售服务
        result = inventory_service.sell_item(user_id, item_type, item_id, quantity)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"出售失败: {e}")
        return jsonify({"success": False, "message": "出售失败，请稍后重试"})


@game_bp.route("/game/api/shops", methods=["GET"])
@login_required
async def api_get_shops():
    """获取商店列表"""
    try:
        shop_service = current_app.config.get("SHOP_SERVICE")
        
        if not shop_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        shops = shop_service.shop_repo.get_all_shops()
        
        return jsonify({
            "success": True,
            "data": shops
        })
        
    except Exception as e:
        logger.error(f"获取商店列表失败: {e}")
        return jsonify({"success": False, "message": "获取商店列表失败"})


@game_bp.route("/game/api/shops/<int:shop_id>/items", methods=["GET"])
@login_required
async def api_get_shop_items(shop_id):
    """获取商店商品"""
    try:
        shop_service = current_app.config.get("SHOP_SERVICE")
        
        if not shop_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        items = shop_service.shop_repo.get_shop_items(shop_id)
        
        return jsonify({
            "success": True,
            "data": items
        })
        
    except Exception as e:
        logger.error(f"获取商店商品失败: {e}")
        return jsonify({"success": False, "message": "获取商店商品失败"})


@game_bp.route("/game/api/shops/purchase", methods=["POST"])
@login_required
async def api_purchase_item():
    """购买商品"""
    try:
        data = await request.get_json()
        shop_id = data.get("shop_id")
        item_id = data.get("item_id")
        quantity = data.get("quantity", 1)
        
        user_id = session.get("game_user_id")
        shop_service = current_app.config.get("SHOP_SERVICE")
        
        if not shop_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        # 调用购买服务
        result = shop_service.purchase_item(user_id, shop_id, item_id, quantity)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"购买失败: {e}")
        return jsonify({"success": False, "message": "购买失败，请稍后重试"})
