import functools
import os.path
import sys

from quart import Quart, render_template, request, redirect, url_for, session, flash, Blueprint,current_app

from ..db import FishingDB

admin_bp = Blueprint(
    'admin_bp',
    __name__,
    template_folder='templates',
    static_folder='static',
)

# 工厂函数，用于创建和配置Quart应用
def create_app(db_instance, secret_key):
    app = Quart(__name__)
    app.secret_key = os.urandom(24) # 用于session加密
    app.config['DB'] = db_instance
    app.config['SECRET_LOGIN_KEY'] = secret_key

    # 注册Blueprint
    app.register_blueprint(admin_bp, url_prefix='/admin') # 所有后台URL都以 /admin 开头

    @app.route("/")
    def root():
        return redirect(url_for('admin_bp.index'))
    return app

# 登录验证装饰器
def login_required(f):
    @functools.wraps(f)
    async def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('admin_bp.login'))
        return await f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/login', methods=['GET', 'POST'])
async def login():
    if request.method == 'POST':
        form = await request.form
        # 从应用中获取密钥
        secret_key = current_app.config['SECRET_LOGIN_KEY']
        if form.get('secret_key') == secret_key:
            session['logged_in'] = True
            await flash('登录成功！', 'success')
            return redirect(url_for('admin_bp.index'))
        else:
            await flash('登录失败，请检查密钥！', 'danger')
    return await render_template('login.html')

@admin_bp.route('/logout')
async def logout():
    session.pop('logged_in', None)
    await flash("你已成功登出。", "info")
    return redirect(url_for('admin_bp.login'))

@admin_bp.route('/')
@login_required
async def index():
    return await render_template('index.html')

# --- 鱼类管理 ---
@admin_bp.route('/fish')
@login_required
async def manage_fish():
    db = current_app.config['DB']
    fishes = db.get_all_fish()
    return await render_template('fish.html', fishes=fishes)

@admin_bp.route('/fish/add', methods=['POST'])
@login_required
async def add_fish():
    form = await request.form
    db = current_app.config['DB']
    db.add_fish(form)
    await flash("鱼类添加成功！", "success")
    return redirect(url_for('admin_bp.manage_fish'))

@admin_bp.route('/fish/edit/<int:fish_id>', methods=['POST'])
@login_required
async def edit_fish(fish_id):
    form = await request.form
    db = current_app.config['DB']
    db.update_fish(fish_id, form)
    await flash(f"鱼类ID {fish_id} 更新成功！", "success")
    return redirect(url_for('admin_bp.manage_fish'))

@admin_bp.route('/fish/delete/<int:fish_id>', methods=['POST'])
@login_required
async def delete_fish(fish_id):
    db = current_app.config['DB']
    db.delete_fish(fish_id)
    await flash(f"鱼类ID {fish_id} 已删除！", "warning")
    return redirect(url_for('admin_bp.manage_fish'))


# --- 鱼竿管理 ---
@admin_bp.route('/rods')
@login_required
async def manage_rods():
    db = current_app.config['DB']
    items = db.get_all_rods_admin()
    return await render_template('rods.html', items=items)


@admin_bp.route('/rods/add', methods=['POST'])
@login_required
async def add_rod():
    form = await request.form
    db = current_app.config['DB']
    db.add_rod_admin(form)
    await flash("鱼竿添加成功！", "success")
    return redirect(url_for('admin_bp.manage_rods'))


@admin_bp.route('/rods/edit/<int:rod_id>', methods=['POST'])
@login_required
async def edit_rod(rod_id):
    form = await request.form
    db = current_app.config['DB']
    db.update_rod_admin(rod_id, form)
    await flash(f"鱼竿ID {rod_id} 更新成功！", "success")
    return redirect(url_for('admin_bp.manage_rods'))


@admin_bp.route('/rods/delete/<int:rod_id>', methods=['POST'])
@login_required
async def delete_rod(rod_id):
    db = current_app.config['DB']
    db.delete_rod_admin(rod_id)
    await flash(f"鱼竿ID {rod_id} 已删除！", "warning")
    return redirect(url_for('admin_bp.manage_rods'))


# --- 鱼饵管理 ---
@admin_bp.route('/baits')
@login_required
async def manage_baits():
    db = current_app.config['DB']
    items = db.get_all_baits_admin()
    return await render_template('baits.html', items=items)


@admin_bp.route('/baits/add', methods=['POST'])
@login_required
async def add_bait():
    form = await request.form
    db = current_app.config['DB']
    db.add_bait_admin(form)
    await flash("鱼饵添加成功！", "success")
    return redirect(url_for('admin_bp.manage_baits'))


@admin_bp.route('/baits/edit/<int:bait_id>', methods=['POST'])
@login_required
async def edit_bait(bait_id):
    form = await request.form
    db = current_app.config['DB']
    db.update_bait_admin(bait_id, form)
    await flash(f"鱼饵ID {bait_id} 更新成功！", "success")
    return redirect(url_for('admin_bp.manage_baits'))


@admin_bp.route('/baits/delete/<int:bait_id>', methods=['POST'])
@login_required
async def delete_bait(bait_id):
    db = current_app.config['DB']
    db.delete_bait_admin(bait_id)
    await flash(f"鱼饵ID {bait_id} 已删除！", "warning")
    return redirect(url_for('admin_bp.manage_baits'))


# --- 饰品管理 ---
@admin_bp.route('/accessories')
@login_required
async def manage_accessories():
    db = current_app.config['DB']
    items = db.get_all_accessories_admin()
    return await render_template('accessories.html', items=items)


@admin_bp.route('/accessories/add', methods=['POST'])
@login_required
async def add_accessory():
    form = await request.form
    db = current_app.config['DB']
    db.add_accessory_admin(form)
    await flash("饰品添加成功！", "success")
    return redirect(url_for('admin_bp.manage_accessories'))


@admin_bp.route('/accessories/edit/<int:accessory_id>', methods=['POST'])
@login_required
async def edit_accessory(accessory_id):
    form = await request.form
    db = current_app.config['DB']
    db.update_accessory_admin(accessory_id, form)
    await flash(f"饰品ID {accessory_id} 更新成功！", "success")
    return redirect(url_for('admin_bp.manage_accessories'))


@admin_bp.route('/accessories/delete/<int:accessory_id>', methods=['POST'])
@login_required
async def delete_accessory(accessory_id):
    db = current_app.config['DB']
    db.delete_accessory_admin(accessory_id)
    await flash(f"饰品ID {accessory_id} 已删除！", "warning")
    return redirect(url_for('admin_bp.manage_accessories'))


# --- 抽卡池管理 ---
@admin_bp.route('/gacha')
@login_required
async def manage_gacha():
    db = current_app.config['DB']
    pools = db.get_all_gacha_pools()  # 使用你已有的 get_all_gacha_pools 方法
    return await render_template('gacha.html', pools=pools)


@admin_bp.route('/gacha/add', methods=['POST'])
@login_required
async def add_gacha_pool():
    form = await request.form
    db = current_app.config['DB']
    db.add_gacha_pool_admin(form)
    await flash("奖池添加成功！", "success")
    return redirect(url_for('admin_bp.manage_gacha'))


@admin_bp.route('/gacha/edit/<int:pool_id>', methods=['POST'])
@login_required
async def edit_gacha_pool(pool_id):
    form = await request.form
    db = current_app.config['DB']
    db.update_gacha_pool_admin(pool_id, form)
    await flash(f"奖池ID {pool_id} 更新成功！", "success")
    return redirect(url_for('admin_bp.manage_gacha'))


@admin_bp.route('/gacha/delete/<int:pool_id>', methods=['POST'])
@login_required
async def delete_gacha_pool(pool_id):
    db = current_app.config['DB']
    db.delete_gacha_pool_admin(pool_id)
    await flash(f"奖池ID {pool_id} 已删除！", "warning")
    return redirect(url_for('admin_bp.manage_gacha'))


# --- 奖池物品详情管理 ---
@admin_bp.route('/gacha/pool/<int:pool_id>')
@login_required
async def manage_gacha_pool_details(pool_id):
    db = current_app.config['DB']
    pool = db.get_gacha_pool_admin(pool_id)
    if not pool:
        await flash("找不到指定的奖池！", "danger")
        return redirect(url_for('admin_bp.manage_gacha'))

    items_in_pool = db.get_items_in_pool_admin(pool_id)

    # 为了方便在前端下拉框中选择，我们需要获取所有可作为奖品的物品
    all_rods = db.get_all_rods_admin()
    all_baits = db.get_all_baits_admin()
    all_accessories = db.get_all_accessories_admin()

    return await render_template(
        'gacha_pool_details.html',
        pool=pool,
        items=items_in_pool,
        all_rods=all_rods,
        all_baits=all_baits,
        all_accessories=all_accessories
    )


@admin_bp.route('/gacha/pool/<int:pool_id>/add_item', methods=['POST'])
@login_required
async def add_item_to_pool(pool_id):
    form = await request.form
    db = current_app.config['DB']
    db.add_item_to_pool_admin(pool_id, form)
    await flash("成功向奖池中添加物品！", "success")
    return redirect(url_for('admin_bp.manage_gacha_pool_details', pool_id=pool_id))


@admin_bp.route('/gacha/pool/edit_item/<int:item_id>', methods=['POST'])
@login_required
async def edit_pool_item(item_id):
    form = await request.form
    db = current_app.config['DB']
    # 注意：需要从表单中获取pool_id以便重定向
    pool_id = request.args.get('pool_id')
    db.update_pool_item_admin(item_id, form)
    await flash(f"奖池物品ID {item_id} 更新成功！", "success")
    return redirect(url_for('admin_bp.manage_gacha_pool_details', pool_id=pool_id))


@admin_bp.route('/gacha/pool/delete_item/<int:item_id>', methods=['POST'])
@login_required
async def delete_pool_item(item_id):
    db = current_app.config['DB']
    pool_id = request.args.get('pool_id')
    db.delete_pool_item_admin(item_id)
    await flash(f"奖池物品ID {item_id} 已删除！", "warning")
    return redirect(url_for('admin_bp.manage_gacha_pool_details', pool_id=pool_id))