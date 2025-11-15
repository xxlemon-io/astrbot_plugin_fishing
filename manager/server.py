import functools
import os
import traceback
from typing import Dict, Any
from datetime import datetime, timedelta
import csv
import io

from quart import (
    Quart, render_template, request, redirect, url_for, session, flash,
    Blueprint, current_app, jsonify
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

@admin_bp.route("/fish/csv/template")
@login_required
async def fish_csv_template():
    header = ["name", "description", "rarity", "base_value", "min_weight", "max_weight", "icon_url"]
    sample = ["示例鱼", "一条很普通的示例鱼", "1", "10", "100", "500", ""]
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    writer.writerow(sample)
    csv_data = output.getvalue()

    from quart import Response
    return Response(
        csv_data,
        headers={
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": "attachment; filename=fish_template.csv",
        },
    )

@admin_bp.route("/fish/csv/import", methods=["POST"])
@login_required
async def import_fish_csv():
    try:
        files = await request.files
        file = files.get("file")
        if not file:
            await flash("未选择文件", "danger")
            return redirect(url_for("admin_bp.manage_fish"))

        content = file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        
        required_cols = {"name", "rarity", "base_value", "min_weight", "max_weight"}
        if not required_cols.issubset(set([c.strip() for c in reader.fieldnames or []])):
            await flash("CSV列缺失，至少需要: name, rarity, base_value, min_weight, max_weight", "danger")
            return redirect(url_for("admin_bp.manage_fish"))

        item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
        success_count = 0
        fail_count = 0
        for idx, row in enumerate(reader, start=2):
            try:
                data = {
                    "name": (row.get("name") or "").strip(),
                    "description": (row.get("description") or "").strip() or None,
                    "rarity": int(row.get("rarity") or 1),
                    "base_value": int(row.get("base_value") or 0),
                    "min_weight": int(row.get("min_weight") or 1),
                    "max_weight": int(row.get("max_weight") or 100),
                    "icon_url": (row.get("icon_url") or "").strip() or None,
                }
                if not data["name"]:
                    raise ValueError("缺少名称")
                item_template_service.add_fish_template(data)
                success_count += 1
            except Exception as e:
                logger.error(f"导入鱼类第{idx}行失败: {e}")
                fail_count += 1
        
        if success_count:
            await flash(f"成功导入 {success_count} 条鱼类记录" + (f"，失败 {fail_count} 条" if fail_count else ""), "success")
        else:
            await flash("未成功导入任何鱼类记录", "warning")
    except Exception as e:
        logger.error(f"导入鱼类CSV出错: {e}")
        logger.error(traceback.format_exc())
        await flash(f"导入失败: {str(e)}", "danger")
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


# --- Rods CSV 模板下载与导入 ---
@admin_bp.route("/rods/csv/template")
@login_required
async def rods_csv_template():
    header = [
        "name",
        "description",
        "rarity",
        "source",
        "purchase_cost",
        "bonus_fish_quality_modifier",
        "bonus_fish_quantity_modifier",
        "bonus_rare_fish_chance",
        "durability",
        "icon_url",
    ]
    sample = [
        "示例鱼竿",
        "这是一个示例描述",
        "3",
        "shop",
        "1000",
        "1.1",
        "1.0",
        "0.05",
        "",
        "",
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    writer.writerow(sample)
    csv_data = output.getvalue()

    from quart import Response
    return Response(
        csv_data,
        headers={
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": "attachment; filename=rods_template.csv",
        },
    )


@admin_bp.route("/rods/csv/import", methods=["POST"])
@login_required
async def import_rods_csv():
    try:
        files = await request.files
        file = files.get("file")
        if not file:
            await flash("未选择文件", "danger")
            return redirect(url_for("admin_bp.manage_rods"))

        content = file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        required_cols = {
            "name",
            "rarity",
            "source",
            "bonus_fish_quality_modifier",
            "bonus_fish_quantity_modifier",
            "bonus_rare_fish_chance",
        }
        if not required_cols.issubset(set([c.strip() for c in reader.fieldnames or []])):
            await flash("CSV列缺失，至少需要: name, rarity, source, 三个加成字段", "danger")
            return redirect(url_for("admin_bp.manage_rods"))

        item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
        success_count = 0
        fail_count = 0
        for idx, row in enumerate(reader, start=2):  # 从第2行开始（跳过表头）
            try:
                data = {
                    "name": (row.get("name") or "").strip(),
                    "description": (row.get("description") or "").strip() or None,
                    "rarity": int(row.get("rarity") or 1),
                    "source": (row.get("source") or "shop").strip(),
                    "purchase_cost": int(row["purchase_cost"]) if (row.get("purchase_cost") or "").strip() != "" else None,
                    "bonus_fish_quality_modifier": float(row.get("bonus_fish_quality_modifier") or 1.0),
                    "bonus_fish_quantity_modifier": float(row.get("bonus_fish_quantity_modifier") or 1.0),
                    "bonus_rare_fish_chance": float(row.get("bonus_rare_fish_chance") or 0.0),
                    "durability": int(row["durability"]) if (row.get("durability") or "").strip() != "" else None,
                    "icon_url": (row.get("icon_url") or "").strip() or None,
                }
                if not data["name"]:
                    raise ValueError("缺少名称")
                item_template_service.add_rod_template(data)
                success_count += 1
            except Exception as e:
                logger.error(f"导入鱼竿第{idx}行失败: {e}")
                fail_count += 1

        if success_count:
            await flash(f"成功导入 {success_count} 条鱼竿记录" + (f"，失败 {fail_count} 条" if fail_count else ""), "success")
        else:
            await flash("未成功导入任何鱼竿记录", "warning")
    except Exception as e:
        logger.error(f"导入鱼竿CSV出错: {e}")
        logger.error(traceback.format_exc())
        await flash(f"导入失败: {str(e)}", "danger")
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


# --- Accessories CSV 模板下载与导入 ---
@admin_bp.route("/accessories/csv/template")
@login_required
async def accessories_csv_template():
    header = [
        "name",
        "description",
        "rarity",
        "slot_type",
        "bonus_fish_quality_modifier",
        "bonus_fish_quantity_modifier",
        "bonus_rare_fish_chance",
        "bonus_coin_modifier",
        "other_bonus_description",
        "icon_url",
    ]
    sample = [
        "示例饰品",
        "这是一个示例描述",
        "2",
        "general",
        "1.05",
        "1.0",
        "0.02",
        "1.10",
        "额外描述",
        "",
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    writer.writerow(sample)
    csv_data = output.getvalue()

    from quart import Response
    return Response(
        csv_data,
        headers={
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": "attachment; filename=accessories_template.csv",
        },
    )


@admin_bp.route("/accessories/csv/import", methods=["POST"])
@login_required
async def import_accessories_csv():
    try:
        files = await request.files
        file = files.get("file")
        if not file:
            await flash("未选择文件", "danger")
            return redirect(url_for("admin_bp.manage_accessories"))

        content = file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        required_cols = {
            "name",
            "rarity",
            "slot_type",
            "bonus_fish_quality_modifier",
            "bonus_fish_quantity_modifier",
            "bonus_rare_fish_chance",
            "bonus_coin_modifier",
        }
        if not required_cols.issubset(set([c.strip() for c in reader.fieldnames or []])):
            await flash("CSV列缺失，至少需要: name, rarity, slot_type, 四个加成字段", "danger")
            return redirect(url_for("admin_bp.manage_accessories"))

        item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
        success_count = 0
        fail_count = 0
        for idx, row in enumerate(reader, start=2):
            try:
                data = {
                    "name": (row.get("name") or "").strip(),
                    "description": (row.get("description") or "").strip() or None,
                    "rarity": int(row.get("rarity") or 1),
                    "slot_type": (row.get("slot_type") or "general").strip(),
                    "bonus_fish_quality_modifier": float(row.get("bonus_fish_quality_modifier") or 1.0),
                    "bonus_fish_quantity_modifier": float(row.get("bonus_fish_quantity_modifier") or 1.0),
                    "bonus_rare_fish_chance": float(row.get("bonus_rare_fish_chance") or 0.0),
                    "bonus_coin_modifier": float(row.get("bonus_coin_modifier") or 1.0),
                    "other_bonus_description": (row.get("other_bonus_description") or "").strip() or None,
                    "icon_url": (row.get("icon_url") or "").strip() or None,
                }
                if not data["name"]:
                    raise ValueError("缺少名称")
                item_template_service.add_accessory_template(data)
                success_count += 1
            except Exception as e:
                logger.error(f"导入饰品第{idx}行失败: {e}")
                fail_count += 1

        if success_count:
            await flash(f"成功导入 {success_count} 条饰品记录" + (f"，失败 {fail_count} 条" if fail_count else ""), "success")
        else:
            await flash("未成功导入任何饰品记录", "warning")
    except Exception as e:
        logger.error(f"导入饰品CSV出错: {e}")
        logger.error(traceback.format_exc())
        await flash(f"导入失败: {str(e)}", "danger")
    return redirect(url_for("admin_bp.manage_accessories"))


# --- 抽卡池管理 ---
@admin_bp.route("/gacha")
@login_required
async def manage_gacha():
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    pools = item_template_service.get_all_gacha_pools()
    # 直接渲染，不再拼装包含物品的展示数据
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
    # 限时逻辑：仅当开关为 ON 时保留截止时间
    is_limited_flag = data.get("is_limited_time") in (True, "1", 1, "on")
    open_until_value = data.get("open_until") if is_limited_flag and data.get("open_until") else None
    payload = {
        "name": data.get("name"),
        "description": data.get("description"),
        "cost_coins": amount if currency_type == "coins" else 0,
        "cost_premium_currency": amount if currency_type == "premium" else 0,
        "is_limited_time": is_limited_flag,
        "open_until": open_until_value
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
    # 限时逻辑：仅当开关为 ON 时保留截止时间
    is_limited_flag = data.get("is_limited_time") in (True, "1", 1, "on")
    open_until_value = data.get("open_until") if is_limited_flag and data.get("open_until") else None
    payload = {
        "name": data.get("name"),
        "description": data.get("description"),
        "cost_coins": amount if currency_type == "coins" else 0,
        "cost_premium_currency": amount if currency_type == "premium" else 0,
        "is_limited_time": is_limited_flag,
        "open_until": open_until_value
    }
    item_template_service.update_pool_template(pool_id, payload)
    await flash(f"奖池ID {pool_id} 更新成功！", "success")
    return redirect(url_for("admin_bp.manage_gacha"))


@admin_bp.route("/gacha/copy/<int:pool_id>", methods=["POST"])
@login_required
async def copy_gacha_pool(pool_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    try:
        new_pool_id = item_template_service.copy_pool_template(pool_id)
        await flash(f"奖池ID {pool_id} 已成功复制，新奖池ID为 {new_pool_id}！", "success")
    except Exception as e:
        await flash(f"复制奖池失败：{str(e)}", "danger")
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
        item_rarity = None  # 添加星级属性
        item_type = item.item_type
        item_id = item.item_id
        
        # 根据类型从 item_template_service 获取名称和星级
        if item_type == "rod":
            template = item_template_service.item_template_repo.get_rod_by_id(item_id)
            if template:
                item_name = template.name
                item_rarity = template.rarity
        elif item_type == "accessory":
            template = item_template_service.item_template_repo.get_accessory_by_id(item_id)
            if template:
                item_name = template.name
                item_rarity = template.rarity
        elif item_type == "bait":
            template = item_template_service.item_template_repo.get_bait_by_id(item_id)
            if template:
                item_name = template.name
                item_rarity = template.rarity
        elif item_type == "item":
            template = item_template_service.item_template_repo.get_by_id(item_id)
            if template:
                item_name = template.name
                item_rarity = template.rarity
        elif item_type == "fish":
            template = item_template_service.item_template_repo.get_fish_by_id(item_id)
            if template:
                item_name = template.name
                item_rarity = template.rarity
        elif item_type == "titles":
            template = item_template_service.item_template_repo.get_title_by_id(item_id)
            if template:
                item_name = template.name
        elif item_type == "coins":
            item_name = f"{item.quantity} 金币"

        item_dict["item_name"] = item_name  # 添加名称属性
        item_dict["rarity"] = item_rarity  # 添加星级属性
        enriched_items.append(item_dict)

    return await render_template(
        "gacha_pool_details.html",
        pool=details["pool"],
        items=enriched_items,  # 传递丰富化后的物品列表
        all_rods=details["all_rods"],
        all_baits=details["all_baits"],
        all_accessories=details["all_accessories"],
        all_items=item_template_service.get_all_items()  # 新增
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


@admin_bp.route("/gacha/pool/update_weight/<int:item_id>", methods=["POST"])
@login_required
async def update_pool_item_weight(item_id):
    """快速更新奖池物品权重"""
    try:
        data = await request.get_json()
        weight = data.get("weight")

        if not weight or not isinstance(weight, (int, float)) or weight < 1:
            return jsonify({"success": False, "message": "权重必须是大于0的数字"}), 400

        item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]

        # 直接更新权重，update_pool_item方法会处理验证
        item_template_service.update_pool_item(item_id, {"weight": int(weight)})

        return jsonify({"success": True, "message": "权重更新成功"})

    except Exception as e:
        logger.error(f"权重更新失败 - item_id: {item_id}, error: {str(e)}")
        return jsonify({"success": False, "message": f"更新失败: {str(e)}"}), 500


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
        "current_title": result["current_title"],
        "titles": result.get("titles", [])
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


# --- 交易所管理 ---
@admin_bp.route("/exchange")
@login_required
async def manage_exchange():
    try:
        exchange_service = current_app.config["EXCHANGE_SERVICE"]
        
        # 获取当前价格
        market_status = exchange_service.get_market_status()
        
        # 获取价格历史（最近7天）
        price_history = exchange_service.get_price_history(days=7)
        
        # 获取用户持仓统计
        user_stats = exchange_service.get_user_commodity_stats()
        
        return await render_template(
            "exchange.html",
            market_status=market_status,
            price_history=price_history,
            user_stats=user_stats,
            now=datetime.now()
        )
    except Exception as e:
        logger.error(f"交易所管理页面出错: {e}")
        logger.error(traceback.format_exc())
        await flash(f"页面加载失败: {str(e)}", "danger")
        return redirect(url_for("admin_bp.index"))

@admin_bp.route("/exchange/update_prices", methods=["POST"])
@login_required
async def update_exchange_prices():
    try:
        exchange_service = current_app.config["EXCHANGE_SERVICE"]
        result = exchange_service.manual_update_prices()
        
        if result["success"]:
            await flash("交易所价格更新成功！", "success")
        else:
            await flash(f"价格更新失败：{result['message']}", "danger")
    except Exception as e:
        logger.error(f"更新交易所价格失败: {e}")
        await flash(f"价格更新失败: {str(e)}", "danger")
    
    return redirect(url_for("admin_bp.manage_exchange"))

@admin_bp.route("/exchange/reset_prices", methods=["POST"])
@login_required
async def reset_exchange_prices():
    try:
        exchange_service = current_app.config["EXCHANGE_SERVICE"]
        result = exchange_service.reset_prices_to_initial()
        
        if result["success"]:
            await flash("交易所价格已重置到初始值！", "success")
        else:
            await flash(f"价格重置失败：{result['message']}", "danger")
    except Exception as e:
        logger.error(f"重置交易所价格失败: {e}")
        await flash(f"价格重置失败: {str(e)}", "danger")
    
    return redirect(url_for("admin_bp.manage_exchange"))

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
        all_items = item_template_service.get_all_items()
        
        return await render_template(
            "users_inventory.html",
            user_id=user_id,
            user_nickname=inventory_result["nickname"],
            inventory=inventory_result,
            all_fish=all_fish,
            all_rods=all_rods,
            all_accessories=all_accessories,
            all_baits=all_baits,
            all_items=all_items
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
        quality_level = data.get("quality_level", 0)  # 添加品质等级参数
        
        if not item_type or not item_id:
            return {"success": False, "message": "缺少必要参数"}, 400
        
        result = user_service.add_item_to_user_inventory(user_id, item_type, item_id, quantity, quality_level)
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

# --- 用户物品实例属性编辑（精炼等级/耐久度） ---
@admin_bp.route("/users/<user_id>/inventory/rod/<int:instance_id>/update", methods=["POST"])
@login_required
@admin_required
async def update_rod_instance(user_id, instance_id):
    user_service = current_app.config["USER_SERVICE"]
    try:
        data = await request.get_json()
        if not data:
            return {"success": False, "message": "无效的请求数据"}, 400
        return user_service.update_user_rod_instance_for_admin(user_id, instance_id, data)
    except Exception as e:
        return {"success": False, "message": f"更新鱼竿实例时发生错误: {str(e)}"}, 500

@admin_bp.route("/users/<user_id>/inventory/accessory/<int:instance_id>/update", methods=["POST"])
@login_required
@admin_required
async def update_accessory_instance(user_id, instance_id):
    user_service = current_app.config["USER_SERVICE"]
    try:
        data = await request.get_json()
        if not data:
            return {"success": False, "message": "无效的请求数据"}, 400
        return user_service.update_user_accessory_instance_for_admin(user_id, instance_id, data)
    except Exception as e:
        return {"success": False, "message": f"更新饰品实例时发生错误: {str(e)}"}, 500

# --- 称号管理 ---
@admin_bp.route("/titles")
@login_required
@admin_required
async def manage_titles():
    user_service = current_app.config["USER_SERVICE"]
    result = user_service.get_all_titles_for_admin()
    if not result["success"]:
        await flash("获取称号列表失败：" + result.get("message", "未知错误"), "danger")
        return redirect(url_for("admin_bp.index"))
    return await render_template("titles.html", titles=result["titles"])

@admin_bp.route("/titles/add", methods=["POST"])
@login_required
@admin_required
async def add_title():
    user_service = current_app.config["USER_SERVICE"]
    form = await request.form
    name = form.get("name", "").strip()
    description = form.get("description", "").strip()
    display_format = form.get("display_format", "{name}").strip()
    
    if not name:
        await flash("称号名称不能为空", "danger")
        return redirect(url_for("admin_bp.manage_titles"))
    
    if not description:
        description = f"自定义称号：{name}"
    
    result = user_service.create_custom_title(name, description, display_format)
    if result["success"]:
        await flash(result["message"], "success")
    else:
        await flash(result["message"], "danger")
    return redirect(url_for("admin_bp.manage_titles"))

@admin_bp.route("/titles/edit/<int:title_id>", methods=["POST"])
@login_required
@admin_required
async def edit_title(title_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    form = await request.form
    name = form.get("name", "").strip()
    description = form.get("description", "").strip()
    display_format = form.get("display_format", "{name}").strip()
    
    if not name:
        await flash("称号名称不能为空", "danger")
        return redirect(url_for("admin_bp.manage_titles"))
    
    # 检查称号是否存在
    existing_title = item_template_service.get_title_by_id(title_id)
    if not existing_title:
        await flash(f"称号ID {title_id} 不存在", "danger")
        return redirect(url_for("admin_bp.manage_titles"))
    
    # 检查名称是否与其他称号冲突
    title_by_name = item_template_service.get_title_by_name(name)
    if title_by_name and title_by_name.title_id != title_id:
        await flash(f"称号名称 '{name}' 已被其他称号使用", "danger")
        return redirect(url_for("admin_bp.manage_titles"))
    
    # 更新称号
    title_data = {
        "name": name,
        "description": description,
        "display_format": display_format
    }
    item_template_service.update_title_template(title_id, title_data)
    await flash(f"称号ID {title_id} 更新成功！", "success")
    return redirect(url_for("admin_bp.manage_titles"))

@admin_bp.route("/titles/delete/<int:title_id>", methods=["POST"])
@login_required
@admin_required
async def delete_title(title_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    try:
        item_template_service.delete_title_template(title_id)
        await flash(f"称号ID {title_id} 已删除！", "warning")
    except Exception as e:
        await flash(f"删除失败：{str(e)}", "danger")
    return redirect(url_for("admin_bp.manage_titles"))

@admin_bp.route("/users/<user_id>/grant_title", methods=["POST"])
@login_required
@admin_required
async def grant_title_to_user(user_id):
    user_service = current_app.config["USER_SERVICE"]
    try:
        data = await request.get_json()
        if not data:
            return {"success": False, "message": "无效的请求数据"}, 400
        
        title_name = data.get("title_name")
        if not title_name:
            return {"success": False, "message": "缺少称号名称"}, 400
        
        result = user_service.grant_title_to_user_by_name(user_id, title_name)
        return result
    except Exception as e:
        return {"success": False, "message": f"授予称号时发生错误: {str(e)}"}, 500

@admin_bp.route("/users/<user_id>/revoke_title", methods=["POST"])
@login_required
@admin_required
async def revoke_title_from_user(user_id):
    user_service = current_app.config["USER_SERVICE"]
    try:
        data = await request.get_json()
        if not data:
            return {"success": False, "message": "无效的请求数据"}, 400
        
        title_name = data.get("title_name")
        if not title_name:
            return {"success": False, "message": "缺少称号名称"}, 400
        
        result = user_service.revoke_title_from_user_by_name(user_id, title_name)
        return result
    except Exception as e:
        return {"success": False, "message": f"移除称号时发生错误: {str(e)}"}, 500

@admin_bp.route("/api/titles", methods=["GET"])
@login_required
@admin_required
async def api_get_all_titles():
    """获取所有称号列表的API"""
    user_service = current_app.config["USER_SERVICE"]
    result = user_service.get_all_titles_for_admin()
    return jsonify(result)

# --- 道具管理 ---
@admin_bp.route("/items")
@login_required
@admin_required
async def manage_items():
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    items = item_template_service.get_all_items()
    return await render_template("items.html", items=items)

@admin_bp.route("/items/add", methods=["POST"])
@login_required
@admin_required
async def add_item():
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    try:
        form_data = await request.form
        data = {k: v for k, v in form_data.items()}
        data['rarity'] = int(data.get('rarity', 1))
        data['cost'] = int(data.get('cost', 0))
        # 使用布尔值保存是否消耗品
        is_flag = 'is_consumable' in data
        data['is_consumable'] = is_flag
        item_template_service.add_item_template(data)
        await flash("道具模板已添加", "success")
    except Exception as e:
        await flash(f"添加道具模板失败: {str(e)}", "danger")
    return redirect(url_for("admin_bp.manage_items"))

@admin_bp.route("/items/edit/<int:item_id>", methods=["POST"])
@login_required
@admin_required
async def edit_item(item_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    try:
        form_data = await request.form
        data = {k: v for k, v in form_data.items()}
        data['rarity'] = int(data.get('rarity', 1))
        data['cost'] = int(data.get('cost', 0))
        # 使用布尔值保存是否消耗品
        is_flag = 'is_consumable' in data
        data['is_consumable'] = is_flag
        item_template_service.update_item_template(item_id, data)
        await flash("道具模板已更新", "success")
    except Exception as e:
        await flash(f"更新道具模板失败: {str(e)}", "danger")
    return redirect(url_for("admin_bp.manage_items"))

@admin_bp.route("/items/delete/<int:item_id>", methods=["POST"])
@login_required
@admin_required
async def delete_item(item_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    try:
        item_template_service.delete_item_template(item_id)
        await flash("道具模板已删除", "success")
    except Exception as e:
        await flash(f"删除道具模板失败: {str(e)}", "danger")
    return redirect(url_for("admin_bp.manage_items"))

@admin_bp.route('/zones', methods=['GET'])
@login_required
async def manage_zones():
    fishing_zone_service = current_app.config["FISHING_ZONE_SERVICE"]
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    zones = fishing_zone_service.get_all_zones()
    all_fish = item_template_service.get_all_fish()
    all_items = item_template_service.get_all_items()
    return await render_template('zones.html', zones=zones, all_fish=all_fish, all_items=all_items)

@admin_bp.route('/api/zones', methods=['POST'])
@login_required
async def create_zone_api():
    try:
        data = await request.get_json()
        fishing_zone_service = current_app.config["FISHING_ZONE_SERVICE"]
        
        # --- Enhanced Validation ---
        errors = {}
        zone_id = data.get('id')
        if not zone_id or not str(zone_id).isdigit() or int(zone_id) <= 0:
            errors['id'] = '区域 ID 必须是一个正整数'
        
        if not data.get('name'):
            errors['name'] = '区域名称不能为空'
            
        quota = data.get('daily_rare_fish_quota')
        if quota is None or not str(quota).isdigit() or int(quota) < 0:
            errors['daily_rare_fish_quota'] = '稀有鱼每日配额必须是一个非负整数'
            
        fishing_cost = data.get('fishing_cost')
        if fishing_cost is None or not str(fishing_cost).isdigit() or int(fishing_cost) < 1:
            errors['fishing_cost'] = '钓鱼消耗必须是一个正整数'
        
        if errors:
            return jsonify({"success": False, "message": "数据校验失败", "errors": errors}), 400
        # --- End of Validation ---

        new_zone = fishing_zone_service.create_zone(data)
        # create_zone 已返回字典，直接返回
        return jsonify({"success": True, "message": "钓鱼区域创建成功", "zone": new_zone})
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 409 # 409 Conflict
    except Exception as e:
        logger.error(f"创建钓鱼区域失败: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500

@admin_bp.route('/api/zones/<int:zone_id>', methods=['PUT'])
@login_required
async def update_zone_api(zone_id):
    try:
        data = await request.get_json()
        fishing_zone_service = current_app.config["FISHING_ZONE_SERVICE"]
        
        # --- Enhanced Validation ---
        errors = {}
        if not data.get('name'):
            errors['name'] = '区域名称不能为空'
            
        quota = data.get('daily_rare_fish_quota')
        if quota is None or not str(quota).isdigit() or int(quota) < 0:
            errors['daily_rare_fish_quota'] = '稀有鱼每日配额必须是一个非负整数'
            
        fishing_cost = data.get('fishing_cost')
        if fishing_cost is None or not str(fishing_cost).isdigit() or int(fishing_cost) < 1:
            errors['fishing_cost'] = '钓鱼消耗必须是一个正整数'

        if errors:
            return jsonify({"success": False, "message": "数据校验失败", "errors": errors}), 400
        # --- End of Validation ---

        fishing_zone_service.update_zone(zone_id, data)
        # 前端会刷新页面，这里不必返回完整对象
        return jsonify({"success": True, "message": "钓鱼区域更新成功"})
    except Exception as e:
        logger.error(f"更新钓鱼区域失败: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500

@admin_bp.route('/api/zones/<int:zone_id>', methods=['DELETE'])
@login_required
async def delete_zone_api(zone_id):
    try:
        fishing_zone_service = current_app.config["FISHING_ZONE_SERVICE"]
        fishing_zone_service.delete_zone(zone_id)
        return jsonify({"success": True, "message": "钓鱼区域删除成功"})
    except Exception as e:
        logger.error(f"删除钓鱼区域失败: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500

# --- 商店管理 (Shop Offers) - 已集成到商店详情页面 ---

# ===== 商店管理（新设计：shops + shop_items） =====
@admin_bp.route("/shops")
@login_required
async def manage_shops():
    shop_service = current_app.config["SHOP_SERVICE"]
    shops = shop_service.shop_repo.get_all_shops()
    # 对商店列表进行排序：按 sort_order 升序，然后按 shop_id 升序
    shops.sort(key=lambda x: (x.get("sort_order", 999), x.get("shop_id", 999)))
    return await render_template("shops.html", shops=shops)

@admin_bp.route("/shops/<int:shop_id>")
@login_required
async def manage_shop_details(shop_id):
    shop_service = current_app.config["SHOP_SERVICE"]
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    
    # 获取商店信息
    shop = shop_service.shop_repo.get_shop_by_id(shop_id)
    if not shop:
        return "商店不存在", 404
    
    # 获取商店内的商品
    items = shop_service.shop_repo.get_shop_items(shop_id)
    items_with_details = []
    
    for item in items:
        # 获取成本和奖励
        costs = shop_service.shop_repo.get_item_costs(item["item_id"])
        rewards = shop_service.shop_repo.get_item_rewards(item["item_id"])
        
        # 为成本添加物品名称
        for cost in costs:
            if cost["cost_type"] == "fish":
                fish_template = item_template_service.get_fish_by_id(cost.get("cost_item_id"))
                cost["fish_name"] = fish_template.name if fish_template else None
            elif cost["cost_type"] == "item":
                item_template = item_template_service.get_item_by_id(cost.get("cost_item_id"))
                cost["item_name"] = item_template.name if item_template else None
            elif cost["cost_type"] == "rod":
                rod_template = item_template_service.get_rod_by_id(cost.get("cost_item_id"))
                cost["rod_name"] = rod_template.name if rod_template else None
            elif cost["cost_type"] == "accessory":
                accessory_template = item_template_service.get_accessory_by_id(cost.get("cost_item_id"))
                cost["accessory_name"] = accessory_template.name if accessory_template else None
        
        # 为奖励添加物品名称
        for reward in rewards:
            if reward["reward_type"] == "fish":
                fish_template = item_template_service.get_fish_by_id(reward.get("reward_item_id"))
                reward["fish_name"] = fish_template.name if fish_template else None
            elif reward["reward_type"] == "item":
                item_template = item_template_service.get_item_by_id(reward.get("reward_item_id"))
                reward["item_name"] = item_template.name if item_template else None
            elif reward["reward_type"] == "rod":
                rod_template = item_template_service.get_rod_by_id(reward.get("reward_item_id"))
                reward["rod_name"] = rod_template.name if rod_template else None
            elif reward["reward_type"] == "accessory":
                accessory_template = item_template_service.get_accessory_by_id(reward.get("reward_item_id"))
                reward["accessory_name"] = accessory_template.name if accessory_template else None
            elif reward["reward_type"] == "bait":
                bait_template = item_template_service.get_bait_by_id(reward.get("reward_item_id"))
                reward["bait_name"] = bait_template.name if bait_template else None
        
        items_with_details.append({
            "item": item,
            "costs": costs,
            "rewards": rewards,
        })
    
    # 获取所有可用的商品（兼容旧接口）
    available_offers = shop_service.shop_repo.get_active_offers()
    
    # 可选物品下拉所需的全量模板数据
    all_rods = item_template_service.get_all_rods()
    all_baits = item_template_service.get_all_baits()
    all_accessories = item_template_service.get_all_accessories()
    all_items = item_template_service.get_all_items()
    all_fish = item_template_service.get_all_fish()

    return await render_template(
        "shop_details.html",
        shop=shop,
        items=items_with_details,
        available_offers=available_offers,
        all_rods=all_rods,
        all_baits=all_baits,
        all_accessories=all_accessories,
        all_items=all_items,
        all_fish=all_fish,
    )

@admin_bp.route("/api/shops", methods=["GET"])
@login_required
async def api_list_shops():
    shop_service = current_app.config["SHOP_SERVICE"]
    shops = shop_service.shop_repo.get_all_shops()
    # 对商店列表进行排序：按 sort_order 升序，然后按 shop_id 升序
    shops.sort(key=lambda x: (x.get("sort_order", 999), x.get("shop_id", 999)))
    return jsonify({"success": True, "shops": shops})

@admin_bp.route("/shops/add", methods=["POST"])
@login_required
async def add_shop():
    data = await request.form
    shop_service = current_app.config["SHOP_SERVICE"]
    
    shop_data = {
        "name": data.get("name"),
        "description": data.get("description"),
        "shop_type": data.get("shop_type", "normal"),
        "is_active": data.get("is_active") == "on",
        "start_time": data.get("start_time") or None,
        "end_time": data.get("end_time") or None,
        "daily_start_time": data.get("daily_start_time") or None,
        "daily_end_time": data.get("daily_end_time") or None,
        "sort_order": int(data.get("sort_order", 100)),
    }
    
    created = shop_service.shop_repo.create_shop(shop_data)
    return redirect(url_for("admin_bp.manage_shops"))

@admin_bp.route("/shops/edit/<int:shop_id>", methods=["POST"])
@login_required
async def edit_shop(shop_id):
    data = await request.form
    shop_service = current_app.config["SHOP_SERVICE"]
    
    shop_data = {
        "name": data.get("name"),
        "description": data.get("description"),
        "shop_type": data.get("shop_type", "normal"),
        "is_active": data.get("is_active") == "on",
        "start_time": data.get("start_time") or None,
        "end_time": data.get("end_time") or None,
        "daily_start_time": data.get("daily_start_time") or None,
        "daily_end_time": data.get("daily_end_time") or None,
        "sort_order": int(data.get("sort_order", 100)),
    }
    
    shop_service.shop_repo.update_shop(shop_id, shop_data)
    return redirect(url_for("admin_bp.manage_shops"))

@admin_bp.route("/shops/delete/<int:shop_id>", methods=["POST"])
@login_required
async def delete_shop(shop_id):
    shop_service = current_app.config["SHOP_SERVICE"]
    shop_service.shop_repo.delete_shop(shop_id)
    return redirect(url_for("admin_bp.manage_shops"))

@admin_bp.route("/api/shops", methods=["POST"])
@login_required
async def api_create_shop():
    payload = await request.get_json()
    shop_service = current_app.config["SHOP_SERVICE"]
    created = shop_service.shop_repo.create_shop(payload or {})
    return jsonify({"success": True, "shop": created})

@admin_bp.route("/api/shops/<int:shop_id>", methods=["PUT"])
@login_required
async def api_update_shop(shop_id):
    payload = await request.get_json()
    shop_service = current_app.config["SHOP_SERVICE"]
    shop_service.shop_repo.update_shop(shop_id, payload or {})
    return jsonify({"success": True})

@admin_bp.route("/api/shops/<int:shop_id>", methods=["DELETE"])
@login_required
async def api_delete_shop(shop_id):
    shop_service = current_app.config["SHOP_SERVICE"]
    shop_service.shop_repo.delete_shop(shop_id)
    return jsonify({"success": True})

@admin_bp.route("/api/shops/<int:shop_id>/items", methods=["GET"])
@login_required
async def api_get_shop_items(shop_id):
    shop_service = current_app.config["SHOP_SERVICE"]
    items = shop_service.shop_repo.get_shop_items(shop_id)
    return jsonify({"success": True, "items": items})

@admin_bp.route("/shops/<int:shop_id>/items/add", methods=["POST"])
@login_required
async def add_shop_item(shop_id):
    data = await request.form
    shop_service = current_app.config["SHOP_SERVICE"]
    
    # 创建商品
    item_data = {
        "name": data.get("name") or "未命名商品",
        "description": data.get("description") or "",
        "category": data.get("category", "general"),
        "stock_total": int(data.get("stock_total")) if data.get("stock_total") else None,
        "stock_sold": int(data.get("stock_sold", 0)),
        "per_user_limit": int(data.get("per_user_limit")) if data.get("per_user_limit") else None,
        "per_user_daily_limit": int(data.get("per_user_daily_limit")) if data.get("per_user_daily_limit") else None,
        "is_active": data.get("is_active") == "on",
        "start_time": data.get("start_time") or None,
        "end_time": data.get("end_time") or None,
        "sort_order": int(data.get("sort_order", 100)),
    }
    
    created_item = shop_service.shop_repo.create_shop_item(shop_id, item_data)
    item_id = created_item["item_id"]
    
    # 解析并添加成本
    cost_full_ids = data.getlist("cost_item_full_id") if hasattr(data, 'getlist') else []
    cost_amounts = data.getlist("cost_amount") if hasattr(data, 'getlist') else []
    cost_relations = data.getlist("cost_relation") if hasattr(data, 'getlist') else []
    cost_groups = data.getlist("cost_group") if hasattr(data, 'getlist') else []
    cost_quality_levels = data.getlist("cost_quality_level") if hasattr(data, 'getlist') else []
    
    for idx, full_id in enumerate(cost_full_ids):
        if not full_id:
            continue
        amount_text = cost_amounts[idx] if idx < len(cost_amounts) else ""
        if not amount_text:
            continue
        try:
            amount_val = int(amount_text)
        except Exception:
            continue
            
        t, _, id_text = full_id.partition('-')
        cost_data = {
            "cost_type": t,
            "cost_amount": amount_val,
            "cost_relation": cost_relations[idx] if idx < len(cost_relations) else "and",
            "group_id": int(cost_groups[idx]) if idx < len(cost_groups) and cost_groups[idx] else None,
            "quality_level": int(cost_quality_levels[idx]) if idx < len(cost_quality_levels) and cost_quality_levels[idx] else 0,
        }
        
        if t in ("fish", "item", "rod", "accessory"):
            try:
                cost_data["cost_item_id"] = int(id_text)
            except Exception:
                continue
        
        shop_service.shop_repo.add_item_cost(item_id, cost_data)

    # 解析并添加奖励
    reward_full_ids = data.getlist("reward_item_full_id") if hasattr(data, 'getlist') else []
    reward_quantities = data.getlist("reward_quantity") if hasattr(data, 'getlist') else []
    reward_refine_levels = data.getlist("reward_refine_level") if hasattr(data, 'getlist') else []
    reward_quality_levels = data.getlist("reward_quality_level") if hasattr(data, 'getlist') else []
    
    for idx, full_id in enumerate(reward_full_ids):
        if not full_id:
            continue
        qty_text = reward_quantities[idx] if idx < len(reward_quantities) else "1"
        try:
            qty_val = int(qty_text or "1")
        except Exception:
            qty_val = 1
            
        t, _, id_text = full_id.partition('-')
        reward_data = {
            "reward_type": t,
            "reward_quantity": qty_val,
            "reward_refine_level": int(reward_refine_levels[idx]) if idx < len(reward_refine_levels) and reward_refine_levels[idx] else None,
            "quality_level": int(reward_quality_levels[idx]) if idx < len(reward_quality_levels) and reward_quality_levels[idx] else 0,
        }
        
        try:
            reward_data["reward_item_id"] = int(id_text)
        except Exception:
            continue
            
        shop_service.shop_repo.add_item_reward(item_id, reward_data)
    
    return redirect(url_for("admin_bp.manage_shop_details", shop_id=shop_id))

@admin_bp.route("/shops/<int:shop_id>/items/edit/<int:item_id>", methods=["POST"])
@login_required
async def edit_shop_item(shop_id, item_id):
    data = await request.form
    shop_service = current_app.config["SHOP_SERVICE"]
    
    # 更新商品信息
    item_data = {
        "name": data.get("name", ""),
        "description": data.get("description", ""),
        "category": data.get("category", "general"),
        "stock_total": int(data.get("stock_total")) if data.get("stock_total") else None,
        "stock_sold": int(data.get("stock_sold", 0)),
        "per_user_limit": int(data.get("per_user_limit")) if data.get("per_user_limit") else None,
        "per_user_daily_limit": int(data.get("per_user_daily_limit")) if data.get("per_user_daily_limit") else None,
        "is_active": data.get("is_active") == "on",
        "start_time": data.get("start_time") or None,
        "end_time": data.get("end_time") or None,
        "sort_order": int(data.get("sort_order", 100)),
    }
    
    shop_service.shop_repo.update_shop_item(item_id, item_data)
    
    # 更新成本（先删除旧的，再添加新的）
    # 这里简化处理，实际项目中可能需要更精细的更新逻辑
    costs = shop_service.shop_repo.get_item_costs(item_id)
    for cost in costs:
        shop_service.shop_repo.delete_item_cost(cost["cost_id"])
    
    # 添加新成本
    cost_full_ids = data.getlist("cost_item_full_id") if hasattr(data, 'getlist') else []
    cost_amounts = data.getlist("cost_amount") if hasattr(data, 'getlist') else []
    cost_relations = data.getlist("cost_relation") if hasattr(data, 'getlist') else []
    cost_groups = data.getlist("cost_group") if hasattr(data, 'getlist') else []
    cost_quality_levels = data.getlist("cost_quality_level") if hasattr(data, 'getlist') else []
    
    for idx, full_id in enumerate(cost_full_ids):
        if not full_id:
            continue
        amount_text = cost_amounts[idx] if idx < len(cost_amounts) else ""
        if not amount_text:
            continue
        try:
            amount_val = int(amount_text)
        except Exception:
            continue
            
        t, _, id_text = full_id.partition('-')
        cost_data = {
            "cost_type": t,
            "cost_amount": amount_val,
            "cost_relation": cost_relations[idx] if idx < len(cost_relations) else "and",
            "group_id": int(cost_groups[idx]) if idx < len(cost_groups) and cost_groups[idx] else None,
            "quality_level": int(cost_quality_levels[idx]) if idx < len(cost_quality_levels) and cost_quality_levels[idx] else 0,
        }
        
        if t in ("fish", "item", "rod", "accessory"):
            try:
                cost_data["cost_item_id"] = int(id_text)
            except Exception:
                continue
        
        shop_service.shop_repo.add_item_cost(item_id, cost_data)
    
    # 更新奖励（先删除旧的，再添加新的）
    rewards = shop_service.shop_repo.get_item_rewards(item_id)
    for reward in rewards:
        shop_service.shop_repo.delete_item_reward(reward["reward_id"])
    
    # 添加新奖励
    reward_full_ids = data.getlist("reward_item_full_id") if hasattr(data, 'getlist') else []
    reward_quantities = data.getlist("reward_quantity") if hasattr(data, 'getlist') else []
    reward_refine_levels = data.getlist("reward_refine_level") if hasattr(data, 'getlist') else []
    reward_quality_levels = data.getlist("reward_quality_level") if hasattr(data, 'getlist') else []
    
    for idx, full_id in enumerate(reward_full_ids):
        if not full_id:
            continue
        qty_text = reward_quantities[idx] if idx < len(reward_quantities) else "1"
        try:
            qty_val = int(qty_text or "1")
        except Exception:
            qty_val = 1
            
        t, _, id_text = full_id.partition('-')
        reward_data = {
            "reward_type": t,
            "reward_quantity": qty_val,
            "reward_refine_level": int(reward_refine_levels[idx]) if idx < len(reward_refine_levels) and reward_refine_levels[idx] else None,
            "quality_level": int(reward_quality_levels[idx]) if idx < len(reward_quality_levels) and reward_quality_levels[idx] else 0,
        }
        
        try:
            reward_data["reward_item_id"] = int(id_text)
        except Exception:
            continue
            
        shop_service.shop_repo.add_item_reward(item_id, reward_data)
    
    return redirect(url_for("admin_bp.manage_shop_details", shop_id=shop_id))

@admin_bp.route("/shops/<int:shop_id>/items/remove/<int:item_id>", methods=["POST"])
@login_required
async def remove_shop_item(shop_id, item_id):
    shop_service = current_app.config["SHOP_SERVICE"]
    
    # 删除商品（会自动删除相关的成本和奖励）
    shop_service.shop_repo.delete_shop_item(item_id)
    await flash("商品已删除", "success")
    
    return redirect(url_for("admin_bp.manage_shop_details", shop_id=shop_id))

@admin_bp.route("/api/shops/<int:shop_id>/items", methods=["POST"])
@login_required
async def api_add_shop_item(shop_id):
    payload = await request.get_json()
    shop_service = current_app.config["SHOP_SERVICE"]
    created = shop_service.shop_repo.create_shop_item(shop_id, payload or {})
    return jsonify({"success": True, "item": created})

@admin_bp.route("/api/shop/items/<int:item_id>", methods=["PUT"])
@login_required
async def api_update_shop_item(item_id):
    payload = await request.get_json()
    shop_service = current_app.config["SHOP_SERVICE"]
    shop_service.shop_repo.update_shop_item(item_id, payload or {})
    return jsonify({"success": True})

@admin_bp.route("/api/shop/items/<int:item_id>", methods=["DELETE"])
@login_required
async def api_delete_shop_item(item_id):
    shop_service = current_app.config["SHOP_SERVICE"]
    shop_service.shop_repo.delete_shop_item(item_id)
    return jsonify({"success": True})

# 创建商品模板路由
@admin_bp.route("/offers/create", methods=["POST"])
@login_required
async def create_offer():
    """创建新的商品模板"""
    data = await request.form
    shop_service = current_app.config["SHOP_SERVICE"]
    
    try:
        # 解析表单数据
        offer_data = {
            "name": data.get("name"),
            "description": data.get("description"),
            "category": "general",  # 添加默认分类
            "is_active": data.get("is_active") == "on",
            "start_time": data.get("start_time") or None,
            "end_time": data.get("end_time") or None,
            "per_user_limit": int(data.get("per_user_limit")) if data.get("per_user_limit") else None,
            "per_user_daily_limit": int(data.get("per_user_daily_limit")) if data.get("per_user_daily_limit") else None,
            "stock_total": int(data.get("stock_total")) if data.get("stock_total") else None,
            "sort_order": int(data.get("sort_order", 100))
        }
        
        # 解析成本
        costs = []
        cost_full_ids = data.getlist("cost_item_full_id") if hasattr(data, 'getlist') else []
        cost_amounts = data.getlist("cost_amount") if hasattr(data, 'getlist') else []
        for idx, full_id in enumerate(cost_full_ids):
            if not full_id:
                continue
            amount_text = cost_amounts[idx] if idx < len(cost_amounts) else ""
            if not amount_text:
                continue
            try:
                amount_val = int(amount_text)
            except Exception:
                continue
            t, _, id_text = full_id.partition('-')
            if t in ("coins", "premium"):
                costs.append({"cost_type": t, "item_id": None, "amount": amount_val})
            elif t in ("fish", "item"):
                try:
                    item_id_val = int(id_text)
                except Exception:
                    continue
                costs.append({"cost_type": t, "item_id": item_id_val, "amount": amount_val})
        
        # 解析奖励
        rewards = []
        reward_item_types = data.getlist("reward_item_type")
        reward_item_ids = data.getlist("reward_item_id")
        reward_quantities = data.getlist("reward_quantity")
        reward_refine_levels = data.getlist("reward_refine_level")
        
        for i, item_type in enumerate(reward_item_types):
            if item_type and reward_item_ids[i] and reward_quantities[i]:
                reward_data = {
                    "item_type": item_type,
                    "item_id": int(reward_item_ids[i]),
                    "quantity": int(reward_quantities[i])
                }
                if reward_refine_levels[i]:
                    reward_data["refine_level"] = int(reward_refine_levels[i])
                rewards.append(reward_data)
        
        # 创建商品
        offer = shop_service.shop_repo.create_offer(offer_data, costs)
        
        # 添加奖励
        for reward_data in rewards:
            shop_service.shop_repo.add_reward(offer.offer_id, reward_data)
        
        return redirect(url_for("admin_bp.manage_shops"))
        
    except Exception as e:
        logger.error(f"创建商品失败: {e}")
        return redirect(url_for("admin_bp.manage_shops"))

# 旧的商品管理API路由已移除，功能已集成到商店详情页面