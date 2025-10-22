import asyncio
from hypercorn.config import Config
from hypercorn.asyncio import serve

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.star.filter.permission import PermissionType
from astrbot.api.message_components import At, Node, Plain

from ..utils import parse_target_user_id, _is_port_available
from ..manager.server import create_app
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import FishingPlugin


async def modify_coins(plugin: "FishingPlugin", event: AstrMessageEvent):
    """修改用户金币"""
    args = event.message_str.split(" ")

    # 解析目标用户ID（支持@和用户ID两种方式）
    target_user_id, error_msg = parse_target_user_id(event, args, 1)
    if error_msg:
        yield event.plain_result(error_msg)
        return

    # 检查金币数量参数
    if len(args) < 3:
        yield event.plain_result(
            "❌ 请指定金币数量，例如：/修改金币 @用户 1000 或 /修改金币 123456789 1000"
        )
        return

    coins = args[2]
    if not coins.isdigit():
        yield event.plain_result("❌ 金币数量必须是数字，请检查后重试。")
        return

    if result := plugin.user_service.modify_user_coins(target_user_id, int(coins)):
        yield event.plain_result(
            f"✅ 成功修改用户 {target_user_id} 的金币数量为 {coins} 金币"
        )
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")


async def modify_premium(plugin: "FishingPlugin", event: AstrMessageEvent):
    """修改用户高级货币"""
    args = event.message_str.split(" ")

    # 解析目标用户ID（支持@和用户ID两种方式）
    target_user_id, error_msg = parse_target_user_id(event, args, 1)
    if error_msg:
        yield event.plain_result(error_msg)
        return

    # 检查高级货币数量参数
    if len(args) < 3:
        yield event.plain_result(
            "❌ 请指定高级货币数量，例如：/修改高级货币 @用户 100 或 /修改高级货币 123456789 100"
        )
        return

    premium = args[2]
    if not premium.isdigit():
        yield event.plain_result("❌ 高级货币数量必须是数字，请检查后重试。")
        return

    user = plugin.user_repo.get_by_id(target_user_id)
    if not user:
        yield event.plain_result("❌ 用户不存在或未注册，请检查后重试。")
        return
    user.premium_currency = int(premium)
    plugin.user_repo.update(user)
    yield event.plain_result(f"✅ 成功修改用户 {target_user_id} 的高级货币为 {premium}")


async def reward_premium(plugin: "FishingPlugin", event: AstrMessageEvent):
    """奖励用户高级货币"""
    args = event.message_str.split(" ")

    # 解析目标用户ID（支持@和用户ID两种方式）
    target_user_id, error_msg = parse_target_user_id(event, args, 1)
    if error_msg:
        yield event.plain_result(error_msg)
        return

    # 检查高级货币数量参数
    if len(args) < 3:
        yield event.plain_result(
            "❌ 请指定高级货币数量，例如：/奖励高级货币 @用户 100 或 /奖励高级货币 123456789 100"
        )
        return

    premium = args[2]
    if not premium.isdigit():
        yield event.plain_result("❌ 高级货币数量必须是数字，请检查后重试。")
        return

    user = plugin.user_repo.get_by_id(target_user_id)
    if not user:
        yield event.plain_result("❌ 用户不存在或未注册，请检查后重试。")
        return
    user.premium_currency += int(premium)
    plugin.user_repo.update(user)
    yield event.plain_result(f"✅ 成功给用户 {target_user_id} 奖励 {premium} 高级货币")


async def deduct_premium(plugin: "FishingPlugin", event: AstrMessageEvent):
    """扣除用户高级货币"""
    args = event.message_str.split(" ")

    # 解析目标用户ID（支持@和用户ID两种方式）
    target_user_id, error_msg = parse_target_user_id(event, args, 1)
    if error_msg:
        yield event.plain_result(error_msg)
        return

    # 检查高级货币数量参数
    if len(args) < 3:
        yield event.plain_result(
            "❌ 请指定高级货币数量，例如：/扣除高级货币 @用户 100 或 /扣除高级货币 123456789 100"
        )
        return

    premium = args[2]
    if not premium.isdigit():
        yield event.plain_result("❌ 高级货币数量必须是数字，请检查后重试。")
        return

    user = plugin.user_repo.get_by_id(target_user_id)
    if not user:
        yield event.plain_result("❌ 用户不存在或未注册，请检查后重试。")
        return
    if int(premium) > user.premium_currency:
        yield event.plain_result("❌ 扣除的高级货币不能超过用户当前拥有数量")
        return
    user.premium_currency -= int(premium)
    plugin.user_repo.update(user)
    yield event.plain_result(f"✅ 成功扣除用户 {target_user_id} 的 {premium} 高级货币")


async def reward_all_coins(plugin: "FishingPlugin", event: AstrMessageEvent):
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
    user_ids = plugin.user_repo.get_all_user_ids()
    if not user_ids:
        yield event.plain_result("❌ 当前没有注册用户。")
        return
    updated = 0
    for uid in user_ids:
        user = plugin.user_repo.get_by_id(uid)
        if not user:
            continue
        user.coins += amount_int
        plugin.user_repo.update(user)
        updated += 1
    yield event.plain_result(f"✅ 已向 {updated} 位用户每人发放 {amount_int} 金币")


async def reward_all_premium(plugin: "FishingPlugin", event: AstrMessageEvent):
    """给所有注册用户发放高级货币"""
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result(
            "❌ 请指定奖励的高级货币数量，例如：/全体奖励高级货币 100"
        )
        return
    amount = args[1]
    if not amount.isdigit() or int(amount) <= 0:
        yield event.plain_result("❌ 奖励数量必须是正整数，请检查后重试。")
        return
    amount_int = int(amount)
    user_ids = plugin.user_repo.get_all_user_ids()
    if not user_ids:
        yield event.plain_result("❌ 当前没有注册用户。")
        return
    updated = 0
    for uid in user_ids:
        user = plugin.user_repo.get_by_id(uid)
        if not user:
            continue
        user.premium_currency += amount_int
        plugin.user_repo.update(user)
        updated += 1
    yield event.plain_result(f"✅ 已向 {updated} 位用户每人发放 {amount_int} 高级货币")


async def deduct_all_coins(plugin: "FishingPlugin", event: AstrMessageEvent):
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
    user_ids = plugin.user_repo.get_all_user_ids()
    if not user_ids:
        yield event.plain_result("❌ 当前没有注册用户。")
        return
    affected = 0
    total_deducted = 0
    for uid in user_ids:
        user = plugin.user_repo.get_by_id(uid)
        if not user:
            continue
        if user.coins <= 0:
            continue
        deduct = min(user.coins, amount_int)
        if deduct <= 0:
            continue
        user.coins -= deduct
        plugin.user_repo.update(user)
        affected += 1
        total_deducted += deduct
    yield event.plain_result(
        f"✅ 已从 {affected} 位用户总计扣除 {total_deducted} 金币（每人至多 {amount_int}）"
    )


async def deduct_all_premium(plugin: "FishingPlugin", event: AstrMessageEvent):
    """从所有注册用户扣除高级货币（不低于0）"""
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result(
            "❌ 请指定扣除的高级货币数量，例如：/全体扣除高级货币 100"
        )
        return
    amount = args[1]
    if not amount.isdigit() or int(amount) <= 0:
        yield event.plain_result("❌ 扣除数量必须是正整数，请检查后重试。")
        return
    amount_int = int(amount)
    user_ids = plugin.user_repo.get_all_user_ids()
    if not user_ids:
        yield event.plain_result("❌ 当前没有注册用户。")
        return
    affected = 0
    total_deducted = 0
    for uid in user_ids:
        user = plugin.user_repo.get_by_id(uid)
        if not user:
            continue
        if user.premium_currency <= 0:
            continue
        deduct = min(user.premium_currency, amount_int)
        if deduct <= 0:
            continue
        user.premium_currency -= deduct
        plugin.user_repo.update(user)
        affected += 1
        total_deducted += deduct
    yield event.plain_result(
        f"✅ 已从 {affected} 位用户总计扣除 {total_deducted} 高级货币（每人至多 {amount_int}）"
    )


async def reward_coins(plugin: "FishingPlugin", event: AstrMessageEvent):
    """奖励用户金币"""
    args = event.message_str.split(" ")

    # 解析目标用户ID（支持@和用户ID两种方式）
    target_user_id, error_msg = parse_target_user_id(event, args, 1)
    if error_msg:
        yield event.plain_result(error_msg)
        return

    # 检查金币数量参数
    if len(args) < 3:
        yield event.plain_result(
            "❌ 请指定金币数量，例如：/奖励金币 @用户 1000 或 /奖励金币 123456789 1000"
        )
        return

    coins = args[2]
    if not coins.isdigit():
        yield event.plain_result("❌ 金币数量必须是数字，请检查后重试。")
        return

    if (current_coins := plugin.user_service.get_user_currency(target_user_id)) is None:
        yield event.plain_result("❌ 用户不存在或未注册，请检查后重试。")
        return
    if result := plugin.user_service.modify_user_coins(
        target_user_id, int(current_coins.get("coins") + int(coins))
    ):
        yield event.plain_result(f"✅ 成功给用户 {target_user_id} 奖励 {coins} 金币")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")


async def refund_taxes(plugin: "FishingPlugin", event: AstrMessageEvent):
    """退还特定日期范围内的税收（先模拟，再执行）"""
    args = event.message_str.split(" ")
    
    # 检查参数：/退税 开始日期 结束日期 [税收类型] [确认]
    if len(args) < 3:
        yield event.plain_result(
            "❌ 参数不足！\n"
            "用法：\n"
            "  /退税 2024-10-19 2024-10-22 - 模拟运行（查看影响）\n"
            "  /退税 2024-10-19 2024-10-22 确认 - 实际执行退税\n"
            "  /退税 2024-10-19 2024-10-22 每日资产税 确认 - 指定税收类型"
        )
        return
    
    start_date = args[1]
    end_date = args[2]
    
    # 解析可选参数
    tax_type = "每日资产税"  # 默认值
    confirm = False
    
    if len(args) >= 4:
        if args[3] == "确认":
            confirm = True
        elif len(args) >= 5 and args[4] == "确认":
            tax_type = args[3]
            confirm = True
        else:
            tax_type = args[3]
    
    # 验证日期格式
    import re
    date_pattern = r'^\d{4}-\d{2}-\d{2}$'
    if not re.match(date_pattern, start_date) or not re.match(date_pattern, end_date):
        yield event.plain_result("❌ 日期格式错误！请使用 YYYY-MM-DD 格式，例如：2024-10-19")
        return
    
    # 执行退税（模拟或实际）
    dry_run = not confirm
    result = plugin.user_service.refund_taxes_by_date_range(
        start_date=start_date,
        end_date=end_date,
        tax_type=tax_type,
        dry_run=dry_run
    )
    
    if not result.get("success"):
        yield event.plain_result(f"❌ {result.get('message')}")
        return
    
    if dry_run:
        # 模拟运行结果
        message = f"【🔍 退税模拟运行】\n"
        message += f"=" * 40 + "\n"
        message += f"📅 日期范围: {start_date} 至 {end_date}\n"
        message += f"📋 税收类型: {tax_type}\n"
        message += f"👥 影响用户: {result['total_users']} 人\n"
        message += f"💰 总退税额: {result['total_refund_amount']:,} 金币\n\n"
        message += f"【前20位用户预览】\n"
        message += f"-" * 40 + "\n"
        
        for item in result['preview']:
            message += f"  {item['nickname'] or item['user_id']:12s} | "
            message += f"被收税{item['tax_count']:2d}次 | "
            message += f"退还{item['refund_amount']:,}币\n"
        
        message += f"\n⚠️ 这只是模拟运行！\n"
        message += f"若确认无误，请执行：\n"
        message += f"/退税 {start_date} {end_date} {tax_type} 确认"
        
        yield event.plain_result(message)
    else:
        # 实际执行结果
        message = f"【✅ 退税执行完成】\n"
        message += f"=" * 40 + "\n"
        message += f"{result['message']}\n\n"
        message += f"📅 日期范围: {start_date} 至 {end_date}\n"
        message += f"📋 税收类型: {tax_type}\n"
        message += f"✓ 成功: {result['total_users']} 人\n"
        if result['failed_users'] > 0:
            message += f"✗ 失败: {result['failed_users']} 人\n"
        message += f"💰 总退税额: {result['total_refund_amount']:,} 金币\n\n"
        
        if result.get('details'):
            message += f"【部分退税详情（前10位）】\n"
            message += f"-" * 40 + "\n"
            for item in result['details'][:10]:
                message += f"  {item['nickname'] or item['user_id']:12s} | "
                message += f"{item['old_coins']:,} → {item['new_coins']:,}\n"
        
        yield event.plain_result(message)


async def rollback_refund_taxes(plugin: "FishingPlugin", event: AstrMessageEvent):
    """撤回退税操作（先模拟，再执行）"""
    args = event.message_str.split(" ")
    
    # 检查参数：/撤回退税 开始日期 结束日期 [确认]
    if len(args) < 3:
        yield event.plain_result(
            "❌ 参数不足！\n"
            "用法：\n"
            "  /撤回退税 2025-10-19 2025-10-22 - 模拟运行（查看影响）\n"
            "  /撤回退税 2025-10-19 2025-10-22 确认 - 实际执行撤回"
        )
        return
    
    start_date = args[1]
    end_date = args[2]
    confirm = len(args) >= 4 and args[3] == "确认"
    
    # 验证日期格式
    import re
    date_pattern = r'^\d{4}-\d{2}-\d{2}$'
    if not re.match(date_pattern, start_date) or not re.match(date_pattern, end_date):
        yield event.plain_result("❌ 日期格式错误！请使用 YYYY-MM-DD 格式，例如：2025-10-19")
        return
    
    # 执行撤回（模拟或实际）
    dry_run = not confirm
    result = plugin.user_service.rollback_refund_taxes(
        start_date=start_date,
        end_date=end_date,
        dry_run=dry_run
    )
    
    if not result.get("success"):
        yield event.plain_result(f"❌ {result.get('message')}")
        return
    
    if dry_run:
        # 模拟运行结果
        message = f"【🔍 撤回退税模拟运行】\n"
        message += f"=" * 40 + "\n"
        message += f"📅 日期范围: {start_date} 至 {end_date}\n"
        message += f"👥 影响用户: {result['total_users']} 人\n"
        message += f"💰 总撤回额: {result['total_rollback_amount']:,} 金币\n\n"
        message += f"【前20位用户预览】\n"
        message += f"-" * 40 + "\n"
        
        for item in result['preview']:
            status = "✓" if item['current_coins'] >= item['rollback_amount'] else "✗金币不足"
            message += f"  {item['nickname'] or item['user_id']:12s} | "
            message += f"撤回{item['rollback_amount']:,}币 | "
            message += f"{status}\n"
        
        message += f"\n⚠️ 这只是模拟运行！\n"
        message += f"若确认无误，请执行：\n"
        message += f"/撤回退税 {start_date} {end_date} 确认"
        
        yield event.plain_result(message)
    else:
        # 实际执行结果
        message = f"【✅ 撤回退税执行完成】\n"
        message += f"=" * 40 + "\n"
        message += f"{result['message']}\n\n"
        message += f"📅 日期范围: {start_date} 至 {end_date}\n"
        message += f"✓ 成功: {result['total_users']} 人\n"
        if result['failed_users'] > 0:
            message += f"✗ 失败: {result['failed_users']} 人\n"
        if result['insufficient_coins_users'] > 0:
            message += f"⚠️ 金币不足: {result['insufficient_coins_users']} 人\n"
        message += f"💰 总撤回额: {result['total_rollback_amount']:,} 金币\n\n"
        
        if result.get('details'):
            message += f"【部分撤回详情（前10位）】\n"
            message += f"-" * 40 + "\n"
            for item in result['details'][:10]:
                if item['status'] == '成功':
                    message += f"  {item['nickname'] or item['user_id']:12s} | "
                    message += f"{item['old_coins']:,} → {item['new_coins']:,}\n"
                else:
                    message += f"  {item['nickname'] or item['user_id']:12s} | "
                    message += f"{item['status']} (需{item['rollback_amount']:,}, 仅{item['current_coins']:,})\n"
        
        yield event.plain_result(message)


async def deduct_coins(plugin: "FishingPlugin", event: AstrMessageEvent):
    """扣除用户金币"""
    args = event.message_str.split(" ")

    # 解析目标用户ID（支持@和用户ID两种方式）
    target_user_id, error_msg = parse_target_user_id(event, args, 1)
    if error_msg:
        yield event.plain_result(error_msg)
        return

    # 检查金币数量参数
    if len(args) < 3:
        yield event.plain_result(
            "❌ 请指定金币数量，例如：/扣除金币 @用户 1000 或 /扣除金币 123456789 1000"
        )
        return

    coins = args[2]
    if not coins.isdigit():
        yield event.plain_result("❌ 金币数量必须是数字，请检查后重试。")
        return

    if (current_coins := plugin.user_service.get_user_currency(target_user_id)) is None:
        yield event.plain_result("❌ 用户不存在或未注册，请检查后重试。")
        return
    if int(coins) > current_coins.get("coins"):
        yield event.plain_result("❌ 扣除的金币数量不能超过用户当前拥有的金币数量")
        return
    if result := plugin.user_service.modify_user_coins(
        target_user_id, int(current_coins.get("coins") - int(coins))
    ):
        yield event.plain_result(f"✅ 成功扣除用户 {target_user_id} 的 {coins} 金币")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")


async def start_admin(plugin: "FishingPlugin", event: AstrMessageEvent):
    if plugin.web_admin_task and not plugin.web_admin_task.done():
        yield event.plain_result("❌ 钓鱼后台管理已经在运行中")
        return
    yield event.plain_result("🔄 正在启动钓鱼插件Web管理后台...")

    if not await _is_port_available(plugin.port):
        yield event.plain_result(f"❌ 端口 {plugin.port} 已被占用，请更换端口后重试")
        return

    try:
        services_to_inject = {
            "item_template_service": plugin.item_template_service,
            "user_service": plugin.user_service,
            "market_service": plugin.market_service,
            "fishing_zone_service": plugin.fishing_zone_service,
            "shop_service": plugin.shop_service,
            "exchange_service": plugin.exchange_service,
        }
        app = create_app(secret_key=plugin.secret_key, services=services_to_inject)
        config = Config()
        config.bind = [f"0.0.0.0:{plugin.port}"]
        plugin.web_admin_task = asyncio.create_task(serve(app, config))

        # 等待服务启动
        for i in range(10):
            if await plugin._check_port_active():
                break
            await asyncio.sleep(1)
        else:
            raise TimeoutError("⌛ 启动超时，请检查防火墙设置")

        await asyncio.sleep(1)  # 等待服务启动

        yield event.plain_result(
            f"✅ 钓鱼后台已启动！\n🔗请访问 http://localhost:{plugin.port}/admin\n🔑 密钥请到配置文件中查看\n\n⚠️ 重要提示：\n• 如需公网访问，请自行配置端口转发和防火墙规则\n• 确保端口 {plugin.port} 已开放并映射到公网IP\n• 建议使用反向代理（如Nginx）增强安全性"
        )
    except Exception as e:
        logger.error(f"启动后台失败: {e}", exc_info=True)
        yield event.plain_result(f"❌ 启动后台失败: {e}")


async def stop_admin(plugin: "FishingPlugin", event: AstrMessageEvent):
    """关闭钓鱼后台管理"""
    if (
        not hasattr(plugin, "web_admin_task")
        or not plugin.web_admin_task
        or plugin.web_admin_task.done()
    ):
        yield event.plain_result("❌ 钓鱼后台管理没有在运行中")
        return

    try:
        # 1. 请求取消任务
        plugin.web_admin_task.cancel()
        # 2. 等待任务实际被取消
        await plugin.web_admin_task
    except asyncio.CancelledError:
        # 3. 捕获CancelledError，这是成功关闭的标志
        logger.info("钓鱼插件Web管理后台已成功关闭")
        yield event.plain_result("✅ 钓鱼后台已关闭")
    except Exception as e:
        # 4. 捕获其他可能的意外错误
        logger.error(f"关闭钓鱼后台管理时发生意外错误: {e}", exc_info=True)
        yield event.plain_result(f"❌ 关闭钓鱼后台管理失败: {e}")


async def sync_initial_data(plugin: "FishingPlugin", event: AstrMessageEvent):
    """从 initial_data.py 同步所有初始设定（道具、商店等）。"""
    try:
        plugin.data_setup_service.sync_all_initial_data()
        yield event.plain_result("✅ 所有初始设定数据同步成功！")
    except Exception as e:
        logger.error(f"同步初始设定数据时出错: {e}")
        yield event.plain_result(f"❌ 同步初始设定数据失败: {e}")


async def impersonate_start(plugin: "FishingPlugin", event: AstrMessageEvent):
    """管理员开始扮演一名用户。"""
    admin_id = event.get_sender_id()
    args = event.message_str.split(" ")

    # 如果已经在线，则显示当前状态
    if admin_id in plugin.impersonation_map:
        target_user_id = plugin.impersonation_map[admin_id]
        target_user = plugin.user_repo.get_by_id(target_user_id)
        nickname = target_user.nickname if target_user else "未知用户"
        yield event.plain_result(f"您当前正在代理用户: {nickname} ({target_user_id})")
        return

    # 解析目标用户ID（支持@和用户ID两种方式）
    target_user_id, error_msg = parse_target_user_id(event, args, 1)
    if error_msg:
        yield event.plain_result(
            f"用法: /代理上线 <目标用户ID> 或 /代理上线 @用户\n{error_msg}"
        )
        return

    target_user = plugin.user_repo.get_by_id(target_user_id)
    if not target_user:
        yield event.plain_result("❌ 目标用户不存在。")
        return

    plugin.impersonation_map[admin_id] = target_user_id
    nickname = target_user.nickname
    yield event.plain_result(
        f"✅ 您已成功代理用户: {nickname} ({target_user_id})。\n现在您发送的所有游戏指令都将以该用户的身份执行。\n使用 /代理下线 结束代理。"
    )


async def impersonate_stop(plugin: "FishingPlugin", event: AstrMessageEvent):
    """管理员结束扮演用户。"""
    admin_id = event.get_sender_id()
    if admin_id in plugin.impersonation_map:
        del plugin.impersonation_map[admin_id]
        yield event.plain_result("✅ 您已成功结束代理。")
    else:
        yield event.plain_result("❌ 您当前没有在代理任何用户。")


async def reward_all_items(plugin: "FishingPlugin", event: AstrMessageEvent):
    """给所有注册用户发放道具"""
    args = event.message_str.split(" ")
    if len(args) < 4:
        yield event.plain_result(
            "❌ 请指定道具类型、道具ID和数量，例如：/全体发放道具 item 1 5"
        )
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
        yield event.plain_result(
            f"❌ 不支持的道具类型。支持的类型：{', '.join(valid_types)}"
        )
        return

    # 验证道具是否存在
    item_template = None
    if item_type == "item":
        item_template = plugin.item_template_repo.get_item_by_id(item_id)
    elif item_type == "bait":
        item_template = plugin.item_template_repo.get_bait_by_id(item_id)
    elif item_type == "rod":
        item_template = plugin.item_template_repo.get_rod_by_id(item_id)
    elif item_type == "accessory":
        item_template = plugin.item_template_repo.get_accessory_by_id(item_id)

    if not item_template:
        yield event.plain_result(f"❌ 道具不存在，请检查道具ID和类型。")
        return

    # 获取所有用户ID
    user_ids = plugin.user_repo.get_all_user_ids()
    if not user_ids:
        yield event.plain_result("❌ 当前没有注册用户。")
        return

    # 给所有用户发放道具
    success_count = 0
    failed_count = 0

    for user_id in user_ids:
        try:
            result = plugin.user_service.add_item_to_user_inventory(
                user_id, item_type, item_id, quantity
            )
            if result.get("success", False):
                success_count += 1
            else:
                failed_count += 1
        except Exception as e:
            failed_count += 1
            logger.error(f"给用户 {user_id} 发放道具失败: {e}")

    item_name = getattr(item_template, "name", f"ID:{item_id}")
    yield event.plain_result(
        f"✅ 全体发放道具完成！\n📦 道具：{item_name} x{quantity}\n✅ 成功：{success_count} 位用户\n❌ 失败：{failed_count} 位用户"
    )