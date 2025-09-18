import functools
import os
import traceback
from typing import Dict, Any

from quart import (
    Quart, render_template, request, redirect, url_for, session, flash,
    Blueprint, current_app
)
from astrbot.api import logger


admin_bp = Blueprint(
    "admin_bp",
    __name__,
    template_folder="templates",
    static_folder="static",
)

# 工厂函数现在接收服务实例
def create_app(secret_key: str, services: Dict[str, Any]):
    """
    创建并配置Quart应用实例。

    Args:
        secret_key: 用于session加密的密钥。
        services: 关键字参数，包含所有需要注入的服务实例。
    """
    app = Quart(__name__)
    app.secret_key = os.urandom(24)
    app.config["SECRET_LOGIN_KEY"] = secret_key

    # 将所有注入的服务实例存入app的配置中，供路由函数使用
    # 键名将转换为大写，例如 'user_service' -> 'USER_SERVICE'
    for service_name, service_instance in services.items():
        app.config[service_name.upper()] = service_instance

    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.route("/")
    def root():
        return redirect(url_for("admin_bp.index"))
    
    @app.route("/favicon.ico")
    def favicon():
        # 返回404而不是500错误
        from quart import abort
        abort(404)
    
    # 添加全局错误处理器
    @app.errorhandler(404)
    async def handle_404_error(error):
        # 只对非静态资源记录404错误
        if not request.path.startswith('/admin/static/') and request.path != '/favicon.ico':
            logger.error(f"404 Not Found: {request.url} - {request.method}")
        
        # 为API路径返回JSON，为页面返回HTML
        if request.path.startswith('/admin/market/') and request.method in ['POST', 'PUT', 'DELETE']:
            return {"success": False, "message": "API端点不存在"}, 404
        return "Not Found", 404
    
    @app.errorhandler(500)
    async def handle_500_error(error):
        logger.error(f"Internal Server Error: {error}")
        logger.error(traceback.format_exc())
        
        # 为API路径返回JSON，为页面返回HTML
        if request.path.startswith('/admin/market/') and request.method in ['POST', 'PUT', 'DELETE']:
            return {"success": False, "message": "服务器内部错误"}, 500
        return "Internal Server Error", 500
    
    return app

def login_required(f):
    @functools.wraps(f)
    async def decorated_function(*args, **kwargs):
        if "logged_in" not in session:
            return redirect(url_for("admin_bp.login"))
        return await f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @functools.wraps(f)
    async def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            await flash("无权限访问该页面", "danger")
            return redirect(url_for("admin_bp.login"))
        return await f(*args, **kwargs)
    return decorated_function

@admin_bp.route("/login", methods=["GET", "POST"])
async def login():
    if request.method == "POST":
        form = await request.form
        # 从应用配置中获取密钥
        secret_key = current_app.config["SECRET_LOGIN_KEY"]
        if form.get("secret_key") == secret_key:
            session["logged_in"] = True
            # 简单角色标记：现阶段使用同一密钥视为管理员
            session["is_admin"] = True
            await flash("登录成功！", "success")
            return redirect(url_for("admin_bp.index"))
        else:
            await flash("登录失败，请检查密钥！", "danger")
    return await render_template("login.html")

@admin_bp.route("/logout")
async def logout():
    session.pop("logged_in", None)
    await flash("你已成功登出。", "info")
    return redirect(url_for("admin_bp.login"))

@admin_bp.route("/")
@login_required
async def index():
    return await render_template("index.html")

# --- 物品模板管理 (鱼、鱼竿、鱼饵、饰品) ---
# 使用 item_template_service 来处理所有模板相关的CRUD操作

@admin_bp.route("/fish")
@login_required
async def manage_fish():
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    fishes = item_template_service.get_all_fish()
    return await render_template("fish.html", fishes=fishes)

@admin_bp.route("/fish/add", methods=["POST"])
@login_required
async def add_fish():
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    # 注意：服务层应处理来自表单的数据转换和验证
    item_template_service.add_fish_template(form.to_dict())
    await flash("鱼类添加成功！", "success")
    return redirect(url_for("admin_bp.manage_fish"))

@admin_bp.route("/fish/edit/<int:fish_id>", methods=["POST"])
@login_required
async def edit_fish(fish_id):
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    item_template_service.update_fish_template(fish_id, form.to_dict())
    await flash(f"鱼类ID {fish_id} 更新成功！", "success")
    return redirect(url_for("admin_bp.manage_fish"))

@admin_bp.route("/fish/delete/<int:fish_id>", methods=["POST"])
@login_required
async def delete_fish(fish_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    item_template_service.delete_fish_template(fish_id)
    await flash(f"鱼类ID {fish_id} 已删除！", "warning")
    return redirect(url_for("admin_bp.manage_fish"))

# --- 鱼竿管理 (Rods) ---
@admin_bp.route("/rods")
@login_required
async def manage_rods():
    # 从app配置中获取服务实例
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    # 调用服务层方法获取所有鱼竿模板
    items = item_template_service.get_all_rods()
    return await render_template("rods.html", items=items)


@admin_bp.route("/rods/add", methods=["POST"])
@login_required
async def add_rod():
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    # 调用服务层方法添加新的鱼竿模板
    item_template_service.add_rod_template(form.to_dict())
    await flash("鱼竿添加成功！", "success")
    return redirect(url_for("admin_bp.manage_rods"))


@admin_bp.route("/rods/edit/<int:rod_id>", methods=["POST"])
@login_required
async def edit_rod(rod_id):
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    # 调用服务层方法更新指定的鱼竿模板
    item_template_service.update_rod_template(rod_id, form.to_dict())
    await flash(f"鱼竿ID {rod_id} 更新成功！", "success")
    return redirect(url_for("admin_bp.manage_rods"))


@admin_bp.route("/rods/delete/<int:rod_id>", methods=["POST"])
@login_required
async def delete_rod(rod_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    # 调用服务层方法删除指定的鱼竿模板
    item_template_service.delete_rod_template(rod_id)
    await flash(f"鱼竿ID {rod_id} 已删除！", "warning")
    return redirect(url_for("admin_bp.manage_rods"))


# --- 鱼饵管理 (Baits) ---
@admin_bp.route("/baits")
@login_required
async def manage_baits():
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    items = item_template_service.get_all_baits()
    return await render_template("baits.html", items=items)


@admin_bp.route("/baits/add", methods=["POST"])
@login_required
async def add_bait():
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    item_template_service.add_bait_template(form.to_dict())
    await flash("鱼饵添加成功！", "success")
    return redirect(url_for("admin_bp.manage_baits"))


@admin_bp.route("/baits/edit/<int:bait_id>", methods=["POST"])
@login_required
async def edit_bait(bait_id):
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    item_template_service.update_bait_template(bait_id, form.to_dict())
    await flash(f"鱼饵ID {bait_id} 更新成功！", "success")
    return redirect(url_for("admin_bp.manage_baits"))


@admin_bp.route("/baits/delete/<int:bait_id>", methods=["POST"])
@login_required
async def delete_bait(bait_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    item_template_service.delete_bait_template(bait_id)
    await flash(f"鱼饵ID {bait_id} 已删除！", "warning")
    return redirect(url_for("admin_bp.manage_baits"))


# --- 饰品管理 (Accessories) ---
@admin_bp.route("/accessories")
@login_required
async def manage_accessories():
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    items = item_template_service.get_all_accessories()
    return await render_template("accessories.html", items=items)


@admin_bp.route("/accessories/add", methods=["POST"])
@login_required
async def add_accessory():
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    item_template_service.add_accessory_template(form.to_dict())
    await flash("饰品添加成功！", "success")
    return redirect(url_for("admin_bp.manage_accessories"))


@admin_bp.route("/accessories/edit/<int:accessory_id>", methods=["POST"])
@login_required
async def edit_accessory(accessory_id):
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    item_template_service.update_accessory_template(accessory_id, form.to_dict())
    await flash(f"饰品ID {accessory_id} 更新成功！", "success")
    return redirect(url_for("admin_bp.manage_accessories"))


@admin_bp.route("/accessories/delete/<int:accessory_id>", methods=["POST"])
@login_required
async def delete_accessory(accessory_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    item_template_service.delete_accessory_template(accessory_id)
    await flash(f"饰品ID {accessory_id} 已删除！", "warning")
    return redirect(url_for("admin_bp.manage_accessories"))


# --- 抽卡池管理 ---
@admin_bp.route("/gacha")
@login_required
async def manage_gacha():
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    pools = item_template_service.get_all_gacha_pools()
    return await render_template("gacha.html", pools=pools)


@admin_bp.route("/gacha/add", methods=["POST"])
@login_required
async def add_gacha_pool():
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    data = form.to_dict()
    # 将 currency_type/cost_amount 映射到 cost_coins 或 cost_premium_currency
    currency_type = data.get("currency_type", "coins")
    amount = int(data.get("cost_amount", 0) or 0)
    payload = {
        "name": data.get("name"),
        "description": data.get("description"),
        "cost_coins": amount if currency_type == "coins" else 0,
        "cost_premium_currency": amount if currency_type == "premium" else 0,
    }
    item_template_service.add_pool_template(payload)
    await flash("奖池添加成功！", "success")
    return redirect(url_for("admin_bp.manage_gacha"))


@admin_bp.route("/gacha/edit/<int:pool_id>", methods=["POST"])
@login_required
async def edit_gacha_pool(pool_id):
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    data = form.to_dict()
    currency_type = data.get("currency_type", "coins")
    amount = int(data.get("cost_amount", 0) or 0)
    payload = {
        "name": data.get("name"),
        "description": data.get("description"),
        "cost_coins": amount if currency_type == "coins" else 0,
        "cost_premium_currency": amount if currency_type == "premium" else 0,
    }
    item_template_service.update_pool_template(pool_id, payload)
    await flash(f"奖池ID {pool_id} 更新成功！", "success")
    return redirect(url_for("admin_bp.manage_gacha"))


@admin_bp.route("/gacha/delete/<int:pool_id>", methods=["POST"])
@login_required
async def delete_gacha_pool(pool_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    item_template_service.delete_pool_template(pool_id)
    await flash(f"奖池ID {pool_id} 已删除！", "warning")
    return redirect(url_for("admin_bp.manage_gacha"))


# --- 奖池物品详情管理 ---
@admin_bp.route("/gacha/pool/<int:pool_id>")
@login_required
async def manage_gacha_pool_details(pool_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    details = item_template_service.get_pool_details_for_admin(pool_id)

    if not details.get("pool"):
        await flash("找不到指定的奖池！", "danger")
        return redirect(url_for("admin_bp.manage_gacha"))

    enriched_items = []
    for item in details.get("pool").items:
        # 将 dataclass 转换为字典以便修改
        item_dict = item.__dict__
        item_name = "未知物品"
        item_type = item.item_type
        item_id = item.item_id

        # 根据类型从 item_template_service 获取名称
        if item_type == "rod":
            template = item_template_service.item_template_repo.get_rod_by_id(item_id)
            if template:
                item_name = template.name
        elif item_type == "accessory":
            template = item_template_service.item_template_repo.get_accessory_by_id(item_id)
            if template:
                item_name = template.name
        elif item_type == "bait":
            template = item_template_service.item_template_repo.get_bait_by_id(item_id)
            if template:
                item_name = template.name
        elif item_type == "fish":
            template = item_template_service.item_template_repo.get_fish_by_id(item_id)
            if template:
                item_name = template.name
        elif item_type == "titles":
            template = item_template_service.item_template_repo.get_title_by_id(item_id)
            if template:
                item_name = template.name
        elif item_type == "coins":
            item_name = f"{item.quantity} 金币"

        item_dict["item_name"] = item_name  # 添加名称属性
        enriched_items.append(item_dict)

    return await render_template(
        "gacha_pool_details.html",
        pool=details["pool"],
        items=enriched_items,  # 传递丰富化后的物品列表
        all_rods=details["all_rods"],
        all_baits=details["all_baits"],
        all_accessories=details["all_accessories"]
    )


@admin_bp.route("/gacha/pool/<int:pool_id>/add_item", methods=["POST"])
@login_required
async def add_item_to_pool(pool_id):
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    item_template_service.add_item_to_pool(pool_id, form.to_dict())
    await flash("成功向奖池中添加物品！", "success")
    return redirect(url_for("admin_bp.manage_gacha_pool_details", pool_id=pool_id))


@admin_bp.route("/gacha/pool/edit_item/<int:item_id>", methods=["POST"])
@login_required
async def edit_pool_item(item_id):
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    pool_id = request.args.get("pool_id")
    if not pool_id:
        await flash("编辑失败：缺少奖池ID信息。", "danger")
        return redirect(url_for("admin_bp.manage_gacha"))
    item_template_service.update_pool_item(item_id, form.to_dict())
    await flash(f"奖池物品ID {item_id} 更新成功！", "success")
    return redirect(url_for("admin_bp.manage_gacha_pool_details", pool_id=pool_id))


@admin_bp.route("/gacha/pool/delete_item/<int:item_id>", methods=["POST"])
@login_required
async def delete_pool_item(item_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    pool_id = request.args.get("pool_id")
    if not pool_id:
        await flash("删除失败：缺少奖池ID信息。", "danger")
        return redirect(url_for("admin_bp.manage_gacha"))
    item_template_service.delete_pool_item(item_id)
    await flash(f"奖池物品ID {item_id} 已删除！", "warning")
    return redirect(url_for("admin_bp.manage_gacha_pool_details", pool_id=pool_id))


# --- 用户管理 ---
@admin_bp.route("/users")
@login_required
@admin_required
async def manage_users():
    user_service = current_app.config["USER_SERVICE"]
    page = int(request.args.get("page", 1))
    search = request.args.get("search", "")
    
    result = user_service.get_users_for_admin(page=page, per_page=20, search=search or None)
    
    if not result["success"]:
        await flash("获取用户列表失败：" + result.get("message", "未知错误"), "danger")
        return redirect(url_for("admin_bp.index"))
    
    return await render_template(
        "users.html", 
        users=result["users"], 
        pagination=result["pagination"],
        search=search
    )

@admin_bp.route("/users/<user_id>")
@login_required
@admin_required
async def get_user_detail(user_id):
    user_service = current_app.config["USER_SERVICE"]
    result = user_service.get_user_details_for_admin(user_id)
    
    if not result["success"]:
        return {"success": False, "message": result["message"]}, 404
    
    # 将User对象转换为字典以便JSON序列化
    user_dict = {
        "user_id": result["user"].user_id,
        "nickname": result["user"].nickname,
        "coins": result["user"].coins,
        "premium_currency": result["user"].premium_currency,
        "total_fishing_count": result["user"].total_fishing_count,
        "total_weight_caught": result["user"].total_weight_caught,
        "total_coins_earned": result["user"].total_coins_earned,
        "consecutive_login_days": result["user"].consecutive_login_days,
        "fish_pond_capacity": result["user"].fish_pond_capacity,
        "fishing_zone_id": result["user"].fishing_zone_id,
        "auto_fishing_enabled": result["user"].auto_fishing_enabled,
        "created_at": result["user"].created_at.isoformat() if result["user"].created_at else None,
        "last_login_time": result["user"].last_login_time.isoformat() if result["user"].last_login_time else None
    }
    
    return {
        "success": True,
        "user": user_dict,
        "equipped_rod": result["equipped_rod"],
        "equipped_accessory": result["equipped_accessory"],
        "current_title": result["current_title"]
    }

@admin_bp.route("/users/<user_id>/update", methods=["POST"])
@login_required
@admin_required
async def update_user(user_id):
    user_service = current_app.config["USER_SERVICE"]
    
    try:
        # 获取JSON数据
        data = await request.get_json()
        if not data:
            return {"success": False, "message": "无效的请求数据"}, 400
        
        return user_service.update_user_for_admin(user_id, data)
    except Exception as e:
        return {"success": False, "message": f"更新用户时发生错误: {str(e)}"}, 500

@admin_bp.route("/users/<user_id>/delete", methods=["POST"])
@login_required
@admin_required
async def delete_user(user_id):
    user_service = current_app.config["USER_SERVICE"]
    
    try:
        return user_service.delete_user_for_admin(user_id)
    except Exception as e:
        return {"success": False, "message": f"删除用户时发生错误: {str(e)}"}, 500


# --- 市场管理 ---
@admin_bp.route("/market")
@login_required
async def manage_market():
    try:
        market_service = current_app.config["MARKET_SERVICE"]
        
        # 获取查询参数
        page = int(request.args.get("page", 1))
        item_type = request.args.get("item_type", "")
        min_price = request.args.get("min_price", "")
        max_price = request.args.get("max_price", "")
        search = request.args.get("search", "")
        
        # 转换参数
        min_price = int(min_price) if min_price else None
        max_price = int(max_price) if max_price else None
        item_type = item_type or None
        search = search or None
        
        result = market_service.get_all_market_listings_for_admin(
            page=page, 
            per_page=20,
            item_type=item_type,
            min_price=min_price,
            max_price=max_price,
            search=search
        )
        
        if not result["success"]:
            await flash("获取市场列表失败：" + result.get("message", "未知错误"), "danger")
            return redirect(url_for("admin_bp.index"))
        
        return await render_template(
            "market.html",
            listings=result["listings"],
            pagination=result["pagination"],
            stats=result["stats"],
            filters={
                "item_type": request.args.get("item_type", ""),
                "min_price": request.args.get("min_price", ""),
                "max_price": request.args.get("max_price", ""),
                "search": request.args.get("search", "")
            }
        )
    except Exception as e:
        logger.error(f"市场管理页面出错: {e}")
        logger.error(traceback.format_exc())
        await flash(f"页面加载失败: {str(e)}", "danger")
        return redirect(url_for("admin_bp.index"))

@admin_bp.route("/market/<int:market_id>/price", methods=["POST"])
@login_required
async def update_market_price(market_id):
    market_service = current_app.config["MARKET_SERVICE"]
    
    try:
        data = await request.get_json()
        if not data:
            return {"success": False, "message": "无效的请求数据"}, 400
        
        new_price = data.get("price")
        if new_price is None:
            return {"success": False, "message": "缺少价格参数"}, 400

        # 类型校验: 检查 new_price 是否为数字
        try:
            new_price_numeric = float(new_price)
        except (TypeError, ValueError):
            return {"success": False, "message": "价格参数必须为数字"}, 400

        return market_service.update_market_item_price(market_id, int(new_price_numeric))
    except Exception as e:
        logger.error(f"更新价格错误: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "message": f"更新价格时发生错误: {str(e)}"}, 500

@admin_bp.route("/market/<int:market_id>/remove", methods=["POST"])
@login_required
async def remove_market_item(market_id):
    market_service = current_app.config["MARKET_SERVICE"]
    
    try:
        return market_service.remove_market_item_by_admin(market_id)
    except Exception as e:
        logger.error(f"下架商品错误: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "message": f"下架商品时发生错误: {str(e)}"}, 500

@admin_bp.route("/users/create", methods=["POST"])
@login_required
@admin_required
async def create_user():
    user_service = current_app.config["USER_SERVICE"]
    try:
        data = await request.get_json()
        if not data:
            return {"success": False, "message": "无效的请求数据"}, 400
        return user_service.create_user_for_admin(data)
    except Exception as e:
        return {"success": False, "message": f"创建用户时发生错误: {str(e)}"}, 500

# --- 用户物品管理 ---
@admin_bp.route("/users/<user_id>/inventory")
@login_required
@admin_required
async def manage_user_inventory(user_id):
    try:
        user_service = current_app.config["USER_SERVICE"]
        item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
        
        # 获取用户库存信息
        inventory_result = user_service.get_user_inventory_for_admin(user_id)
        
        if not inventory_result["success"]:
            await flash("获取用户库存失败：" + inventory_result.get("message", "未知错误"), "danger")
            return redirect(url_for("admin_bp.manage_users"))
        
        # 获取所有物品模板用于添加物品
        all_fish = item_template_service.get_all_fish()
        all_rods = item_template_service.get_all_rods()
        all_accessories = item_template_service.get_all_accessories()
        all_baits = item_template_service.get_all_baits()
        
        return await render_template(
            "users_inventory.html",
            user_id=user_id,
            user_nickname=inventory_result["nickname"],
            inventory=inventory_result,
            all_fish=all_fish,
            all_rods=all_rods,
            all_accessories=all_accessories,
            all_baits=all_baits
        )
    except Exception as e:
        await flash(f"页面加载失败: {str(e)}", "danger")
        return redirect(url_for("admin_bp.manage_users"))

@admin_bp.route("/users/<user_id>/inventory/add", methods=["POST"])
@login_required
async def add_item_to_user_inventory(user_id):
    user_service = current_app.config["USER_SERVICE"]
    
    try:
        data = await request.get_json()
        if not data:
            return {"success": False, "message": "无效的请求数据"}, 400
        
        item_type = data.get("item_type")
        item_id = data.get("item_id")
        quantity = data.get("quantity", 1)
        
        if not item_type or not item_id:
            return {"success": False, "message": "缺少必要参数"}, 400
        
        result = user_service.add_item_to_user_inventory(user_id, item_type, item_id, quantity)
        return result
    except Exception as e:
        return {"success": False, "message": f"添加物品时发生错误: {str(e)}"}, 500

@admin_bp.route("/users/<user_id>/inventory/remove", methods=["POST"])
@login_required
async def remove_item_from_user_inventory(user_id):
    user_service = current_app.config["USER_SERVICE"]
    
    try:
        data = await request.get_json()
        if not data:
            return {"success": False, "message": "无效的请求数据"}, 400
        
        item_type = data.get("item_type")
        item_id = data.get("item_id")
        quantity = data.get("quantity", 1)
        
        if not item_type or not item_id:
            return {"success": False, "message": "缺少必要参数"}, 400
        
        result = user_service.remove_item_from_user_inventory(user_id, item_type, item_id, quantity)
        return result
    except Exception as e:
        return {"success": False, "message": f"移除物品时发生错误: {str(e)}"}, 500