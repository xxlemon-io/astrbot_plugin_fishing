import asyncio
from hypercorn.config import Config
from hypercorn.asyncio import serve

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.star.filter.permission import PermissionType
from astrbot.api.message_components import At, Node, Plain

from ..utils import parse_target_user_id, _is_port_available
from ..manager.server import create_app


async def modify_coins(self, event: AstrMessageEvent):
    """修改用户金币"""
    args = event.message_str.split(" ")
    
    # 解析目标用户ID（支持@和用户ID两种方式）
    target_user_id, error_msg = parse_target_user_id(event, args, 1)
    if error_msg:
        yield event.plain_result(error_msg)
        return
    
    # 检查金币数量参数
    if len(args) < 3:
        yield event.plain_result("❌ 请指定金币数量，例如：/修改金币 @用户 1000 或 /修改金币 123456789 1000")
        return
    
    coins = args[2]
    if not coins.isdigit():
        yield event.plain_result("❌ 金币数量必须是数字，请检查后重试。")
        return
    
    if result := self.user_service.modify_user_coins(target_user_id, int(coins)):
        yield event.plain_result(f"✅ 成功修改用户 {target_user_id} 的金币数量为 {coins} 金币")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def modify_premium(self, event: AstrMessageEvent):
    """修改用户高级货币"""
    args = event.message_str.split(" ")
    
    # 解析目标用户ID（支持@和用户ID两种方式）
    target_user_id, error_msg = parse_target_user_id(event, args, 1)
    if error_msg:
        yield event.plain_result(error_msg)
        return
    
    # 检查高级货币数量参数
    if len(args) < 3:
        yield event.plain_result("❌ 请指定高级货币数量，例如：/修改高级货币 @用户 100 或 /修改高级货币 123456789 100")
        return
    
    premium = args[2]
    if not premium.isdigit():
        yield event.plain_result("❌ 高级货币数量必须是数字，请检查后重试。")
        return
    
    user = self.user_repo.get_by_id(target_user_id)
    if not user:
        yield event.plain_result("❌ 用户不存在或未注册，请检查后重试。")
        return
    user.premium_currency = int(premium)
    self.user_repo.update(user)
    yield event.plain_result(f"✅ 成功修改用户 {target_user_id} 的高级货币为 {premium}")

async def reward_premium(self, event: AstrMessageEvent):
    """奖励用户高级货币"""
    args = event.message_str.split(" ")
    
    # 解析目标用户ID（支持@和用户ID两种方式）
    target_user_id, error_msg = parse_target_user_id(event, args, 1)
    if error_msg:
        yield event.plain_result(error_msg)
        return
    
    # 检查高级货币数量参数
    if len(args) < 3:
        yield event.plain_result("❌ 请指定高级货币数量，例如：/奖励高级货币 @用户 100 或 /奖励高级货币 123456789 100")
        return
    
    premium = args[2]
    if not premium.isdigit():
        yield event.plain_result("❌ 高级货币数量必须是数字，请检查后重试。")
        return
    
    user = self.user_repo.get_by_id(target_user_id)
    if not user:
        yield event.plain_result("❌ 用户不存在或未注册，请检查后重试。")
        return
    user.premium_currency += int(premium)
    self.user_repo.update(user)
    yield event.plain_result(f"✅ 成功给用户 {target_user_id} 奖励 {premium} 高级货币")

async def deduct_premium(self, event: AstrMessageEvent):
    """扣除用户高级货币"""
    args = event.message_str.split(" ")
    
    # 解析目标用户ID（支持@和用户ID两种方式）
    target_user_id, error_msg = parse_target_user_id(event, args, 1)
    if error_msg:
        yield event.plain_result(error_msg)
        return
    
    # 检查高级货币数量参数
    if len(args) < 3:
        yield event.plain_result("❌ 请指定高级货币数量，例如：/扣除高级货币 @用户 100 或 /扣除高级货币 123456789 100")
        return
    
    premium = args[2]
    if not premium.isdigit():
        yield event.plain_result("❌ 高级货币数量必须是数字，请检查后重试。")
        return
    
    user = self.user_repo.get_by_id(target_user_id)
    if not user:
        yield event.plain_result("❌ 用户不存在或未注册，请检查后重试。")
        return
    if int(premium) > user.premium_currency:
        yield event.plain_result("❌ 扣除的高级货币不能超过用户当前拥有数量")
        return
    user.premium_currency -= int(premium)
    self.user_repo.update(user)
    yield event.plain_result(f"✅ 成功扣除用户 {target_user_id} 的 {premium} 高级货币")

async def reward_all_coins(self, event: AstrMessageEvent):
    """给所有注册用户发放金币"""
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result("❌ 请指定奖励的金币数量，例如：/全体奖励金币 1000")
        return
    amount = args[1]
    if not amount.isdigit() or int(amount) <= 0:
        yield event.plain_result("❌ 奖励数量必须是正整数，请检查后重试。")
        return
    amount_int = int(amount)
    user_ids = self.user_repo.get_all_user_ids()
    if not user_ids:
        yield event.plain_result("❌ 当前没有注册用户。")
        return
    updated = 0
    for uid in user_ids:
        user = self.user_repo.get_by_id(uid)
        if not user:
            continue
        user.coins += amount_int
        self.user_repo.update(user)
        updated += 1
    yield event.plain_result(f"✅ 已向 {updated} 位用户每人发放 {amount_int} 金币")

async def reward_all_premium(self, event: AstrMessageEvent):
    """给所有注册用户发放高级货币"""
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result("❌ 请指定奖励的高级货币数量，例如：/全体奖励高级货币 100")
        return
    amount = args[1]
    if not amount.isdigit() or int(amount) <= 0:
        yield event.plain_result("❌ 奖励数量必须是正整数，请检查后重试。")
        return
    amount_int = int(amount)
    user_ids = self.user_repo.get_all_user_ids()
    if not user_ids:
        yield event.plain_result("❌ 当前没有注册用户。")
        return
    updated = 0
    for uid in user_ids:
        user = self.user_repo.get_by_id(uid)
        if not user:
            continue
        user.premium_currency += amount_int
        self.user_repo.update(user)
        updated += 1
    yield event.plain_result(f"✅ 已向 {updated} 位用户每人发放 {amount_int} 高级货币")

async def deduct_all_coins(self, event: AstrMessageEvent):
    """从所有注册用户扣除金币（不低于0）"""
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result("❌ 请指定扣除的金币数量，例如：/全体扣除金币 1000")
        return
    amount = args[1]
    if not amount.isdigit() or int(amount) <= 0:
        yield event.plain_result("❌ 扣除数量必须是正整数，请检查后重试。")
        return
    amount_int = int(amount)
    user_ids = self.user_repo.get_all_user_ids()
    if not user_ids:
        yield event.plain_result("❌ 当前没有注册用户。")
        return
    affected = 0
    total_deducted = 0
    for uid in user_ids:
        user = self.user_repo.get_by_id(uid)
        if not user:
            continue
        if user.coins <= 0:
            continue
        deduct = min(user.coins, amount_int)
        if deduct <= 0:
            continue
        user.coins -= deduct
        self.user_repo.update(user)
        affected += 1
        total_deducted += deduct
    yield event.plain_result(f"✅ 已从 {affected} 位用户总计扣除 {total_deducted} 金币（每人至多 {amount_int}）")

async def deduct_all_premium(self, event: AstrMessageEvent):
    """从所有注册用户扣除高级货币（不低于0）"""
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result("❌ 请指定扣除的高级货币数量，例如：/全体扣除高级货币 100")
        return
    amount = args[1]
    if not amount.isdigit() or int(amount) <= 0:
        yield event.plain_result("❌ 扣除数量必须是正整数，请检查后重试。")
        return
    amount_int = int(amount)
    user_ids = self.user_repo.get_all_user_ids()
    if not user_ids:
        yield event.plain_result("❌ 当前没有注册用户。")
        return
    affected = 0
    total_deducted = 0
    for uid in user_ids:
        user = self.user_repo.get_by_id(uid)
        if not user:
            continue
        if user.premium_currency <= 0:
            continue
        deduct = min(user.premium_currency, amount_int)
        if deduct <= 0:
            continue
        user.premium_currency -= deduct
        self.user_repo.update(user)
        affected += 1
        total_deducted += deduct
    yield event.plain_result(f"✅ 已从 {affected} 位用户总计扣除 {total_deducted} 高级货币（每人至多 {amount_int}）")
async def reward_coins(self, event: AstrMessageEvent):
    """奖励用户金币"""
    args = event.message_str.split(" ")
    
    # 解析目标用户ID（支持@和用户ID两种方式）
    target_user_id, error_msg = parse_target_user_id(event, args, 1)
    if error_msg:
        yield event.plain_result(error_msg)
        return
    
    # 检查金币数量参数
    if len(args) < 3:
        yield event.plain_result("❌ 请指定金币数量，例如：/奖励金币 @用户 1000 或 /奖励金币 123456789 1000")
        return
    
    coins = args[2]
    if not coins.isdigit():
        yield event.plain_result("❌ 金币数量必须是数字，请检查后重试。")
        return
    
    if (current_coins := self.user_service.get_user_currency(target_user_id)) is None:
        yield event.plain_result("❌ 用户不存在或未注册，请检查后重试。")
        return
    if result := self.user_service.modify_user_coins(target_user_id, int(current_coins.get('coins') + int(coins))):
        yield event.plain_result(f"✅ 成功给用户 {target_user_id} 奖励 {coins} 金币")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def deduct_coins(self, event: AstrMessageEvent):
    """扣除用户金币"""
    args = event.message_str.split(" ")
    
    # 解析目标用户ID（支持@和用户ID两种方式）
    target_user_id, error_msg = parse_target_user_id(event, args, 1)
    if error_msg:
        yield event.plain_result(error_msg)
        return
    
    # 检查金币数量参数
    if len(args) < 3:
        yield event.plain_result("❌ 请指定金币数量，例如：/扣除金币 @用户 1000 或 /扣除金币 123456789 1000")
        return
    
    coins = args[2]
    if not coins.isdigit():
        yield event.plain_result("❌ 金币数量必须是数字，请检查后重试。")
        return
    
    if (current_coins := self.user_service.get_user_currency(target_user_id)) is None:
        yield event.plain_result("❌ 用户不存在或未注册，请检查后重试。")
        return
    if int(coins) > current_coins.get('coins'):
        yield event.plain_result("❌ 扣除的金币数量不能超过用户当前拥有的金币数量")
        return
    if result := self.user_service.modify_user_coins(target_user_id, int(current_coins.get('coins') - int(coins))):
        yield event.plain_result(f"✅ 成功扣除用户 {target_user_id} 的 {coins} 金币")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")

async def start_admin(self, event: AstrMessageEvent):
    if self.web_admin_task and not self.web_admin_task.done():
        yield event.plain_result("❌ 钓鱼后台管理已经在运行中")
        return
    yield event.plain_result("🔄 正在启动钓鱼插件Web管理后台...")

    if not await _is_port_available(self.port):
        yield event.plain_result(f"❌ 端口 {self.port} 已被占用，请更换端口后重试")
        return

    try:
        services_to_inject = {
            "item_template_service": self.item_template_service,
            "user_service": self.user_service,
            "market_service": self.market_service,
            "fishing_zone_service": self.fishing_zone_service,
            "shop_service": self.shop_service,
        }
        app = create_app(
            secret_key=self.secret_key,
            services=services_to_inject
        )
        config = Config()
        config.bind = [f"0.0.0.0:{self.port}"]
        self.web_admin_task = asyncio.create_task(serve(app, config))

        # 等待服务启动
        for i in range(10):
            if await self._check_port_active():
                break
            await asyncio.sleep(1)
        else:
            raise TimeoutError("⌛ 启动超时，请检查防火墙设置")

        await asyncio.sleep(1)  # 等待服务启动

        yield event.plain_result(f"✅ 钓鱼后台已启动！\n🔗请访问 http://localhost:{self.port}/admin\n🔑 密钥请到配置文件中查看\n\n⚠️ 重要提示：\n• 如需公网访问，请自行配置端口转发和防火墙规则\n• 确保端口 {self.port} 已开放并映射到公网IP\n• 建议使用反向代理（如Nginx）增强安全性")
    except Exception as e:
        logger.error(f"启动后台失败: {e}", exc_info=True)
        yield event.plain_result(f"❌ 启动后台失败: {e}")

async def stop_admin(self, event: AstrMessageEvent):
    """关闭钓鱼后台管理"""
    if not hasattr(self, "web_admin_task") or not self.web_admin_task or self.web_admin_task.done():
        yield event.plain_result("❌ 钓鱼后台管理没有在运行中")
        return

    try:
        # 1. 请求取消任务
        self.web_admin_task.cancel()
        # 2. 等待任务实际被取消
        await self.web_admin_task
    except asyncio.CancelledError:
        # 3. 捕获CancelledError，这是成功关闭的标志
        logger.info("钓鱼插件Web管理后台已成功关闭")
        yield event.plain_result("✅ 钓鱼后台已关闭")
    except Exception as e:
        # 4. 捕获其他可能的意外错误
        logger.error(f"关闭钓鱼后台管理时发生意外错误: {e}", exc_info=True)
        yield event.plain_result(f"❌ 关闭钓鱼后台管理失败: {e}")

async def sync_initial_data(self, event: AstrMessageEvent):
    """从 initial_data.py 同步所有初始设定（道具、商店等）。"""
    try:
        self.data_setup_service.sync_all_initial_data()
        yield event.plain_result("✅ 所有初始设定数据同步成功！")
    except Exception as e:
        logger.error(f"同步初始设定数据时出错: {e}")
        yield event.plain_result(f"❌ 同步初始设定数据失败: {e}")

async def impersonate_start(self, event: AstrMessageEvent):
    """管理员开始扮演一名用户。"""
    admin_id = event.get_sender_id()
    args = event.message_str.split(" ")
    
    # 如果已经在线，则显示当前状态
    if admin_id in self.impersonation_map:
        target_user_id = self.impersonation_map[admin_id]
        target_user = self.user_repo.get_by_id(target_user_id)
        nickname = target_user.nickname if target_user else '未知用户'
        yield event.plain_result(f"您当前正在代理用户: {nickname} ({target_user_id})")
        return
    
    # 解析目标用户ID（支持@和用户ID两种方式）
    target_user_id, error_msg = parse_target_user_id(event, args, 1)
    if error_msg:
        yield event.plain_result(f"用法: /代理上线 <目标用户ID> 或 /代理上线 @用户\n{error_msg}")
        return

    target_user = self.user_repo.get_by_id(target_user_id)
    if not target_user:
        yield event.plain_result("❌ 目标用户不存在。")
        return

    self.impersonation_map[admin_id] = target_user_id
    nickname = target_user.nickname
    yield event.plain_result(f"✅ 您已成功代理用户: {nickname} ({target_user_id})。\n现在您发送的所有游戏指令都将以该用户的身份执行。\n使用 /代理下线 结束代理。")

async def impersonate_stop(self, event: AstrMessageEvent):
    """管理员结束扮演用户。"""
    admin_id = event.get_sender_id()
    if admin_id in self.impersonation_map:
        del self.impersonation_map[admin_id]
        yield event.plain_result("✅ 您已成功结束代理。")
    else:
        yield event.plain_result("❌ 您当前没有在代理任何用户。")

async def reward_all_items(self, event: AstrMessageEvent):
    """给所有注册用户发放道具"""
    args = event.message_str.split(" ")
    if len(args) < 4:
        yield event.plain_result("❌ 请指定道具类型、道具ID和数量，例如：/全体发放道具 item 1 5")
        return
    
    item_type = args[1]
    item_id_str = args[2]
    quantity_str = args[3]
    
    # 验证道具ID
    if not item_id_str.isdigit():
        yield event.plain_result("❌ 道具ID必须是数字，请检查后重试。")
        return
    item_id = int(item_id_str)
    
    # 验证数量
    if not quantity_str.isdigit() or int(quantity_str) <= 0:
        yield event.plain_result("❌ 数量必须是正整数，请检查后重试。")
        return
    quantity = int(quantity_str)
    
    # 验证道具类型
    valid_types = ["item", "bait", "rod", "accessory"]
    if item_type not in valid_types:
        yield event.plain_result(f"❌ 不支持的道具类型。支持的类型：{', '.join(valid_types)}")
        return
    
    # 验证道具是否存在
    item_template = None
    if item_type == "item":
        item_template = self.item_template_repo.get_item_by_id(item_id)
    elif item_type == "bait":
        item_template = self.item_template_repo.get_bait_by_id(item_id)
    elif item_type == "rod":
        item_template = self.item_template_repo.get_rod_by_id(item_id)
    elif item_type == "accessory":
        item_template = self.item_template_repo.get_accessory_by_id(item_id)
    
    if not item_template:
        yield event.plain_result(f"❌ 道具不存在，请检查道具ID和类型。")
        return
    
    # 获取所有用户ID
    user_ids = self.user_repo.get_all_user_ids()
    if not user_ids:
        yield event.plain_result("❌ 当前没有注册用户。")
        return
    
    # 给所有用户发放道具
    success_count = 0
    failed_count = 0
    
    for user_id in user_ids:
        try:
            result = self.user_service.add_item_to_user_inventory(user_id, item_type, item_id, quantity)
            if result.get("success", False):
                success_count += 1
            else:
                failed_count += 1
        except Exception as e:
            failed_count += 1
            logger.error(f"给用户 {user_id} 发放道具失败: {e}")
    
    item_name = getattr(item_template, 'name', f'ID:{item_id}')
    yield event.plain_result(f"✅ 全体发放道具完成！\n📦 道具：{item_name} x{quantity}\n✅ 成功：{success_count} 位用户\n❌ 失败：{failed_count} 位用户")

async def update_exchange_prices(self, event: AstrMessageEvent):
    """手动更新交易所价格（管理员）"""
    try:
        result = self.exchange_service.manual_update_prices()
        
        if result["success"]:
            # 格式化价格显示
            price_info = []
            for commodity_id, price in result["prices"].items():
                commodity_name = self.exchange_service.commodities.get(commodity_id, {}).name if commodity_id in self.exchange_service.commodities else commodity_id
                price_info.append(f"• {commodity_name}: {price:,} 金币")
            
            price_display = "\n".join(price_info)
            yield event.plain_result(f"✅ 交易所价格更新成功！\n\n📊 当前价格：\n{price_display}")
        else:
            yield event.plain_result(f"❌ 价格更新失败：{result['message']}")
            
    except Exception as e:
        logger.error(f"手动更新价格失败: {e}")
        yield event.plain_result("❌ 价格更新失败，请稍后再试。")