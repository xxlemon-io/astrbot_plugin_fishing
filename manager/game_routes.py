import functools
from quart import Blueprint, render_template, request, session, jsonify, current_app
from astrbot.api import logger
from ..core.utils import get_now

# 创建游戏相关的Blueprint
game_bp = Blueprint("game_bp", __name__)


def game_login_required(f):
    """游戏登录验证装饰器"""
    @functools.wraps(f)
    async def wrapper(*args, **kwargs):
        if "game_user_id" not in session:
            # 检查是否是API请求
            if request.path.startswith('/game/api/'):
                return jsonify({"success": False, "message": "请先登录", "redirect": "/game/login"}), 401
            else:
                # 对于页面请求，重定向到登录页面
                from quart import redirect, url_for
                return redirect(url_for('auth_bp.auth_login_page'))
        return await f(*args, **kwargs)
    return wrapper


@game_bp.route("/game/")
@game_login_required
async def game_home():
    """游戏主页"""
    return await render_template("game/home.html")


@game_bp.route("/game/fishing")
@game_login_required
async def game_fishing():
    """钓鱼页面"""
    return await render_template("game/fishing.html")


@game_bp.route("/game/inventory")
@game_login_required
async def game_inventory():
    """背包页面"""
    return await render_template("game/inventory.html")


@game_bp.route("/game/shop")
@game_login_required
async def game_shop():
    """商店页面"""
    return await render_template("game/shop.html")


@game_bp.route("/game/market")
@game_login_required
async def game_market():
    """市场页面"""
    return await render_template("game/market.html")


@game_bp.route("/game/gacha")
@game_login_required
async def game_gacha():
    """抽卡页面"""
    return await render_template("game/gacha.html")


@game_bp.route("/game/social")
@game_login_required
async def game_social():
    """社交页面"""
    return await render_template("game/social.html")


@game_bp.route("/game/exchange")
@game_login_required
async def game_exchange():
    """交易所页面"""
    return await render_template("game/exchange.html")


@game_bp.route("/game/profile")
@game_login_required
async def game_profile():
    """个人中心页面"""
    return await render_template("game/profile.html")


# ========== API 路由 ==========

@game_bp.route("/game/api/profile", methods=["GET"])
@game_login_required
async def api_get_profile():
    """获取用户个人信息"""
    try:
        user_id = session.get("game_user_id")
        user_service = current_app.config.get("USER_SERVICE")
        inventory_service = current_app.config.get("INVENTORY_SERVICE")
        item_template_service = current_app.config.get("ITEM_TEMPLATE_SERVICE")
        
        if not user_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        user = user_service.user_repo.get_by_id(user_id)
        if not user:
            return jsonify({"success": False, "message": "用户不存在"})
        
        # 获取装备的鱼竿信息
        equipped_rod = None
        if user.equipped_rod_instance_id and inventory_service and item_template_service:
            try:
                rod_instance = inventory_service.inventory_repo.get_user_rod_instance_by_id(user_id, user.equipped_rod_instance_id)
                if rod_instance:
                    rod_template = item_template_service.get_rod_by_id(rod_instance.rod_id)
                    if rod_template:
                        # 计算精炼后的最大耐久度
                        if rod_template.durability is not None:
                            refined_max_durability = int(rod_template.durability * (1.5 ** (max(rod_instance.refine_level, 1) - 1)))
                        else:
                            refined_max_durability = None

                        # 如果实例是无限耐久，则上限也视为 None
                        if rod_instance.current_durability is None:
                            refined_max_durability = None

                        equipped_rod = {
                            "name": rod_template.name,
                            "rarity": rod_template.rarity,
                            "refine_level": rod_instance.refine_level,
                            "current_durability": rod_instance.current_durability,
                            "max_durability": refined_max_durability
                        }
            except Exception as e:
                logger.warning(f"获取装备鱼竿信息失败: {e}")
        
        # 获取装备的饰品信息
        equipped_accessory = None
        if user.equipped_accessory_instance_id and inventory_service and item_template_service:
            try:
                accessory_instance = inventory_service.inventory_repo.get_user_accessory_instance_by_id(user_id, user.equipped_accessory_instance_id)
                if accessory_instance:
                    accessory_template = item_template_service.get_accessory_by_id(accessory_instance.accessory_id)
                    if accessory_template:
                        equipped_accessory = {
                            "name": accessory_template.name,
                            "rarity": accessory_template.rarity,
                            "refine_level": accessory_instance.refine_level
                        }
            except Exception as e:
                logger.warning(f"获取装备饰品信息失败: {e}")
        
        # 获取当前鱼饵信息
        current_bait = None
        if user.current_bait_id and inventory_service and item_template_service:
            try:
                bait_template = item_template_service.get_bait_by_id(user.current_bait_id)
                if bait_template:
                    # 获取用户的鱼饵库存
                    bait_inventory = inventory_service.inventory_repo.get_user_bait_inventory(user_id)
                    bait_quantity = bait_inventory.get(user.current_bait_id, 0)
                    current_bait = {
                        "name": bait_template.name,
                        "rarity": bait_template.rarity,
                        "quantity": bait_quantity
                    }
            except Exception as e:
                logger.warning(f"获取当前鱼饵信息失败: {e}")

        # 获取钓鱼区域信息
        fishing_zone = None
        if user.fishing_zone_id and inventory_service:
            try:
                zone = inventory_service.inventory_repo.get_zone_by_id(user.fishing_zone_id)
                if zone:
                    fishing_zone = {
                        "name": zone.name,
                        "description": zone.description,
                        "rare_fish_quota": getattr(zone, 'daily_rare_fish_quota', 0),
                        "rare_fish_caught": getattr(zone, 'rare_fish_caught_today', 0)
                    }
            except Exception as e:
                logger.warning(f"获取钓鱼区域信息失败: {e}")

        # 检查今日是否签到
        signed_in_today = False
        if user.last_login_time:
            today = get_now().date()
            last_login_date = user.last_login_time.date() if hasattr(user.last_login_time, 'date') else user.last_login_time
            signed_in_today = (last_login_date == today)

        # 获取擦弹剩余次数
        wipe_bomb_remaining = 0
        try:
            game_mechanics_service = current_app.config.get("GAME_MECHANICS_SERVICE")
            if game_mechanics_service:
                # 使用游戏机制服务获取擦弹剩余次数
                wipe_result = game_mechanics_service.get_wipe_bomb_remaining(user_id)
                if wipe_result.get("success"):
                    wipe_bomb_remaining = wipe_result.get("remaining", 0)
        except Exception as e:
            logger.warning(f"获取擦弹剩余次数失败: {e}")

        # 获取鱼塘信息
        pond_info = None
        try:
            if inventory_service:
                # 使用背包服务获取鱼塘信息
                fish_pond = inventory_service.get_user_fish_pond(user_id)
                if fish_pond.get("success"):
                    pond_data = fish_pond.get("data", {})
                    pond_info = {
                        "total_count": pond_data.get("total_count", 0),
                        "total_value": pond_data.get("total_value", 0)
                    }
        except Exception as e:
            logger.warning(f"获取鱼塘信息失败: {e}")

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
            "equipped_rod": equipped_rod,
            "equipped_accessory": equipped_accessory,
            "current_bait": current_bait,
            "fishing_zone": fishing_zone,
            "signed_in_today": signed_in_today,
            "wipe_bomb_remaining": wipe_bomb_remaining,
            "pond_info": pond_info,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login_time": user.last_login_time.isoformat() if user.last_login_time else None
        }
        
        return jsonify({"success": True, "data": user_data})
        
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        return jsonify({"success": False, "message": "获取用户信息失败"})


@game_bp.route("/game/api/fishing/cooldown", methods=["GET"])
@game_login_required
async def api_get_fishing_cooldown():
    """获取钓鱼冷却状态"""
    try:
        user_id = session.get("game_user_id")
        fishing_service = current_app.config.get("FISHING_SERVICE")
        
        if not fishing_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        # 获取用户信息
        user_repo = current_app.config.get("USER_SERVICE").user_repo
        user = user_repo.get_by_id(user_id)
        
        if not user:
            return jsonify({"success": False, "message": "用户不存在"})
        
        # 计算冷却时间
        fishing_config = fishing_service.config.get("fishing", {})
        cooldown = fishing_config.get("cooldown_seconds", 180)
        
        now = get_now()
        if user.last_fishing_time and user.last_fishing_time.year > 1:
            time_since_last_fishing = (now - user.last_fishing_time).total_seconds()
            
            # 检查用户是否装备了海洋之心（减少冷却时间）
            inventory_service = current_app.config.get("INVENTORY_SERVICE")
            if inventory_service:
                equipped_accessory = inventory_service.inventory_repo.get_user_equipped_accessory(user_id)
                if equipped_accessory:
                    item_template_service = current_app.config.get("ITEM_TEMPLATE_SERVICE")
                    if item_template_service:
                        accessory_template = item_template_service.get_accessory_by_id(equipped_accessory.accessory_id)
                        if accessory_template and accessory_template.name == "海洋之心":
                            # 海洋之心装备时，CD时间减半
                            cooldown = cooldown / 2
            
            remaining_time = max(0, cooldown - time_since_last_fishing)
            
            return jsonify({
                "success": True,
                "data": {
                    "is_on_cooldown": remaining_time > 0,
                    "remaining_seconds": int(remaining_time),
                    "cooldown_seconds": int(cooldown),
                    "last_fishing_time": user.last_fishing_time.isoformat() if user.last_fishing_time else None
                }
            })
        else:
            return jsonify({
                "success": True,
                "data": {
                    "is_on_cooldown": False,
                    "remaining_seconds": 0,
                    "cooldown_seconds": int(cooldown),
                    "last_fishing_time": None
                }
            })
        
    except Exception as e:
        logger.error(f"获取钓鱼冷却状态失败: {e}")
        return jsonify({"success": False, "message": "获取钓鱼冷却状态失败"})


@game_bp.route("/game/api/fishing/cast", methods=["POST"])
@game_login_required
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
@game_login_required
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
@game_login_required
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
@game_login_required
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
        result = fishing_zone_service.switch_zone(user_id, zone_id)
        
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
@game_login_required
async def api_get_inventory(item_type):
    """获取背包数据"""
    try:
        user_id = session.get("game_user_id")
        inventory_service = current_app.config.get("INVENTORY_SERVICE")
        
        if not inventory_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        # 根据类型获取不同的背包数据
        if item_type == "fish":
            result = inventory_service.get_user_fish_pond(user_id)
        elif item_type == "rods":
            result = inventory_service.get_user_rod_inventory(user_id)
        elif item_type == "accessories":
            result = inventory_service.get_user_accessory_inventory(user_id)
        elif item_type == "items":
            result = inventory_service.get_user_item_inventory(user_id)
        elif item_type == "baits":
            result = inventory_service.get_user_bait_inventory(user_id)
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
@game_login_required
async def api_equip_item():
    """装备物品"""
    try:
        data = await request.get_json()
        item_type = data.get("item_type")
        item_id = data.get("item_id")
        
        user_id = session.get("game_user_id")
        inventory_service = current_app.config.get("INVENTORY_SERVICE")
        
        if not inventory_service:
            return jsonify({"success": False, "message": "服务不可用"})
            
        result = inventory_service.equip_item(user_id, item_id, item_type)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"装备物品失败: {e}", exc_info=True)
        return jsonify({"success": False, "message": "装备物品失败"})

@game_bp.route("/game/api/inventory/unequip", methods=["POST"])
@game_login_required
async def api_unequip_item():
    """卸下物品"""
    try:
        data = await request.get_json()
        item_type = data.get("item_type")
        
        user_id = session.get("game_user_id")
        inventory_service = current_app.config.get("INVENTORY_SERVICE")
        
        if not inventory_service:
            return jsonify({"success": False, "message": "服务不可用"})
            
        result = inventory_service.unequip_item(user_id, item_type)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"卸下物品失败: {e}", exc_info=True)
        return jsonify({"success": False, "message": "卸下物品失败"})


@game_bp.route("/game/api/inventory/lock", methods=["POST"])
@game_login_required
async def api_lock_item():
    """锁定物品"""
    try:
        data = await request.get_json()
        item_type = data.get("item_type")
        instance_id = data.get("instance_id")
        
        user_id = session.get("game_user_id")
        inventory_service = current_app.config.get("INVENTORY_SERVICE")
        
        if not inventory_service:
            return jsonify({"success": False, "message": "服务不可用"})
            
        if item_type == "rod":
            result = inventory_service.lock_rod(user_id, instance_id)
        elif item_type == "accessory":
            result = inventory_service.lock_accessory(user_id, instance_id)
        else:
            result = {"success": False, "message": "不支持的物品类型"}
            
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"锁定物品失败: {e}", exc_info=True)
        return jsonify({"success": False, "message": "锁定物品失败"})

@game_bp.route("/game/api/inventory/unlock", methods=["POST"])
@game_login_required
async def api_unlock_item():
    """解锁物品"""
    try:
        data = await request.get_json()
        item_type = data.get("item_type")
        instance_id = data.get("instance_id")
        
        user_id = session.get("game_user_id")
        inventory_service = current_app.config.get("INVENTORY_SERVICE")
        
        if not inventory_service:
            return jsonify({"success": False, "message": "服务不可用"})
            
        if item_type == "rod":
            result = inventory_service.unlock_rod(user_id, instance_id)
        elif item_type == "accessory":
            result = inventory_service.unlock_accessory(user_id, instance_id)
        else:
            result = {"success": False, "message": "不支持的物品类型"}
            
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"解锁物品失败: {e}", exc_info=True)
        return jsonify({"success": False, "message": "解锁物品失败"})


@game_bp.route("/game/api/inventory/refine", methods=["POST"])
@game_login_required
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
        result = inventory_service.refine(user_id, item_id, item_type)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"精炼失败: {e}")
        return jsonify({"success": False, "message": "精炼失败，请稍后重试"})


@game_bp.route("/game/api/inventory/sell", methods=["POST"])
@game_login_required
async def api_sell_item():
    """出售物品"""
    try:
        data = await request.get_json()
        item_type = data.get("item_type")
        instance_id = data.get("instance_id")
        quantity = data.get("quantity", 1)
        
        user_id = session.get("game_user_id")
        inventory_service = current_app.config.get("INVENTORY_SERVICE")
        
        if not inventory_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = inventory_service.sell_equipment(user_id, instance_id, item_type)
        
        if result.get("success"):
            return jsonify({
                "success": True,
                "data": result
            })
        else:
            return jsonify({
                "success": False,
                "message": result.get("message", "出售失败")
            })
        
    except Exception as e:
        logger.error(f"出售失败: {e}")
        return jsonify({"success": False, "message": "出售失败，请稍后重试"})


@game_bp.route("/game/api/inventory/sell-all-fish", methods=["POST"])
@game_login_required
async def api_sell_all_fish():
    """批量出售所有鱼类"""
    try:
        user_id = session.get("game_user_id")
        inventory_service = current_app.config.get("INVENTORY_SERVICE")
        
        result = inventory_service.sell_all_fish(user_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"批量出售鱼类失败: {e}")
        return jsonify({"success": False, "message": "批量出售失败，请稍后重试"})


@game_bp.route("/game/api/inventory/sell-keep-fish", methods=["POST"])
@game_login_required
async def api_sell_keep_fish():
    """保留出售鱼类（每种保留一条）"""
    try:
        user_id = session.get("game_user_id")
        inventory_service = current_app.config.get("INVENTORY_SERVICE")
        
        result = inventory_service.sell_all_fish(user_id, keep_one=True)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"保留出售鱼类失败: {e}")
        return jsonify({"success": False, "message": "保留出售失败，请稍后重试"})


@game_bp.route("/game/api/inventory/sell-all-rods", methods=["POST"])
@game_login_required
async def api_sell_all_rods():
    """批量出售所有鱼竿"""
    try:
        user_id = session.get("game_user_id")
        inventory_service = current_app.config.get("INVENTORY_SERVICE")
        
        result = inventory_service.sell_all_rods(user_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"批量出售鱼竿失败: {e}")
        return jsonify({"success": False, "message": "批量出售失败，请稍后重试"})


@game_bp.route("/game/api/inventory/sell-all-accessories", methods=["POST"])
@game_login_required
async def api_sell_all_accessories():
    """批量出售所有饰品"""
    try:
        user_id = session.get("game_user_id")
        inventory_service = current_app.config.get("INVENTORY_SERVICE")
        
        result = inventory_service.sell_all_accessories(user_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"批量出售饰品失败: {e}")
        return jsonify({"success": False, "message": "批量出售失败，请稍后重试"})


@game_bp.route("/game/api/shops", methods=["GET"])
@game_login_required
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
@game_login_required
async def game_api_get_shop_items(shop_id):
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
@game_login_required
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
        result = shop_service.purchase_item(user_id, item_id, quantity)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"购买失败: {e}")
        return jsonify({"success": False, "message": "购买失败，请稍后重试"})


# ========== 市场系统 API ==========

@game_bp.route("/game/api/market/listings", methods=["GET"])
@game_login_required
async def api_get_market_listings():
    """获取市场商品列表"""
    try:
        market_service = current_app.config.get("MARKET_SERVICE")
        
        if not market_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = market_service.get_market_listings()
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取市场商品失败: {e}")
        return jsonify({"success": False, "message": "获取市场商品失败"})


@game_bp.route("/game/api/market/my-listings", methods=["GET"])
@game_login_required
async def api_get_my_listings():
    """获取我的上架商品"""
    try:
        user_id = session.get("game_user_id")
        market_service = current_app.config.get("MARKET_SERVICE")
        
        if not market_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = market_service.get_user_listings(user_id)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取我的上架商品失败: {e}")
        return jsonify({"success": False, "message": "获取我的上架商品失败"})


@game_bp.route("/game/api/market/list", methods=["POST"])
@game_login_required
async def api_list_item():
    """上架商品"""
    try:
        data = await request.get_json()
        item_type = data.get("item_type")
        item_id = data.get("item_id")
        quantity = data.get("quantity", 1)
        price = data.get("price")
        
        user_id = session.get("game_user_id")
        market_service = current_app.config.get("MARKET_SERVICE")
        
        if not market_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = market_service.list_item(user_id, item_type, item_id, quantity, price)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"上架商品失败: {e}")
        return jsonify({"success": False, "message": "上架商品失败，请稍后重试"})


@game_bp.route("/game/api/market/buy", methods=["POST"])
@game_login_required
async def api_buy_item():
    """购买商品"""
    try:
        data = await request.get_json()
        listing_id = data.get("listing_id")
        quantity = data.get("quantity", 1)
        
        user_id = session.get("game_user_id")
        market_service = current_app.config.get("MARKET_SERVICE")
        
        if not market_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = market_service.buy_item(user_id, listing_id, quantity)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"购买商品失败: {e}")
        return jsonify({"success": False, "message": "购买商品失败，请稍后重试"})


@game_bp.route("/game/api/market/remove", methods=["POST"])
@game_login_required
async def api_remove_listing():
    """下架商品"""
    try:
        data = await request.get_json()
        listing_id = data.get("listing_id")
        
        user_id = session.get("game_user_id")
        market_service = current_app.config.get("MARKET_SERVICE")
        
        if not market_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = market_service.remove_listing(user_id, listing_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"下架商品失败: {e}")
        return jsonify({"success": False, "message": "下架商品失败，请稍后重试"})


@game_bp.route("/game/api/market/remove-all", methods=["POST"])
@game_login_required
async def api_remove_all_listings():
    """批量下架所有商品"""
    try:
        user_id = session.get("game_user_id")
        market_service = current_app.config.get("MARKET_SERVICE")
        
        if not market_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = market_service.remove_all_listings(user_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"批量下架失败: {e}")
        return jsonify({"success": False, "message": "批量下架失败，请稍后重试"})


# ========== 抽卡系统 API ==========

@game_bp.route("/game/api/gacha/pools", methods=["GET"])
@game_login_required
async def api_get_gacha_pools():
    """获取所有卡池"""
    try:
        gacha_service = current_app.config.get("GACHA_SERVICE")
        
        if not gacha_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        pools = gacha_service.get_all_pools()
        
        return jsonify({
            "success": True,
            "data": pools
        })
        
    except Exception as e:
        logger.error(f"获取卡池列表失败: {e}")
        return jsonify({"success": False, "message": "获取卡池列表失败"})


@game_bp.route("/game/api/gacha/pools/<int:pool_id>", methods=["GET"])
@game_login_required
async def api_get_gacha_pool_details(pool_id):
    """获取卡池详情"""
    try:
        gacha_service = current_app.config.get("GACHA_SERVICE")
        
        if not gacha_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = gacha_service.get_pool_details(pool_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取卡池详情失败: {e}")
        return jsonify({"success": False, "message": "获取卡池详情失败"})


@game_bp.route("/game/api/gacha/draw", methods=["POST"])
@game_login_required
async def api_gacha_draw():
    """单次抽卡"""
    try:
        data = await request.get_json()
        pool_id = data.get("pool_id")
        
        if not pool_id:
            return jsonify({"success": False, "message": "请选择卡池"})
        
        user_id = session.get("game_user_id")
        gacha_service = current_app.config.get("GACHA_SERVICE")
        
        if not gacha_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = gacha_service.perform_draw(user_id, pool_id, num_draws=1)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"抽卡失败: {e}")
        return jsonify({"success": False, "message": "抽卡失败，请稍后重试"})


@game_bp.route("/game/api/gacha/draw-ten", methods=["POST"])
@game_login_required
async def api_gacha_draw_ten():
    """十连抽卡"""
    try:
        data = await request.get_json()
        pool_id = data.get("pool_id")
        
        if not pool_id:
            return jsonify({"success": False, "message": "请选择卡池"})
        
        user_id = session.get("game_user_id")
        gacha_service = current_app.config.get("GACHA_SERVICE")
        
        if not gacha_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = gacha_service.perform_draw(user_id, pool_id, num_draws=10)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"十连抽卡失败: {e}")
        return jsonify({"success": False, "message": "十连抽卡失败，请稍后重试"})


@game_bp.route("/game/api/gacha/history", methods=["GET"])
@game_login_required
async def api_get_gacha_history():
    """获取抽卡记录"""
    try:
        user_id = session.get("game_user_id")
        gacha_service = current_app.config.get("GACHA_SERVICE")
        
        if not gacha_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = gacha_service.get_user_gacha_history(user_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取抽卡记录失败: {e}")
        return jsonify({"success": False, "message": "获取抽卡记录失败"})


@game_bp.route("/game/api/gacha/wipe-bomb", methods=["POST"])
@game_login_required
async def api_gacha_wipe_bomb():
    """擦弹功能"""
    try:
        data = await request.get_json()
        contribution_amount = data.get("contribution_amount")
        
        if not contribution_amount:
            return jsonify({"success": False, "message": "请输入投入金额"})
        
        user_id = session.get("game_user_id")
        game_mechanics_service = current_app.config.get("GAME_MECHANICS_SERVICE")
        
        if not game_mechanics_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = game_mechanics_service.perform_wipe_bomb(user_id, int(contribution_amount))
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"擦弹失败: {e}")
        return jsonify({"success": False, "message": "擦弹失败，请稍后重试"})


@game_bp.route("/game/api/gacha/wipe-bomb/history", methods=["GET"])
@game_login_required
async def api_get_wipe_bomb_history():
    """获取擦弹记录"""
    try:
        user_id = session.get("game_user_id")
        game_mechanics_service = current_app.config.get("GAME_MECHANICS_SERVICE")
        
        if not game_mechanics_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = game_mechanics_service.get_wipe_bomb_history(user_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取擦弹记录失败: {e}")
        return jsonify({"success": False, "message": "获取擦弹记录失败"})


# ========== 水族箱系统 API ==========

@game_bp.route("/game/aquarium")
@game_login_required
async def game_aquarium():
    """水族箱页面"""
    return await render_template("game/aquarium.html")


@game_bp.route("/game/api/aquarium", methods=["GET"])
@game_login_required
async def api_get_aquarium():
    """获取水族箱信息"""
    try:
        user_id = session.get("game_user_id")
        aquarium_service = current_app.config.get("AQUARIUM_SERVICE")
        
        if not aquarium_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = aquarium_service.get_user_aquarium(user_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取水族箱信息失败: {e}")
        return jsonify({"success": False, "message": "获取水族箱信息失败"})


@game_bp.route("/game/api/aquarium/add", methods=["POST"])
@game_login_required
async def api_add_to_aquarium():
    """添加鱼到水族箱"""
    try:
        data = await request.get_json()
        fish_id = data.get("fish_id")
        quantity = data.get("quantity", 1)
        
        if not fish_id:
            return jsonify({"success": False, "message": "请选择鱼类"})
        
        user_id = session.get("game_user_id")
        aquarium_service = current_app.config.get("AQUARIUM_SERVICE")
        
        if not aquarium_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = aquarium_service.add_fish_to_aquarium(user_id, fish_id, quantity)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"添加鱼到水族箱失败: {e}")
        return jsonify({"success": False, "message": "添加鱼到水族箱失败，请稍后重试"})


@game_bp.route("/game/api/aquarium/remove", methods=["POST"])
@game_login_required
async def api_remove_from_aquarium():
    """从水族箱移出鱼"""
    try:
        data = await request.get_json()
        fish_id = data.get("fish_id")
        quantity = data.get("quantity", 1)
        
        if not fish_id:
            return jsonify({"success": False, "message": "请选择鱼类"})
        
        user_id = session.get("game_user_id")
        aquarium_service = current_app.config.get("AQUARIUM_SERVICE")
        
        if not aquarium_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = aquarium_service.remove_fish_from_aquarium(user_id, fish_id, quantity)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"从水族箱移出鱼失败: {e}")
        return jsonify({"success": False, "message": "从水族箱移出鱼失败，请稍后重试"})


@game_bp.route("/game/api/aquarium/upgrade", methods=["POST"])
@game_login_required
async def api_upgrade_aquarium():
    """升级水族箱"""
    try:
        user_id = session.get("game_user_id")
        aquarium_service = current_app.config.get("AQUARIUM_SERVICE")
        
        if not aquarium_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = aquarium_service.upgrade_aquarium(user_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"升级水族箱失败: {e}")
        return jsonify({"success": False, "message": "升级水族箱失败，请稍后重试"})


# ========== 交易所系统 API ==========

@game_bp.route("/game/api/exchange/open-account", methods=["POST"])
@game_login_required
async def api_open_exchange_account():
    """开通交易所账户"""
    try:
        user_id = session.get("game_user_id")
        exchange_service = current_app.config.get("EXCHANGE_SERVICE")
        
        if not exchange_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = exchange_service.open_exchange_account(user_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"开通交易所账户失败: {e}")
        return jsonify({"success": False, "message": "开通交易所账户失败，请稍后重试"})


@game_bp.route("/game/api/exchange/status", methods=["GET"])
@game_login_required
async def api_get_exchange_status():
    """获取市场状态"""
    try:
        exchange_service = current_app.config.get("EXCHANGE_SERVICE")
        
        if not exchange_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = exchange_service.get_market_status()
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取市场状态失败: {e}")
        return jsonify({"success": False, "message": "获取市场状态失败"})


@game_bp.route("/game/api/exchange/inventory", methods=["GET"])
@game_login_required
async def api_get_exchange_inventory():
    """获取持仓信息"""
    try:
        user_id = session.get("game_user_id")
        exchange_service = current_app.config.get("EXCHANGE_SERVICE")
        
        if not exchange_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = exchange_service.get_user_inventory(user_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取持仓信息失败: {e}")
        return jsonify({"success": False, "message": "获取持仓信息失败"})


@game_bp.route("/game/api/exchange/buy", methods=["POST"])
@game_login_required
async def api_exchange_buy():
    """买入商品"""
    try:
        data = await request.get_json()
        commodity_name = data.get("commodity_name")
        quantity = data.get("quantity", 1)
        
        if not commodity_name or not quantity:
            return jsonify({"success": False, "message": "请选择商品和数量"})
        
        user_id = session.get("game_user_id")
        exchange_service = current_app.config.get("EXCHANGE_SERVICE")
        
        if not exchange_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        # 获取市场状态以获取商品ID和价格
        market_status = exchange_service.get_market_status()
        if not market_status.get("success"):
            return jsonify({"success": False, "message": "获取市场状态失败"})
        
        # 查找商品ID
        commodity_id = None
        for cid, info in market_status["commodities"].items():
            if info["name"] == commodity_name:
                commodity_id = cid
                break
        
        if not commodity_id:
            return jsonify({"success": False, "message": f"找不到商品: {commodity_name}"})
        
        current_price = market_status["prices"].get(commodity_id, 0)
        if current_price <= 0:
            return jsonify({"success": False, "message": f"商品 {commodity_name} 价格异常"})
        
        result = exchange_service.purchase_commodity(user_id, commodity_id, quantity, current_price)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"买入商品失败: {e}")
        return jsonify({"success": False, "message": "买入商品失败，请稍后重试"})


@game_bp.route("/game/api/exchange/sell", methods=["POST"])
@game_login_required
async def api_exchange_sell():
    """卖出商品"""
    try:
        data = await request.get_json()
        commodity_name = data.get("commodity_name")
        quantity = data.get("quantity", 1)
        
        if not commodity_name or not quantity:
            return jsonify({"success": False, "message": "请选择商品和数量"})
        
        user_id = session.get("game_user_id")
        exchange_service = current_app.config.get("EXCHANGE_SERVICE")
        
        if not exchange_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        # 获取市场状态以获取商品ID和价格
        market_status = exchange_service.get_market_status()
        if not market_status.get("success"):
            return jsonify({"success": False, "message": "获取市场状态失败"})
        
        # 查找商品ID
        commodity_id = None
        for cid, info in market_status["commodities"].items():
            if info["name"] == commodity_name:
                commodity_id = cid
                break
        
        if not commodity_id:
            return jsonify({"success": False, "message": f"找不到商品: {commodity_name}"})
        
        current_price = market_status["prices"].get(commodity_id, 0)
        if current_price <= 0:
            return jsonify({"success": False, "message": f"商品 {commodity_name} 价格异常"})
        
        result = exchange_service.sell_commodity(user_id, commodity_id, quantity, current_price)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"卖出商品失败: {e}")
        return jsonify({"success": False, "message": "卖出商品失败，请稍后重试"})


@game_bp.route("/game/api/exchange/clear", methods=["POST"])
@game_login_required
async def api_exchange_clear():
    """清仓"""
    try:
        data = await request.get_json()
        commodity_name = data.get("commodity_name")  # 可选，如果指定则只清空该商品
        
        user_id = session.get("game_user_id")
        exchange_service = current_app.config.get("EXCHANGE_SERVICE")
        
        if not exchange_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        if (commodity_name):
            # 清空指定商品
            market_status = exchange_service.get_market_status()
            if not market_status.get("success"):
                return jsonify({"success": False, "message": "获取市场状态失败"})
            
            commodity_id = None
            for cid, info in market_status["commodities"].items():
                if info["name"] == commodity_name:
                    commodity_id = cid
                    break
            
            if not commodity_id:
                return jsonify({"success": False, "message": f"找不到商品: {commodity_name}"})
            
            result = exchange_service.clear_commodity_inventory(user_id, commodity_id)
        else:
            # 清空所有商品
            result = exchange_service.clear_all_inventory(user_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"清仓失败: {e}")
        return jsonify({"success": False, "message": "清仓失败，请稍后重试"})


# ========== 社交系统 API ==========

@game_bp.route("/game/api/social/ranking", methods=["GET"])
@game_login_required
async def api_get_ranking():
    """获取排行榜"""
    try:
        user_service = current_app.config.get("USER_SERVICE")
        
        if not user_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        leaderboard_data = user_service.get_leaderboard_data()
        
        return jsonify({
            "success": True,
            "data": leaderboard_data
        })
        
    except Exception as e:
        logger.error(f"获取排行榜失败: {e}")
        return jsonify({"success": False, "message": "获取排行榜失败"})


@game_bp.route("/game/api/social/steal", methods=["POST"])
@game_login_required
async def api_steal_fish():
    """偷鱼功能"""
    try:
        data = await request.get_json()
        target_id = data.get("target_id")
        
        if not target_id:
            return jsonify({"success": False, "message": "请指定目标用户"})
        
        user_id = session.get("game_user_id")
        game_mechanics_service = current_app.config.get("GAME_MECHANICS_SERVICE")
        
        if not game_mechanics_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = game_mechanics_service.steal_fish(user_id, target_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"偷鱼失败: {e}")
        return jsonify({"success": False, "message": "偷鱼失败，请稍后重试"})


@game_bp.route("/game/api/social/dispel", methods=["POST"])
@game_login_required
async def api_dispel_protection():
    """驱灵功能"""
    try:
        data = await request.get_json()
        target_id = data.get("target_id")
        
        if not target_id:
            return jsonify({"success": False, "message": "请指定目标用户"})
        
        user_id = session.get("game_user_id")
        game_mechanics_service = current_app.config.get("GAME_MECHANICS_SERVICE")
        
        if not game_mechanics_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        # 检查是否有驱灵香
        inventory_service = current_app.config.get("INVENTORY_SERVICE")
        if not inventory_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        user_inventory = inventory_service.get_user_item_inventory(user_id)
        dispel_items = [item for item in user_inventory.get("items", []) 
                       if item.get("effect_type") == "STEAL_PROTECTION_REMOVAL"]
        
        if not dispel_items:
            return jsonify({"success": False, "message": "你没有驱灵香，无法使用此功能"})
        
        # 检查目标是否有海灵守护效果
        dispel_result = game_mechanics_service.check_steal_protection(target_id)
        if not dispel_result.get("has_protection"):
            return jsonify({"success": False, "message": f"【{dispel_result.get('target_name', '目标')}】没有海灵守护效果，无需驱散"})
        
        # 扣除驱灵香
        dispel_item = dispel_items[0]
        user_service = current_app.config.get("USER_SERVICE")
        remove_result = user_service.remove_item_from_user_inventory(user_id, "item", dispel_item["item_id"], 1)
        if not remove_result.get("success"):
            return jsonify({"success": False, "message": f"扣除驱灵香失败：{remove_result.get('message', '未知错误')}"})
        
        # 驱散目标的海灵守护buff
        result = game_mechanics_service.dispel_steal_protection(target_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"驱灵失败: {e}")
        return jsonify({"success": False, "message": "驱灵失败，请稍后重试"})


@game_bp.route("/game/api/social/titles", methods=["GET"])
@game_login_required
async def api_get_titles():
    """获取称号列表"""
    try:
        user_id = session.get("game_user_id")
        user_service = current_app.config.get("USER_SERVICE")
        
        if not user_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = user_service.get_user_titles(user_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取称号列表失败: {e}")
        return jsonify({"success": False, "message": "获取称号列表失败"})


@game_bp.route("/game/api/social/titles/use", methods=["POST"])
@game_login_required
async def api_use_title():
    """使用称号"""
    try:
        data = await request.get_json()
        title_id = data.get("title_id")
        
        if not title_id:
            return jsonify({"success": False, "message": "请选择称号"})
        
        user_id = session.get("game_user_id")
        user_service = current_app.config.get("USER_SERVICE")
        
        if not user_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = user_service.use_title(user_id, int(title_id))
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"使用称号失败: {e}")
        return jsonify({"success": False, "message": "使用称号失败，请稍后重试"})


@game_bp.route("/game/api/social/achievements", methods=["GET"])
@game_login_required
async def api_get_achievements():
    """获取成就列表"""
    try:
        user_id = session.get("game_user_id")
        achievement_service = current_app.config.get("ACHIEVEMENT_SERVICE")
        
        if not achievement_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = achievement_service.get_user_achievements(user_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取成就列表失败: {e}")
        return jsonify({"success": False, "message": "获取成就列表失败"})


# ========== 增强功能 API ==========

@game_bp.route("/game/api/user/sign-in", methods=["POST"])
@game_login_required
async def api_sign_in():
    """签到功能"""
    try:
        user_id = session.get("game_user_id")
        user_service = current_app.config.get("USER_SERVICE")
        
        if not user_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = user_service.daily_sign_in(user_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"签到失败: {e}")
        return jsonify({"success": False, "message": "签到失败，请稍后重试"})


@game_bp.route("/game/api/fishing/history", methods=["GET"])
@game_login_required
async def api_get_fishing_history():
    """获取钓鱼记录"""
    try:
        user_id = session.get("game_user_id")
        log_repo = current_app.config.get("LOG_REPO")
        
        if not log_repo:
            return jsonify({"success": False, "message": "服务不可用"})
        
        # 获取最近的钓鱼记录
        fishing_records = log_repo.get_fishing_records(user_id, limit=20)
        
        # 转换为字典格式
        logs = []
        for record in fishing_records:
            # 处理timestamp字段，确保是字符串格式
            timestamp_str = record.timestamp
            if hasattr(record.timestamp, 'isoformat'):
                timestamp_str = record.timestamp.isoformat()
            elif isinstance(record.timestamp, str):
                timestamp_str = record.timestamp
            
            logs.append({
                "record_id": record.record_id,
                "user_id": record.user_id,
                "fish_id": record.fish_id,
                "weight": record.weight,
                "value": record.value,
                "timestamp": timestamp_str,
                "rod_instance_id": record.rod_instance_id,
                "accessory_instance_id": record.accessory_instance_id,
                "bait_id": record.bait_id,
                "location_id": record.location_id,
                "is_king_size": record.is_king_size
            })
        
        return jsonify({
            "success": True,
            "data": {"logs": logs}
        })
        
    except Exception as e:
        logger.error(f"获取钓鱼记录失败: {e}")
        return jsonify({"success": False, "message": "获取钓鱼记录失败"})


@game_bp.route("/game/api/fishing/pokedex", methods=["GET"])
@game_login_required
async def api_get_pokedex():
    """获取鱼类图鉴"""
    try:
        user_id = session.get("game_user_id")
        fishing_service = current_app.config.get("FISHING_SERVICE")
        
        if not fishing_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = fishing_service.get_user_pokedex(user_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取鱼类图鉴失败: {e}")
        return jsonify({"success": False, "message": "获取鱼类图鉴失败"})


@game_bp.route("/game/api/inventory/use-item", methods=["POST"])
@game_login_required
async def api_use_item():
    """使用道具"""
    try:
        data = await request.get_json()
        item_id = data.get("item_id")
        quantity = data.get("quantity", 1)
        
        if not item_id:
            return jsonify({"success": False, "message": "请选择道具"})
        
        user_id = session.get("game_user_id")
        inventory_service = current_app.config.get("INVENTORY_SERVICE")
        
        if not inventory_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = inventory_service.use_item(user_id, item_id, quantity)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"使用道具失败: {e}")
        return jsonify({"success": False, "message": "使用道具失败，请稍后重试"})


@game_bp.route("/game/api/pond/upgrade", methods=["POST"])
@game_login_required
async def api_upgrade_pond():
    """升级鱼塘"""
    try:
        user_id = session.get("game_user_id")
        inventory_service = current_app.config.get("INVENTORY_SERVICE")
        
        if not inventory_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = inventory_service.upgrade_fish_pond(user_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"升级鱼塘失败: {e}")
        return jsonify({"success": False, "message": "升级鱼塘失败，请稍后重试"})


@game_bp.route("/game/api/user/tax-records", methods=["GET"])
@game_login_required
async def api_get_tax_records():
    """获取税收记录"""
    try:
        user_id = session.get("game_user_id")
        user_service = current_app.config.get("USER_SERVICE")
        
        if not user_service:
            return jsonify({"success": False, "message": "服务不可用"})
        
        result = user_service.get_tax_record(user_id)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取税收记录失败: {e}")
        return jsonify({"success": False, "message": "获取税收记录失败"})
