import random
from typing import Dict, Any, Optional
from datetime import timedelta, datetime, timezone

# 导入仓储接口和领域模型
from ..repositories.abstract_repository import (
    AbstractUserRepository,
    AbstractLogRepository,
    AbstractInventoryRepository,
    AbstractItemTemplateRepository,
    AbstractAchievementRepository
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
        config: Dict[str, Any],
        achievement_repo: Optional[AbstractAchievementRepository] = None
    ):
        self.user_repo = user_repo
        self.log_repo = log_repo
        self.inventory_repo = inventory_repo
        self.item_template_repo = item_template_repo
        self.gacha_service = gacha_service
        self.config = config
        self.achievement_repo = achievement_repo

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
            sort_by: 排序标准 ('coins', 'max_coins', 'fish_count', 'total_weight_caught')
            limit: 返回的用户数量限制

        Returns:
            包含排行榜数据的字典。
        """
        top_users = []
        if sort_by == "fish_count":
            top_users = self.user_repo.get_top_users_by_fish_count(limit)
        elif sort_by == "total_weight_caught":
            top_users = self.user_repo.get_top_users_by_weight(limit)
        elif sort_by == "max_coins":
            top_users = self.user_repo.get_top_users_by_max_coins(limit)
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
                "max_coins": user.max_coins,  # 添加历史最高金币
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

    def grant_title_to_user_by_name(self, user_id: str, title_name: str) -> Dict[str, Any]:
        """
        通过称号名称授予用户称号。
        """
        if not self.achievement_repo:
            return {"success": False, "message": "成就仓储未初始化"}
        
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        
        title = self.item_template_repo.get_title_by_name(title_name)
        if not title:
            return {"success": False, "message": f"称号 '{title_name}' 不存在"}
        
        # 检查用户是否已拥有该称号
        owned_titles = self.inventory_repo.get_user_titles(user_id)
        if title.title_id in owned_titles:
            return {"success": False, "message": f"用户已拥有称号 '{title_name}'"}
        
        self.achievement_repo.grant_title_to_user(user_id, title.title_id)
        return {"success": True, "message": f"✅ 成功授予用户称号 '{title_name}'"}

    def revoke_title_from_user_by_name(self, user_id: str, title_name: str) -> Dict[str, Any]:
        """
        通过称号名称移除用户的称号。
        """
        if not self.achievement_repo:
            return {"success": False, "message": "成就仓储未初始化"}
        
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        
        title = self.item_template_repo.get_title_by_name(title_name)
        if not title:
            return {"success": False, "message": f"称号 '{title_name}' 不存在"}
        
        # 检查用户是否拥有该称号
        owned_titles = self.inventory_repo.get_user_titles(user_id)
        if title.title_id not in owned_titles:
            return {"success": False, "message": f"用户未拥有称号 '{title_name}'"}
        
        # 如果用户正在使用该称号，则清空当前称号
        if user.current_title_id == title.title_id:
            user.current_title_id = None
            self.user_repo.update(user)
        
        self.achievement_repo.revoke_title_from_user(user_id, title.title_id)
        return {"success": True, "message": f"✅ 成功移除用户称号 '{title_name}'"}

    def create_custom_title(self, name: str, description: str, display_format: str = "{name}") -> Dict[str, Any]:
        """
        创建自定义称号。
        """
        # 检查称号名称是否已存在
        existing_title = self.item_template_repo.get_title_by_name(name)
        if existing_title:
            return {"success": False, "message": f"称号名称 '{name}' 已存在"}
        
        # 获取下一个可用的称号ID
        all_titles = self.item_template_repo.get_all_titles()
        if all_titles:
            next_id = max(t.title_id for t in all_titles) + 1
        else:
            next_id = 1
        
        title_data = {
            "title_id": next_id,
            "name": name,
            "description": description,
            "display_format": display_format
        }
        
        self.item_template_repo.add_title_template(title_data)
        return {"success": True, "message": f"✅ 成功创建称号 '{name}' (ID: {next_id})", "title_id": next_id}

    def get_all_titles_for_admin(self) -> Dict[str, Any]:
        """
        获取所有称号供管理使用。
        """
        titles = self.item_template_repo.get_all_titles()
        titles_data = []
        for title in titles:
            titles_data.append({
                "title_id": title.title_id,
                "name": title.name,
                "description": title.description,
                "display_format": title.display_format
            })
        return {"success": True, "titles": titles_data}

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

    def transfer_coins(self, from_user_id: str, to_user_id: str, amount: int) -> Dict[str, Any]:
        """
        用户之间转账金币。
        Args:
            from_user_id: 转账方用户ID
            to_user_id: 接收方用户ID
            amount: 转账金额（接收方实际到账金额）
        Returns:
            包含成功状态和消息的字典。
        """
        # 检查转账金额
        if amount <= 0:
            return {"success": False, "message": "转账金额必须大于0"}
        
        # 检查是否转账给自己
        if from_user_id == to_user_id:
            return {"success": False, "message": "不能转账给自己"}
        
        # 获取转账方用户
        from_user = self.user_repo.get_by_id(from_user_id)
        if not from_user:
            return {"success": False, "message": "转账方用户不存在"}
        
        # 获取接收方用户
        to_user = self.user_repo.get_by_id(to_user_id)
        if not to_user:
            return {"success": False, "message": "接收方用户不存在"}
        
        # 计算转账手续费
        tax_config = self.config.get("tax", {})
        transfer_tax_rate = tax_config.get("transfer_tax_rate", 0.05)  # 默认5%
        tax_amount = int(amount * transfer_tax_rate)
        total_cost = amount + tax_amount  # 转账方需支付的总金额
        
        # 检查余额是否足够（包含手续费）
        if from_user.coins < total_cost:
            return {
                "success": False,
                "message": f"❌ 余额不足！\n"
                          f"💰 到账金额：{amount} 金币\n"
                          f"💸 转账手续费（{int(transfer_tax_rate*100)}%）：{tax_amount} 金币\n"
                          f"📊 需要总计：{total_cost} 金币\n"
                          f"💳 当前余额：{from_user.coins} 金币"
            }
        
        # 记录转账前的金额
        original_coins = from_user.coins
        
        # 执行转账
        from_user.coins -= total_cost  # 扣除转账金额 + 手续费
        to_user.coins += amount  # 接收方只收到实际转账金额
        
        # 更新数据库
        self.user_repo.update(from_user)
        self.user_repo.update(to_user)
        
        # 记录转账税收
        if tax_amount > 0:
            tax_log = TaxRecord(
                tax_id=0,  # DB会自增
                user_id=from_user_id,
                tax_amount=tax_amount,
                tax_rate=transfer_tax_rate,
                original_amount=original_coins,
                balance_after=from_user.coins,
                timestamp=get_now(),
                tax_type="转账手续费"
            )
            self.log_repo.add_tax_record(tax_log)
        
        # 构建返回消息
        message = f"✅ 转账成功！\n"
        message += f"👤 接收方：{to_user.nickname}\n"
        message += f"💰 到账金额：{amount} 金币\n"
        if tax_amount > 0:
            message += f"💸 转账手续费（{int(transfer_tax_rate*100)}%）：{tax_amount} 金币\n"
            message += f"📊 扣除总计：{total_cost} 金币\n"
        message += f"💳 您的余额：{from_user.coins} 金币"
        
        return {
            "success": True,
            "message": message
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
        
        # 获取用户拥有的所有称号
        owned_titles = self.inventory_repo.get_user_titles(user_id)
        titles_list = []
        for title_id in owned_titles:
            title_template = self.item_template_repo.get_title_by_id(title_id)
            if title_template:
                titles_list.append({
                    "title_id": title_id,
                    "name": title_template.name,
                    "description": title_template.description,
                    "is_current": (title_id == user.current_title_id)
                })
        
        return {
            "success": True,
            "user": user,
            "equipped_rod": equipped_rod,
            "equipped_accessory": equipped_accessory,
            "current_title": current_title,
            "titles": titles_list
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

    def update_nickname(self, user_id: str, new_nickname: str) -> Dict[str, Any]:
        """
        允许用户更新自己的昵称
        
        Args:
            user_id: 用户ID
            new_nickname: 新昵称
            
        Returns:
            包含操作结果的字典
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "❌ 用户不存在，请先注册"}
        
        # 验证新昵称
        if not isinstance(new_nickname, str) or len(new_nickname.strip()) == 0:
            return {"success": False, "message": "❌ 昵称不能为空"}
        
        new_nickname = new_nickname.strip()
        
        if len(new_nickname) > 32:
            return {"success": False, "message": "❌ 昵称长度不能超过32个字符"}
        
        # 检查是否与当前昵称相同
        if user.nickname == new_nickname:
            return {"success": False, "message": f"❌ 您的昵称已经是 {new_nickname}，无需更改"}
        
        old_nickname = user.nickname or user_id
        user.nickname = new_nickname
        
        try:
            self.user_repo.update(user)
            return {
                "success": True, 
                "message": f"✅ 昵称更新成功！\n📝 旧昵称：{old_nickname}\n🆕 新昵称：{new_nickname}"
            }
        except Exception as e:
            return {"success": False, "message": f"❌ 更新昵称时发生错误：{str(e)}"}

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
                    # 计算实际价值（高品质鱼双倍价值）
                    actual_value = fish_template.base_value * (1 + item.quality_level)
                    fish_data.append({
                        "fish_id": item.fish_id,
                        "name": fish_template.name,
                        "rarity": fish_template.rarity,
                        "base_value": fish_template.base_value,
                        "quantity": item.quantity,
                        "quality_level": item.quality_level,  # 添加品质等级
                        "actual_value": actual_value,  # 添加实际价值
                        "quality_label": "✨高品质" if item.quality_level == 1 else "普通",  # 添加品质标签
                        "total_value": actual_value * item.quantity  # 使用实际价值计算总价值
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

    def add_item_to_user_inventory(self, user_id: str, item_type: str, item_id: int, quantity: int = 1, quality_level: int = 0) -> Dict[str, Any]:
        """
        向用户库存添加物品（管理员操作）
        
        Args:
            user_id: 用户ID
            item_type: 物品类型 (fish, rod, accessory, bait, item)
            item_id: 物品ID
            quantity: 数量
            quality_level: 品质等级（仅对鱼类有效，0=普通，1=高品质）
            
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
                self.inventory_repo.add_fish_to_inventory(user_id, item_id, quantity, quality_level)
                quality_label = "✨高品质" if quality_level == 1 else "普通"
                return {"success": True, "message": f"成功添加 {quality_label}{fish_template.name} x{quantity}"}
                
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
                
                self.inventory_repo.update_fish_quantity(user_id, item_id, -quantity, 0)
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