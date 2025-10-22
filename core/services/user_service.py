import random
from typing import Dict, Any, Optional
from datetime import timedelta, datetime, timezone

# 导入仓储接口和领域模型
from ..repositories.abstract_repository import (
    AbstractUserRepository,
    AbstractLogRepository,
    AbstractInventoryRepository,
    AbstractItemTemplateRepository
)
from .gacha_service import GachaService
from ..domain.models import User, TaxRecord
from ..utils import get_now, get_today


class UserService:
    """封装与用户相关的业务逻辑"""

    @staticmethod
    def _to_base36(n: int) -> str:
        if n < 0:
            raise ValueError("n must be non-negative")
        if n == 0:
            return "0"
        digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        out = []
        while n:
            n, rem = divmod(n, 36)
            out.append(digits[rem])
        return "".join(reversed(out))

    def __init__(
        self,
        user_repo: AbstractUserRepository,
        log_repo: AbstractLogRepository,
        inventory_repo: AbstractInventoryRepository,
        item_template_repo: AbstractItemTemplateRepository,
        gacha_service: "GachaService",
        config: Dict[str, Any]
    ):
        self.user_repo = user_repo
        self.log_repo = log_repo
        self.inventory_repo = inventory_repo
        self.item_template_repo = item_template_repo
        self.gacha_service = gacha_service
        self.config = config

    def register(self, user_id: str, nickname: str) -> Dict[str, Any]:
        """
        注册新用户。
        Args:
            user_id: 用户ID
            nickname: 用户昵称
        Returns:
            一个包含成功状态和消息的字典。
        """
        if self.user_repo.check_exists(user_id):
            return {"success": False, "message": "用户已注册"}

        initial_coins = self.config.get("user", {}).get("initial_coins", 200)
        new_user = User(
            user_id=user_id,
            nickname=nickname,
            coins=initial_coins,
            created_at=get_now()
        )
        self.user_repo.add(new_user)
        return {
            "success": True,
            "message": f"注册成功！欢迎 {nickname} 🎉 你获得了 {initial_coins} 金币作为起始资金。"
        }

    def create_user_for_admin(self, data: Dict[str, Any]) -> Dict[str, Any]:
        user_id = data.get("user_id")
        if not user_id:
            return {"success": False, "message": "缺少 user_id"}

        if self.user_repo.check_exists(user_id):
            return {"success": False, "message": "用户已存在"}

        nickname = data.get("nickname")
        initial_coins = data.get("coins")
        if not isinstance(initial_coins, int):
            initial_coins = self.config.get("user", {}).get("initial_coins", 200)

        # 先最小化创建用户记录
        new_user = User(
            user_id=user_id,
            nickname=nickname,
            coins=initial_coins,
            created_at=get_now()
        )
        self.user_repo.add(new_user)

        allowed_fields = {
            'nickname', 'coins', 'premium_currency', 'total_fishing_count',
            'total_weight_caught', 'total_coins_earned', 'consecutive_login_days',
            'fish_pond_capacity', 'fishing_zone_id', 'auto_fishing_enabled'
        }
        updates = {k: v for k, v in data.items() if k in allowed_fields}
        if updates:
            return self.update_user_for_admin(user_id, updates)
        return {"success": True, "message": "用户创建成功"}

    def get_leaderboard_data(self, sort_by: str = "coins", limit: int = 10) -> Dict[str, Any]:
        """
        获取排行榜数据，支持按不同标准排序。

        Args:
            sort_by: 排序标准 ('coins', 'fish_count', 'total_weight_caught')
            limit: 返回的用户数量限制

        Returns:
            包含排行榜数据的字典。
        """
        top_users = []
        if sort_by == "fish_count":
            top_users = self.user_repo.get_top_users_by_fish_count(limit)
        elif sort_by == "total_weight_caught":
            top_users = self.user_repo.get_top_users_by_weight(limit)
        else: # 默认按金币排序
            top_users = self.user_repo.get_top_users_by_coins(limit)
        
        leaderboard = []
        for user in top_users:
            # --- [核心修复] ---
            # 在组装字典时，必须包含 user_id 和 current_title_id
            # 这样下游的 handler 才能根据这些ID去查询详细信息
            leaderboard.append({
                "user_id": user.user_id,  # <--- 添加 user_id
                "nickname": user.nickname,
                "coins": user.coins,
                "fish_count": user.total_fishing_count,
                "total_weight_caught": user.total_weight_caught,
                "current_title_id": user.current_title_id, # <--- 添加 current_title_id
            })
        # --- [修复结束] ---
        
        return {
            "success": True,
            "leaderboard": leaderboard
        }

    def daily_sign_in(self, user_id: str) -> Dict[str, Any]:
        """
        处理用户每日签到。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "请先注册才能签到"}

        today = get_today()
        if self.log_repo.has_checked_in(user_id, today):
            return {"success": False, "message": "你今天已经签到过了，明天再来吧！"}

        yesterday = today - timedelta(days=1)
        if not self.log_repo.has_checked_in(user_id, yesterday):
            user.consecutive_login_days = 0

        signin_config = self.config.get("signin", {})
        min_reward = signin_config.get("min_reward", 100)
        max_reward = signin_config.get("max_reward", 300)
        coins_reward = random.randint(min_reward, max_reward)

        # 1. 增加金币和高级货币
        premium_currency_reward = 1
        user.coins += coins_reward
        user.premium_currency += premium_currency_reward 

        # 2. 更新连续签到和最后登录时间
        user.consecutive_login_days += 1
        user.last_login_time = get_now()

        bonus_coins = 0
        consecutive_bonuses = signin_config.get("consecutive_bonuses", {})
        if str(user.consecutive_login_days) in consecutive_bonuses:
            bonus_coins = consecutive_bonuses[str(user.consecutive_login_days)]
            user.coins += bonus_coins

        self.user_repo.update(user)
        self.log_repo.add_check_in(user_id, today)

        # 3. 构建包含两种奖励的消息
        message = f"签到成功！获得 {coins_reward} 金币和 {premium_currency_reward} 高级货币。"
        if bonus_coins > 0:
            message += f" 连续签到 {user.consecutive_login_days} 天，额外奖励 {bonus_coins} 金币！"

        free_gacha_reward_msg = ""
        free_pool = self.gacha_service.get_daily_free_pool()
        if free_pool:
            gacha_result = self.gacha_service.perform_draw(user.user_id, free_pool.gacha_pool_id, 1)
            if gacha_result.get("success"):
                reward = gacha_result.get("results", [])[0]
                reward_name = reward.get("name", "神秘奖励")
                if reward.get("type") == "coins":
                    reward_name = f"{reward.get('quantity', 0)} 金币"
                free_gacha_reward_msg = f"\n🎁 每日补给: 你获得了 {reward_name}！"
            else:
                fail_reason = gacha_result.get("message", "未能领取每日补给")
                free_gacha_reward_msg = f"\nℹ️ {fail_reason}"

        return {
            "success": True,
            "message": message + free_gacha_reward_msg,
            "coins_reward": coins_reward,
            "bonus_coins": bonus_coins,
            "consecutive_days": user.consecutive_login_days
        }

    def get_user_current_accessory(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户当前装备的配件信息。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        current_accessory = self.inventory_repo.get_user_equipped_accessory(user_id)
        if not current_accessory:
            return {"success": True, "accessory": None}
        accessory_template = self.item_template_repo.get_accessory_by_id(current_accessory.accessory_id)
        if not accessory_template:
            return {"success": False, "message": "配件不存在"}
        return {
            "success": True,
            "accessory": {
                "id": current_accessory.accessory_id,
                "name": accessory_template.name,
                "description": accessory_template.description
            }
        }

    def get_user_titles(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户拥有的称号列表。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        owned_titles = self.inventory_repo.get_user_titles(user_id)
        if not owned_titles:
            return {"success": True, "titles": []}
        titles_data = []
        for title_id in owned_titles:
            title_template = self.item_template_repo.get_title_by_id(title_id)
            if title_template:
                titles_data.append({
                    "title_id": title_id,
                    "name": title_template.name,
                    "description": title_template.description,
                    "is_current": (title_id == user.current_title_id)
                })
        return {"success": True, "titles": titles_data}

    def use_title(self, user_id: str, title_id: int) -> Dict[str, Any]:
        """
        装备一个称号。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        owned_titles = self.inventory_repo.get_user_titles(user_id)
        if title_id not in owned_titles:
            return {"success": False, "message": "你没有这个称号，无法使用"}
        user.current_title_id = title_id
        self.user_repo.update(user)
        title_template = self.item_template_repo.get_title_by_id(title_id)
        return {"success": True, "message": f"✅ 成功装备 {title_template.name}！"}

    def get_user_currency(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户的货币信息。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在", "coins": 0, "premium_currency": 0}
        return {
            "success": True,
            "coins": user.coins,
            "premium_currency": user.premium_currency
        }

    def modify_user_coins(self, user_id: str, amount: int) -> Dict[str, Any]:
        """
        修改用户的金币数量。
        Args:
            user_id: 用户ID
            amount: 修改的金币数量
        Returns:
            包含成功状态和消息的字典。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        user.coins = amount
        self.user_repo.update(user)
        return {
            "success": True,
            "message": f"金币数量已更新，当前金币：{user.coins}"
        }

    def get_tax_record(self, user_id: str) -> Dict[str, Any]:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        tax_records = self.log_repo.get_tax_records(user_id)
        if not tax_records:
            return {"success": True, "records": []}
        records_data = [
            {
                "amount": record.tax_amount,
                "timestamp": record.timestamp,
                "tax_type": record.tax_type,
            }
            for record in tax_records
        ]
        return {"success": True, "records": records_data}

    def refund_taxes_by_date_range(self, start_date: str, end_date: str, tax_type: str = "每日资产税", dry_run: bool = False) -> Dict[str, Any]:
        """
        退还特定日期范围内的税收
        
        Args:
            start_date: 开始日期 (格式: YYYY-MM-DD)
            end_date: 结束日期 (格式: YYYY-MM-DD)
            tax_type: 税收类型 (默认: 每日资产税)
            dry_run: 是否为模拟运行（只查询不执行）
            
        Returns:
            包含操作结果的字典
        """
        from ..utils import get_now
        from datetime import datetime
        
        # 获取数据库连接并查询需要退税的记录
        with self.user_repo._get_connection() as conn:
            cursor = conn.cursor()
            
            # 查询符合条件的税收记录
            cursor.execute("""
                SELECT user_id, SUM(tax_amount) as total_refund, COUNT(*) as count
                FROM taxes
                WHERE tax_type = ? 
                  AND DATE(timestamp) >= ? 
                  AND DATE(timestamp) <= ?
                GROUP BY user_id
                ORDER BY total_refund DESC
            """, (tax_type, start_date, end_date))
            
            refund_records = cursor.fetchall()
            
            if not refund_records:
                return {
                    "success": False,
                    "message": f"没有找到{start_date}至{end_date}期间的{tax_type}记录"
                }
            
            # 统计信息
            total_users = len(refund_records)
            total_refund_amount = sum(r[1] for r in refund_records)
            
            if dry_run:
                # 模拟运行，只返回统计信息
                preview = []
                for user_id, refund_amount, count in refund_records[:20]:  # 只显示前20个
                    user = self.user_repo.get_by_id(user_id)
                    preview.append({
                        "user_id": user_id,
                        "nickname": user.nickname if user else "未知",
                        "tax_count": count,
                        "refund_amount": refund_amount,
                        "current_coins": user.coins if user else 0
                    })
                
                return {
                    "success": True,
                    "dry_run": True,
                    "message": f"模拟运行：将为{total_users}位用户退还总计{total_refund_amount:,}金币",
                    "total_users": total_users,
                    "total_refund_amount": total_refund_amount,
                    "preview": preview
                }
            
            # 执行退税
            successful = 0
            failed = 0
            refund_details = []
            
            for user_id, refund_amount, count in refund_records:
                user = self.user_repo.get_by_id(user_id)
                if not user:
                    failed += 1
                    continue
                
                # 增加用户金币
                old_coins = user.coins
                user.coins += refund_amount
                self.user_repo.update(user)
                
                # 记录退税日志（作为负税额）
                from ..domain.models import TaxRecord
                refund_log = TaxRecord(
                    tax_id=0,  # 数据库自增
                    user_id=user_id,
                    tax_amount=-refund_amount,  # 负数表示退税
                    tax_rate=0.0,
                    original_amount=refund_amount,
                    balance_after=user.coins,
                    timestamp=get_now(),
                    tax_type=f"退税:{tax_type}({start_date}至{end_date})"
                )
                self.log_repo.add_tax_record(refund_log)
                
                successful += 1
                refund_details.append({
                    "user_id": user_id,
                    "nickname": user.nickname,
                    "refund_amount": refund_amount,
                    "tax_count": count,
                    "old_coins": old_coins,
                    "new_coins": user.coins
                })
            
            from astrbot.api import logger as log
            log.info(f"[退税] 完成退税操作: {successful}人成功, {failed}人失败, 总退税额{total_refund_amount:,}")
            
            return {
                "success": True,
                "message": f"✅ 退税完成！为{successful}位用户退还了总计{total_refund_amount:,}金币",
                "total_users": successful,
                "failed_users": failed,
                "total_refund_amount": total_refund_amount,
                "details": refund_details[:50]  # 只返回前50条详细记录
            }

    def rollback_refund_taxes(self, start_date: str, end_date: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        撤回退税操作（查找并撤回指定日期范围内的退税记录）
        
        Args:
            start_date: 开始日期 (格式: YYYY-MM-DD)
            end_date: 结束日期 (格式: YYYY-MM-DD)
            dry_run: 是否为模拟运行（只查询不执行）
            
        Returns:
            包含操作结果的字典
        """
        from ..utils import get_now
        from datetime import datetime
        
        # 获取数据库连接并查询需要撤回的退税记录
        with self.user_repo._get_connection() as conn:
            cursor = conn.cursor()
            
            # 查询退税记录（tax_amount为负数且tax_type包含"退税"）
            cursor.execute("""
                SELECT user_id, SUM(tax_amount) as total_refunded, COUNT(*) as count
                FROM taxes
                WHERE tax_amount < 0 
                  AND tax_type LIKE '退税:%'
                  AND DATE(timestamp) >= ? 
                  AND DATE(timestamp) <= ?
                GROUP BY user_id
                ORDER BY total_refunded ASC
            """, (start_date, end_date))
            
            rollback_records = cursor.fetchall()
            
            if not rollback_records:
                return {
                    "success": False,
                    "message": f"没有找到{start_date}至{end_date}期间的退税记录"
                }
            
            # 统计信息
            total_users = len(rollback_records)
            total_rollback_amount = abs(sum(r[1] for r in rollback_records))  # 取绝对值
            
            if dry_run:
                # 模拟运行，只返回统计信息
                preview = []
                for user_id, refunded_amount, count in rollback_records[:20]:
                    user = self.user_repo.get_by_id(user_id)
                    preview.append({
                        "user_id": user_id,
                        "nickname": user.nickname if user else "未知",
                        "refund_count": count,
                        "rollback_amount": abs(refunded_amount),
                        "current_coins": user.coins if user else 0
                    })
                
                return {
                    "success": True,
                    "dry_run": True,
                    "message": f"模拟运行：将从{total_users}位用户撤回总计{total_rollback_amount:,}金币",
                    "total_users": total_users,
                    "total_rollback_amount": total_rollback_amount,
                    "preview": preview
                }
            
            # 执行撤回
            successful = 0
            failed = 0
            insufficient_coins = 0
            rollback_details = []
            
            for user_id, refunded_amount, count in rollback_records:
                user = self.user_repo.get_by_id(user_id)
                if not user:
                    failed += 1
                    continue
                
                rollback_amount = abs(refunded_amount)  # 要扣除的金额（正数）
                
                # 检查用户金币是否足够
                if user.coins < rollback_amount:
                    insufficient_coins += 1
                    rollback_details.append({
                        "user_id": user_id,
                        "nickname": user.nickname,
                        "status": "金币不足",
                        "rollback_amount": rollback_amount,
                        "current_coins": user.coins
                    })
                    continue
                
                # 扣除用户金币
                old_coins = user.coins
                user.coins -= rollback_amount
                self.user_repo.update(user)
                
                # 删除对应的退税记录
                cursor.execute("""
                    DELETE FROM taxes
                    WHERE user_id = ?
                      AND tax_amount < 0
                      AND tax_type LIKE '退税:%'
                      AND DATE(timestamp) >= ?
                      AND DATE(timestamp) <= ?
                """, (user_id, start_date, end_date))
                
                # 记录撤回操作日志
                from ..domain.models import TaxRecord
                rollback_log = TaxRecord(
                    tax_id=0,
                    user_id=user_id,
                    tax_amount=rollback_amount,  # 正数表示扣除
                    tax_rate=0.0,
                    original_amount=rollback_amount,
                    balance_after=user.coins,
                    timestamp=get_now(),
                    tax_type=f"撤回退税({start_date}至{end_date})"
                )
                self.log_repo.add_tax_record(rollback_log)
                
                successful += 1
                rollback_details.append({
                    "user_id": user_id,
                    "nickname": user.nickname,
                    "status": "成功",
                    "rollback_amount": rollback_amount,
                    "old_coins": old_coins,
                    "new_coins": user.coins
                })
            
            conn.commit()
            
            from astrbot.api import logger as log
            log.info(f"[撤回退税] 完成撤回操作: {successful}人成功, {failed}人失败, {insufficient_coins}人金币不足, 总撤回额{total_rollback_amount:,}")
            
            message = f"✅ 撤回完成！从{successful}位用户撤回了总计{total_rollback_amount:,}金币"
            if insufficient_coins > 0:
                message += f"\n⚠️ {insufficient_coins}位用户金币不足，无法完全撤回"
            
            return {
                "success": True,
                "message": message,
                "total_users": successful,
                "failed_users": failed,
                "insufficient_coins_users": insufficient_coins,
                "total_rollback_amount": total_rollback_amount,
                "details": rollback_details[:50]
            }

    def get_users_for_admin(self, page: int = 1, per_page: int = 20, search: str = None) -> Dict[str, Any]:
        """
        获取用户列表用于后台管理
        
        Args:
            page: 页码（从1开始）
            per_page: 每页数量
            search: 搜索关键词
            
        Returns:
            包含用户列表和分页信息的字典
        """
        offset = (page - 1) * per_page
        if search:
            users = self.user_repo.search_users(search, per_page, offset)
            total_count = self.user_repo.get_search_users_count(search)
        else:
            users = self.user_repo.get_all_users(per_page, offset)
            total_count = self.user_repo.get_users_count()
        
        total_pages = (total_count + per_page - 1) // per_page
        return {
            "success": True,
            "users": users,
            "pagination": {
                "current_page": page,
                "per_page": per_page,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_prev": page > 1,
                "has_next": page < total_pages
            }
        }

    def get_user_details_for_admin(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户详细信息用于后台管理
        
        Args:
            user_id: 用户ID
            
        Returns:
            包含用户详细信息的字典
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        
        equipped_rod = None
        if user.equipped_rod_instance_id:
            rod_instance = self.inventory_repo.get_user_rod_instance_by_id(user.user_id, user.equipped_rod_instance_id)
            if rod_instance:
                rod_template = self.item_template_repo.get_rod_by_id(rod_instance.rod_id)
                if rod_template:
                    equipped_rod = {
                        "name": rod_template.name, 
                        "refine_level": rod_instance.refine_level
                        }
        
        equipped_accessory = None
        if user.equipped_accessory_instance_id:
            accessory_instance = self.inventory_repo.get_user_accessory_instance_by_id(user.user_id, user.equipped_accessory_instance_id)
            if accessory_instance:
                accessory_template = self.item_template_repo.get_accessory_by_id(accessory_instance.accessory_id)
                if accessory_template:
                    equipped_accessory = {
                        "name": accessory_template.name, 
                        "refine_level": accessory_instance.refine_level
                        }
        
        current_title = None
        if user.current_title_id:
            title_template = self.item_template_repo.get_title_by_id(user.current_title_id)
            if title_template:
                current_title = title_template.name
        
        return {
            "success": True,
            "user": user,
            "equipped_rod": equipped_rod,
            "equipped_accessory": equipped_accessory,
            "current_title": current_title
        }

    def update_user_for_admin(self, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新用户信息（管理员操作）
        
        Args:
            user_id: 用户ID
            updates: 要更新的字段字典
            
        Returns:
            包含操作结果的字典
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        
        allowed_fields = [
            'nickname', 'coins', 'premium_currency', 'total_fishing_count',
            'total_weight_caught', 'total_coins_earned', 'consecutive_login_days',
            'fish_pond_capacity', 'fishing_zone_id', 'auto_fishing_enabled'
        ]
        
        # 定义关键字段的校验逻辑
        def is_valid(field: str, value: Any) -> bool:
            numeric_non_negative = {
                'coins', 'premium_currency', 'total_fishing_count', 'total_weight_caught',
                'total_coins_earned', 'consecutive_login_days', 'fish_pond_capacity'
            }
            if field in numeric_non_negative:
                return isinstance(value, int) and value >= 0
            if field == 'fishing_zone_id':
                return isinstance(value, int) and (self.inventory_repo.get_zone_by_id(value) is not None)
            if field == 'auto_fishing_enabled':
                return isinstance(value, bool)
            if field == 'nickname':
                return (isinstance(value, str) and 0 < len(value) <= 32)
            return True
        
        for field, value in updates.items():
            if field in allowed_fields and hasattr(user, field):
                if not is_valid(field, value):
                    return {"success": False, "message": f"字段 {field} 的值无效: {value}"}
                setattr(user, field, value)
        
        self.user_repo.update(user)
        return {"success": True, "message": "用户信息更新成功"}

    def delete_user_for_admin(self, user_id: str) -> Dict[str, Any]:
        """
        删除用户（管理员操作）
        
        Args:
            user_id: 用户ID
            
        Returns:
            包含操作结果的字典
        """
        if not self.user_repo.check_exists(user_id):
            return {"success": False, "message": "用户不存在"}
        success = self.user_repo.delete_user(user_id)
        if success:
            return {"success": True, "message": "用户删除成功"}
        else:
            return {"success": False, "message": "用户删除失败"}
    
    def get_user_inventory_for_admin(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户物品库存信息（管理员操作）
        
        Args:
            user_id: 用户ID
            
        Returns:
            包含用户物品库存信息的字典
        """
        try:
            user = self.user_repo.get_by_id(user_id)
            if not user:
                return {"success": False, "message": "用户不存在"}
            
            # 获取鱼类库存
            fish_inventory = self.inventory_repo.get_fish_inventory(user_id)
            fish_data = []
            for item in fish_inventory:
                fish_template = self.item_template_repo.get_fish_by_id(item.fish_id)
                if fish_template:
                    fish_data.append({
                        "fish_id": item.fish_id,
                        "name": fish_template.name,
                        "rarity": fish_template.rarity,
                        "base_value": fish_template.base_value,
                        "quantity": item.quantity,
                        "total_value": fish_template.base_value * item.quantity
                    })
            
            # 获取鱼竿库存
            rod_instances = self.inventory_repo.get_user_rod_instances(user_id)
            rod_data = []
            for instance in rod_instances:
                rod_template = self.item_template_repo.get_rod_by_id(instance.rod_id)
                if rod_template:
                    rod_data.append({
                        "instance_id": instance.rod_instance_id,
                        "display_code": getattr(instance, 'display_code', f"R{self._to_base36(instance.rod_instance_id)}"),
                        "rod_id": instance.rod_id,
                        "name": rod_template.name,
                        "rarity": rod_template.rarity,
                        "refine_level": instance.refine_level,
                        "durability": instance.current_durability,
                        "is_equipped": instance.rod_instance_id == user.equipped_rod_instance_id,
                        "is_locked": instance.is_locked
                    })
            
            # 获取饰品库存
            accessory_instances = self.inventory_repo.get_user_accessory_instances(user_id)
            accessory_data = []
            for instance in accessory_instances:
                accessory_template = self.item_template_repo.get_accessory_by_id(instance.accessory_id)
                if accessory_template:
                    accessory_data.append({
                        "instance_id": instance.accessory_instance_id,
                        "display_code": getattr(instance, 'display_code', f"A{self._to_base36(instance.accessory_instance_id)}"),
                        "accessory_id": instance.accessory_id,
                        "name": accessory_template.name,
                        "rarity": accessory_template.rarity,
                        "refine_level": instance.refine_level,
                        "is_equipped": instance.accessory_instance_id == user.equipped_accessory_instance_id,
                        "is_locked": instance.is_locked
                    })
            
            # 获取鱼饵库存
            bait_inventory = self.inventory_repo.get_user_bait_inventory(user_id)
            bait_data = []
            for bait_id, quantity in bait_inventory.items():
                bait_template = self.item_template_repo.get_bait_by_id(bait_id)
                if bait_template and quantity > 0:
                    bait_data.append({
                        "bait_id": bait_id,
                        "name": bait_template.name,
                        "rarity": bait_template.rarity,
                        "quantity": quantity,
                        "cost": bait_template.cost,
                        "total_value": bait_template.cost * quantity
                    })

            # 获取道具库存
            item_inventory = self.inventory_repo.get_user_item_inventory(user_id)
            items_data = []
            for item_id, quantity in item_inventory.items():
                item_template = self.item_template_repo.get_item_by_id(item_id)
                if item_template and quantity > 0:
                    items_data.append({
                        "item_id": item_id,
                        "name": item_template.name,
                        "rarity": item_template.rarity,
                        "is_consumable": getattr(item_template, "is_consumable", False),
                        "quantity": quantity,
                        "cost": item_template.cost,
                        "total_value": (item_template.cost or 0) * quantity
                    })
            
            # 计算总价值
            fish_total_value = sum(item["total_value"] for item in fish_data)
            bait_total_value = sum(item["total_value"] for item in bait_data)
            item_total_value = sum(item["total_value"] for item in items_data)
            
            return {
                "success": True,
                "user_id": user_id,
                "nickname": user.nickname,
                "fish_inventory": fish_data,
                "rod_inventory": rod_data,
                "accessory_inventory": accessory_data,
                "bait_inventory": bait_data,
                "item_inventory": items_data,
                "stats": {
                    "fish_count": len(fish_data),
                    "rod_count": len(rod_data),
                    "accessory_count": len(accessory_data),
                    "bait_count": len(bait_data),
                    "item_count": len(items_data),
                    "fish_total_value": fish_total_value,
                    "bait_total_value": bait_total_value,
                    "item_total_value": item_total_value,
                    "total_inventory_value": fish_total_value + bait_total_value + item_total_value
                }
            }
        except Exception as e:
            return {"success": False, "message": f"获取库存信息时发生错误: {str(e)}"}

    def add_item_to_user_inventory(self, user_id: str, item_type: str, item_id: int, quantity: int = 1) -> Dict[str, Any]:
        """
        向用户库存添加物品（管理员操作）
        
        Args:
            user_id: 用户ID
            item_type: 物品类型 (fish, rod, accessory, bait, item)
            item_id: 物品ID
            quantity: 数量
            
        Returns:
            包含操作结果的字典
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        
        try:
            if item_type == "fish":
                fish_template = self.item_template_repo.get_fish_by_id(item_id)
                if not fish_template:
                    return {"success": False, "message": "鱼类不存在"}
                self.inventory_repo.add_fish_to_inventory(user_id, item_id, quantity)
                return {"success": True, "message": f"成功添加 {fish_template.name} x{quantity}"}
                
            elif item_type == "rod":
                rod_template = self.item_template_repo.get_rod_by_id(item_id)
                if not rod_template:
                    return {"success": False, "message": "鱼竿不存在"}
                for _ in range(quantity):
                    self.inventory_repo.add_rod_instance(user_id, item_id, rod_template.durability)
                return {"success": True, "message": f"成功添加 {rod_template.name} x{quantity}"}
                
            elif item_type == "accessory":
                accessory_template = self.item_template_repo.get_accessory_by_id(item_id)
                if not accessory_template:
                    return {"success": False, "message": "饰品不存在"}
                for _ in range(quantity):
                    self.inventory_repo.add_accessory_instance(user_id, item_id)
                return {"success": True, "message": f"成功添加 {accessory_template.name} x{quantity}"}
                
            elif item_type == "bait":
                bait_template = self.item_template_repo.get_bait_by_id(item_id)
                if not bait_template:
                    return {"success": False, "message": "鱼饵不存在"}
                self.inventory_repo.update_bait_quantity(user_id, item_id, quantity)
                return {"success": True, "message": f"成功添加 {bait_template.name} x{quantity}"}
            
            elif item_type == "item":
                item_template = self.item_template_repo.get_item_by_id(item_id)
                if not item_template:
                    return {"success": False, "message": "道具不存在"}
                self.inventory_repo.update_item_quantity(user_id, item_id, quantity)
                return {"success": True, "message": f"成功添加 {item_template.name} x{quantity}"}
                
            else:
                return {"success": False, "message": "不支持的物品类型"}
                
        except Exception as e:
            return {"success": False, "message": f"添加物品失败: {str(e)}"}

    def remove_item_from_user_inventory(self, user_id: str, item_type: str, item_id: int, quantity: int = 1) -> Dict[str, Any]:
        """
        从用户库存移除物品（管理员操作）
        
        Args:
            user_id: 用户ID
            item_type: 物品类型 (fish, rod, accessory, bait, item)
            item_id: 物品ID
            quantity: 数量
            
        Returns:
            包含操作结果的字典
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        
        try:
            if item_type == "fish":
                fish_template = self.item_template_repo.get_fish_by_id(item_id)
                if not fish_template:
                    return {"success": False, "message": "鱼类不存在"}
                
                fish_inventory = self.inventory_repo.get_fish_inventory(user_id)
                current_quantity = 0
                for item in fish_inventory:
                    if item.fish_id == item_id:
                        current_quantity = item.quantity
                        break
                
                if current_quantity < quantity:
                    return {"success": False, "message": f"库存不足，当前只有 {current_quantity} 个"}
                
                self.inventory_repo.update_fish_quantity(user_id, item_id, -quantity)
                return {"success": True, "message": f"成功移除 {fish_template.name} x{quantity}"}
                
            elif item_type == "rod":
                rod_template = self.item_template_repo.get_rod_by_id(item_id)
                if not rod_template:
                    return {"success": False, "message": "鱼竿不存在"}
                
                rod_instances = self.inventory_repo.get_user_rod_instances(user_id)
                target_instances = [inst for inst in rod_instances if inst.rod_id == item_id]
                
                if len(target_instances) < quantity:
                    return {"success": False, "message": f"库存不足，当前只有 {len(target_instances)} 个"}
                
                removed_count = 0
                for instance in target_instances:
                    if removed_count >= quantity: break
                    if instance.rod_instance_id == user.equipped_rod_instance_id:
                        user.equipped_rod_instance_id = None
                        self.user_repo.update(user)
                    self.inventory_repo.delete_rod_instance(instance.rod_instance_id)
                    removed_count += 1
                
                return {"success": True, "message": f"成功移除 {rod_template.name} x{removed_count}"}
                
            elif item_type == "accessory":
                accessory_template = self.item_template_repo.get_accessory_by_id(item_id)
                if not accessory_template:
                    return {"success": False, "message": "饰品不存在"}
                
                accessory_instances = self.inventory_repo.get_user_accessory_instances(user_id)
                target_instances = [inst for inst in accessory_instances if inst.accessory_id == item_id]
                
                if len(target_instances) < quantity:
                    return {"success": False, "message": f"库存不足，当前只有 {len(target_instances)} 个"}
                
                removed_count = 0
                for instance in target_instances:
                    if removed_count >= quantity: break
                    if instance.accessory_instance_id == user.equipped_accessory_instance_id:
                        user.equipped_accessory_instance_id = None
                        self.user_repo.update(user)
                    self.inventory_repo.delete_accessory_instance(instance.accessory_instance_id)
                    removed_count += 1
                
                return {"success": True, "message": f"成功移除 {accessory_template.name} x{removed_count}"}
                
            elif item_type == "bait":
                bait_template = self.item_template_repo.get_bait_by_id(item_id)
                if not bait_template: return {"success": False, "message": "鱼饵不存在"}
                
                bait_inventory = self.inventory_repo.get_user_bait_inventory(user_id)
                current_quantity = bait_inventory.get(item_id, 0)
                
                if current_quantity < quantity:
                    return {"success": False, "message": f"库存不足，当前只有 {current_quantity} 个"}
                
                self.inventory_repo.update_bait_quantity(user_id, item_id, -quantity)
                return {"success": True, "message": f"成功移除 {bait_template.name} x{quantity}"}
            
            elif item_type == "item":
                item_template = self.item_template_repo.get_item_by_id(item_id)
                if not item_template: return {"success": False, "message": "道具不存在"}

                item_inventory = self.inventory_repo.get_user_item_inventory(user_id)
                current_quantity = item_inventory.get(item_id, 0)
                if current_quantity < quantity:
                    return {"success": False, "message": f"库存不足，当前只有 {current_quantity} 个"}
                
                self.inventory_repo.update_item_quantity(user_id, item_id, -quantity)
                return {"success": True, "message": f"成功移除 {item_template.name} x{quantity}"}
                
            else:
                return {"success": False, "message": "不支持的物品类型"}
                
        except Exception as e:
            return {"success": False, "message": f"移除物品失败: {str(e)}"}

    def update_user_rod_instance_for_admin(self, user_id: str, rod_instance_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        管理员更新用户的鱼竿实例属性（精炼等级、耐久度）。

        支持的字段：
        - refine_level: 1-10 的整数
        - durability 或 current_durability: 非负整数，或 null 表示无限耐久
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        instance = self.inventory_repo.get_user_rod_instance_by_id(user_id, rod_instance_id)
        if not instance:
            return {"success": False, "message": "鱼竿实例不存在或不属于该用户"}

        if "refine_level" in updates:
            rl = updates.get("refine_level")
            if not isinstance(rl, int) or rl < 1 or rl > 10:
                return {"success": False, "message": "精炼等级必须为 1-10 的整数"}
            instance.refine_level = rl

        if "durability" in updates or "current_durability" in updates:
            dur_val = updates.get("durability") if "durability" in updates else updates.get("current_durability")
            if dur_val is None:
                instance.current_durability = None
            else:
                if isinstance(dur_val, str):
                    dur_val = dur_val.strip()
                    if dur_val == "": instance.current_durability = None
                    else:
                        try: dur_val = int(dur_val)
                        except ValueError: return {"success": False, "message": "耐久度必须为非负整数或留空表示无限"}
                
                if isinstance(dur_val, int):
                    if dur_val < 0: return {"success": False, "message": "耐久度不能为负数"}
                    instance.current_durability = dur_val
                elif dur_val is not None:
                    return {"success": False, "message": "耐久度必须为非负整数或留空表示无限"}

        rod_template = self.item_template_repo.get_rod_by_id(instance.rod_id)
        if rod_template and rod_template.durability is None:
            instance.current_durability = None

        self.inventory_repo.update_rod_instance(instance)
        return {"success": True, "message": "鱼竿实例已更新"}

    def update_user_accessory_instance_for_admin(self, user_id: str, accessory_instance_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        管理员更新用户的饰品实例属性（精炼等级）。
        支持的字段：
        - refine_level: 1-10 的整数
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        instance = self.inventory_repo.get_user_accessory_instance_by_id(user_id, accessory_instance_id)
        if not instance:
            return {"success": False, "message": "饰品实例不存在或不属于该用户"}

        if "refine_level" in updates:
            rl = updates.get("refine_level")
            try:
                rl = int(rl)
                if not (1 <= rl <= 10): raise ValueError()
            except (ValueError, TypeError):
                return {"success": False, "message": "精炼等级必须为 1-10 的整数"}
            instance.refine_level = rl

        self.inventory_repo.update_accessory_instance(instance)
        return {"success": True, "message": "饰品实例已更新"}