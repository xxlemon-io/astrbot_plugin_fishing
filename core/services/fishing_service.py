import random
import threading
import time
from typing import Dict, Any, Optional
from datetime import  timedelta
from astrbot.api import logger

# 导入仓储接口和领域模型
from ..repositories.abstract_repository import (
    AbstractUserRepository,
    AbstractInventoryRepository,
    AbstractItemTemplateRepository,
    AbstractLogRepository
)
from ..domain.models import FishingRecord, TaxRecord
from ..utils import get_now, get_fish_template, get_today, calculate_after_refine


class FishingService:
    """封装核心的钓鱼动作及后台任务"""

    def __init__(
        self,
        user_repo: AbstractUserRepository,
        inventory_repo: AbstractInventoryRepository,
        item_template_repo: AbstractItemTemplateRepository,
        log_repo: AbstractLogRepository,
        config: Dict[str, Any]
    ):
        self.user_repo = user_repo
        self.inventory_repo = inventory_repo
        self.item_template_repo = item_template_repo
        self.log_repo = log_repo
        self.config = config

        self.today = get_today()
        # 自动钓鱼线程相关属性
        self.auto_fishing_thread: Optional[threading.Thread] = None
        self.auto_fishing_running = False

    def toggle_auto_fishing(self, user_id: str) -> Dict[str, Any]:
        """
        切换用户的自动钓鱼状态。

        Args:
            user_id: 用户ID。

        Returns:
            一个包含操作结果的字典。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "❌您还没有注册，请先使用 /注册 命令注册。"}

        user.auto_fishing_enabled = not user.auto_fishing_enabled
        self.user_repo.update(user)

        if user.auto_fishing_enabled:
            return {"success": True, "message": "🎣 自动钓鱼已开启！"}
        else:
            return {"success": True, "message": "🚫 自动钓鱼已关闭！"}

    def go_fish(self, user_id: str) -> Dict[str, Any]:
        """
        执行一次完整的钓鱼动作。

        Args:
            user_id: 尝试钓鱼的用户ID。

        Returns:
            一个包含结果的字典。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在，无法钓鱼。"}

        # 1. 检查成本
        fishing_cost = self.config.get("fishing", {}).get("cost", 10) + (user.fishing_zone_id - 1) * 50
        if not user.can_afford(fishing_cost):
            return {"success": False, "message": f"金币不足，需要 {fishing_cost} 金币。"}

        # 先扣除成本
        user.coins -= fishing_cost

        # 2. 计算各种加成和修正值
        base_success_rate = 0.7 # 基础成功率70%
        quality_modifier = 1.0 # 质量加成
        quantity_modifier = 1.0 # 数量加成
        rare_chance = 0.0 # 稀有鱼出现几率
        coins_chance = 0.0 # 增加同稀有度高金币出现几率
        logger.debug(f"当前钓鱼概率： base_success_rate={base_success_rate}, quality_modifier={quality_modifier}, quantity_modifier={quantity_modifier}, rare_chance={rare_chance}, coins_chance={coins_chance}")
        # 获取装备鱼竿并应用加成
        equipped_rod_instance = self.inventory_repo.get_user_equipped_rod(user.user_id)
        if equipped_rod_instance:
            rod_template = self.item_template_repo.get_rod_by_id(equipped_rod_instance.rod_id)
            if rod_template:
                quality_modifier *= calculate_after_refine(rod_template.bonus_fish_quality_modifier, refine_level= equipped_rod_instance.refine_level)
                quantity_modifier *= calculate_after_refine(rod_template.bonus_fish_quantity_modifier, refine_level= equipped_rod_instance.refine_level)
                rare_chance += calculate_after_refine(rod_template.bonus_rare_fish_chance, refine_level= equipped_rod_instance.refine_level)
        logger.debug(f"装备鱼竿加成后： quality_modifier={quality_modifier}, quantity_modifier={quantity_modifier}, rare_chance={rare_chance}")
        # 获取装备饰品并应用加成
        equipped_accessory_instance = self.inventory_repo.get_user_equipped_accessory(user.user_id)
        if equipped_accessory_instance:
            acc_template = self.item_template_repo.get_accessory_by_id(equipped_accessory_instance.accessory_id)
            if acc_template:
                quality_modifier *= calculate_after_refine(acc_template.bonus_fish_quality_modifier, refine_level= equipped_accessory_instance.refine_level)
                quantity_modifier *= calculate_after_refine(acc_template.bonus_fish_quantity_modifier, refine_level= equipped_accessory_instance.refine_level)
                rare_chance += calculate_after_refine(acc_template.bonus_rare_fish_chance, refine_level= equipped_accessory_instance.refine_level)
                coins_chance += calculate_after_refine(acc_template.bonus_coin_modifier, refine_level= equipped_accessory_instance.refine_level)
        logger.debug(f"装备饰品加成后： quality_modifier={quality_modifier}, quantity_modifier={quantity_modifier}, rare_chance={rare_chance}, coins_chance={coins_chance}")
        # 获取鱼饵并应用加成
        cur_bait_id = user.current_bait_id
        garbage_reduction_modifier = None

        # 判断鱼饵是否过期
        if user.current_bait_id is not None:
            bait_template = self.item_template_repo.get_bait_by_id(cur_bait_id)
            if bait_template and bait_template.duration_minutes > 0:
                # 检查鱼饵是否过期
                bait_expiry_time = user.bait_start_time
                if bait_expiry_time:
                    now = get_now()
                    expiry_time = bait_expiry_time + timedelta(minutes=bait_template.duration_minutes)
                    # 移除两个时间的时区信息
                    if now.tzinfo is not None:
                        now = now.replace(tzinfo=None)
                    if expiry_time.tzinfo is not None:
                        expiry_time = expiry_time.replace(tzinfo=None)
                    if now > expiry_time:
                        # 鱼饵已过期，清除当前鱼饵
                        user.current_bait_id = None
                        user.bait_start_time = None
                        self.inventory_repo.update_bait_quantity(user_id, cur_bait_id, -1)
                        self.user_repo.update(user)
                        logger.warning(f"用户 {user_id} 的当前鱼饵{bait_template}已过期，已被清除。")
            else:
                if bait_template:
                    # 如果鱼饵没有设置持续时间, 是一次性鱼饵，消耗一个鱼饵
                    user_bait_inventory = self.inventory_repo.get_user_bait_inventory(user_id)
                    if user_bait_inventory is not None and user_bait_inventory.get(user.current_bait_id, 0) > 0:
                        self.inventory_repo.update_bait_quantity(user_id, user.current_bait_id, -1)
                    else:
                        # 如果用户没有库存鱼饵，清除当前鱼饵
                        user.current_bait_id = None
                        user.bait_start_time = None
                        self.user_repo.update(user)
                        logger.warning(f"用户 {user_id} 的当前鱼饵{bait_template.bait_id}已被清除，因为库存不足。")
                else:
                    # 如果鱼饵模板不存在，清除当前鱼饵
                    user.current_bait_id = None
                    user.bait_start_time = None
                    self.user_repo.update(user)
                    logger.warning(f"用户 {user_id} 的当前鱼饵已被清除，因为鱼饵模板不存在。")

        if user.current_bait_id is None:
            # 随机获取一个库存鱼饵
            random_bait_id = self.inventory_repo.get_random_bait(user.user_id)
            if random_bait_id:
                user.current_bait_id = random_bait_id

        if user.current_bait_id is not None:
            bait_template = self.item_template_repo.get_bait_by_id(user.current_bait_id)
            # logger.info(f"鱼饵信息: {bait_template}")
            if bait_template:
                quantity_modifier *= bait_template.quantity_modifier
                rare_chance += bait_template.rare_chance_modifier
                base_success_rate += bait_template.success_rate_modifier
                garbage_reduction_modifier = bait_template.garbage_reduction_modifier
                coins_chance += bait_template.value_modifier
        logger.debug(f"使用鱼饵加成后： base_success_rate={base_success_rate}, quality_modifier={quality_modifier}, quantity_modifier={quantity_modifier}, rare_chance={rare_chance}, coins_chance={coins_chance}")
        # 3. 判断是否成功钓到
        if random.random() >= base_success_rate:
            # 失败逻辑
            user.last_fishing_time = get_now()
            self.user_repo.update(user)
            return {"success": False, "message": "💨 什么都没钓到..."}

        # 4. 成功，生成渔获
        # 设置稀有度分布
        rarity_weights = {
            1: [0.65, 0.25, 0.09, 0.01, 0],  # 区域一：4星概率极低，5星为0
            2: [0.5, 0.3, 0.16, 0.039, 0.001],  # 区域二：提升4星，引入极低概率5星
            3: [0.5, 0.3, 0.15, 0.045, 0.005]  # 区域三：大幅提升4星和5星
        }
        current_weights = rarity_weights.get(user.fishing_zone_id, rarity_weights[1])
        # 根据权重生成稀有度
        rarity_distribution = current_weights.copy()
        # 应用稀有度加成
        if rare_chance > 0.0:
            # 增加稀有鱼出现的几率
            rarity_distribution = [x + rare_chance for x in rarity_distribution]
            # 归一化概率分布
            total = sum(rarity_distribution)
            rarity_distribution = [x / total for x in rarity_distribution]
        zone = self.inventory_repo.get_zone_by_id(user.fishing_zone_id)
        is_rare_fish_available = zone.rare_fish_caught_today < zone.daily_rare_fish_quota
        if not is_rare_fish_available or user.fishing_zone_id == 1:
            # 如果稀有鱼已达上限或者是区域一，则将5星鱼的权重设为0
            rarity_distribution[4] = 0.0
            # 重新归一化概率分布
            total = sum(rarity_distribution)
            if total > 0:
                rarity_distribution = [x / total for x in rarity_distribution]
        rarity = random.choices(
            [1, 2, 3, 4, 5],
            weights=rarity_distribution,
            k=1
        )[0]
        fish_list = self.item_template_repo.get_fishes_by_rarity(rarity)
        # 从指定稀有度的鱼类中随机选择一条，并同时应用金币加成 -> 优先选取金币值高的
        fish_template = None
        if fish_list:
            fish_template = get_fish_template(fish_list, coins_chance)
        else:
            # 鱼列表为空的备选方案
            fish_template = self.item_template_repo.get_random_fish()

        if not fish_template:
             return {"success": False, "message": "错误：鱼类模板库为空！"}

        # 如果有垃圾鱼减少修正，则应用，价值 < 5则被视为垃圾鱼
        if garbage_reduction_modifier is not None and fish_template.base_value < 5:
            # 根据垃圾鱼减少修正值决定是否重新选择一次
            if random.random() < garbage_reduction_modifier:
                # 重新选择一条鱼
                new_rarity = random.choices(
                    [1, 2, 3, 4, 5],
                    weights=rarity_distribution,
                    k=1
                )[0]
                new_fish_list = self.item_template_repo.get_fishes_by_rarity(new_rarity)

                if new_fish_list:
                    fish_template = get_fish_template(new_fish_list, coins_chance)

        # 计算最终属性
        weight = random.randint(fish_template.min_weight, fish_template.max_weight)
        value = fish_template.base_value

        # 计算一下是否超过用户鱼塘容量
        user_fish_inventory = self.inventory_repo.get_fish_inventory(user.user_id)
        if user.fish_pond_capacity == sum(item.quantity for item in user_fish_inventory):
            # 随机删除用户的一条鱼
            random_fish = random.choice(user_fish_inventory)
            self.inventory_repo.update_fish_quantity(
                user.user_id,
                random_fish.fish_id,
                -1
            )

        if fish_template.rarity >= 5:
            # 如果是5星鱼，增加用户的稀有鱼捕获计数
            zone = self.inventory_repo.get_zone_by_id(user.fishing_zone_id)
            if zone:
                zone.rare_fish_caught_today += 1
                self.inventory_repo.update_fishing_zone(zone)

        # 4.2
        extra = random.random() <= (quality_modifier - 1)
        if extra:
            extra_weight = random.randint(fish_template.min_weight, fish_template.max_weight)
            extra_value = fish_template.base_value
            weight += extra_weight
            value += extra_value

        # 5. 更新数据库
        self.inventory_repo.add_fish_to_inventory(user.user_id, fish_template.fish_id, quantity= 1 + extra)

        # 更新用户统计数据
        user.total_fishing_count += 1 + extra
        user.total_weight_caught += weight
        user.total_coins_earned += value
        user.last_fishing_time = get_now()
        self.user_repo.update(user)

        # 判断用户的鱼竿和饰品是否真实存在
        if user.equipped_rod_instance_id:
            rod_instance = self.inventory_repo.get_user_rod_instance_by_id(user.user_id, user.equipped_rod_instance_id)
            if not rod_instance:
                user.equipped_rod_instance_id = None
        if user.equipped_accessory_instance_id:
            accessory_instance = self.inventory_repo.get_user_accessory_instance_by_id(user.user_id, user.equipped_accessory_instance_id)
            if not accessory_instance:
                user.equipped_accessory_instance_id = None

        # 更新用户信息
        self.user_repo.update(user)

        # 记录日志
        record = FishingRecord(
            record_id=0, # DB自增
            user_id=user.user_id,
            fish_id=fish_template.fish_id,
            weight=weight,
            value=value,
            timestamp=user.last_fishing_time,
            rod_instance_id=user.equipped_rod_instance_id,
            accessory_instance_id=user.equipped_accessory_instance_id,
            bait_id=user.current_bait_id
        )
        self.log_repo.add_fishing_record(record)

        # 6. 构建成功返回结果
        return {
            "success": True,
            "fish": {
                "name": fish_template.name,
                "rarity": fish_template.rarity,
                "weight": weight,
                "value": value
            }
        }

    def get_user_pokedex(self, user_id: str) -> Dict[str, Any]:
        """获取用户的图鉴信息。"""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        pokedex_ids = self.log_repo.get_unlocked_fish_ids(user_id)
        # Dict[int, datetime]: 键为鱼类ID，值为首次捕获时间
        if not pokedex_ids:
            return {"success": True, "pokedex": []}
        all_fish_count = len(self.item_template_repo.get_all_fish())
        unlock_fish_count = len(pokedex_ids)
        pokedex = []
        for fish_id, first_caught_time in pokedex_ids.items():
            fish_template = self.item_template_repo.get_fish_by_id(fish_id)
            if fish_template:
                pokedex.append({
                    "fish_id": fish_id,
                    "name": fish_template.name,
                    "rarity": fish_template.rarity,
                    "description": fish_template.description,
                    "value": fish_template.base_value,
                    "first_caught_time": first_caught_time
                })
        # 将图鉴按稀有度从大到小排序
        pokedex.sort(key=lambda x: x["rarity"], reverse=True)
        return {
            "success": True,
            "pokedex": pokedex,
            "total_fish_count": all_fish_count,
            "unlocked_fish_count": unlock_fish_count,
            "unlocked_percentage": (unlock_fish_count / all_fish_count) if all_fish_count > 0 else 0
    }

    def get_user_fish_log(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """
        获取用户的钓鱼记录。

        Args:
            user_id: 用户ID。
            limit: 返回记录的数量限制。

        Returns:
            包含钓鱼记录的字典。
        """
        records = self.log_repo.get_fishing_records(user_id, limit)
        # 根据records中的 fish_id 获取鱼类名称 rod_instance_id 和 accessory_instance_id 以及 bait_id 获取鱼竿、饰品、鱼饵信息
        fish_details = []
        for record in records:
            fish_template = self.item_template_repo.get_fish_by_id(record.fish_id)
            bait_template = self.item_template_repo.get_bait_by_id(record.bait_id) if record.bait_id else None

            user_rod = self.inventory_repo.get_user_rod_instance_by_id(user_id, record.rod_instance_id) if record.rod_instance_id else None
            rod_instance = self.item_template_repo.get_rod_by_id(user_rod.rod_id) if user_rod else None
            user_accessory = self.inventory_repo.get_user_accessory_instance_by_id(user_id, record.accessory_instance_id) if record.accessory_instance_id else None
            accessory_instance = self.item_template_repo.get_accessory_by_id(user_accessory.accessory_id) if user_accessory else None

            fish_details.append({
                "fish_name": fish_template.name if fish_template else "未知鱼类",
                "fish_rarity": fish_template.rarity if fish_template else "未知稀有度",
                "fish_weight": record.weight,
                "fish_value": record.value,
                "timestamp": record.timestamp,
                "rod": rod_instance.name if rod_instance else "未装备鱼竿",
                "accessory": accessory_instance.name if accessory_instance else "未装备饰品",
                "bait": bait_template.name if bait_template else "未使用鱼饵",
            })
        return {
            "success": True,
            "records": fish_details
        }

    def get_user_fishing_zones(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户的钓鱼区域信息。

        Args:
            user_id: 用户ID。

        Returns:
            包含钓鱼区域信息的字典。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        fishing_zones = self.inventory_repo.get_all_fishing_zones()
        zones_info = []
        for zone in fishing_zones:
            zones_info.append({
                "zone_id": zone.id,
                "name": zone.name,
                "description": zone.description,
                "daily_rare_fish_quota": zone.daily_rare_fish_quota,
                "rare_fish_caught_today": zone.rare_fish_caught_today,
                "whether_in_use": zone.id == user.fishing_zone_id,
            })

        return {
            "success": True,
            "zones": zones_info
        }

    def set_user_fishing_zone(self, user_id: str, zone_id: int) -> Dict[str, Any]:
        """
        设置用户的钓鱼区域。

        Args:
            user_id: 用户ID。
            zone_id: 要设置的钓鱼区域ID。

        Returns:
            包含操作结果的字典。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        zone = self.inventory_repo.get_zone_by_id(zone_id)
        if not zone:
            return {"success": False, "message": "钓鱼区域不存在"}

        user.fishing_zone_id = zone.id
        self.user_repo.update(user)

        return {"success": True, "message": f"✅已将钓鱼区域设置为 {zone.name}"}

    def on_load(self, area2num: int, area3num: int):
        zone2 = self.inventory_repo.get_zone_by_id(2)
        zone3 = self.inventory_repo.get_zone_by_id(3)
        zone2.daily_rare_fish_quota = area2num
        zone3.daily_rare_fish_quota = area3num
        self.inventory_repo.update_fishing_zone(zone2)
        self.inventory_repo.update_fishing_zone(zone3)
        logger.info(f"钓鱼区域2和3的今日稀有鱼捕获数量已加载: {area2num}, {area3num}")

    def apply_daily_taxes(self) -> None:
        """对所有高价值用户征收每日税收。"""
        tax_config = self.config.get("tax", {})
        if tax_config.get("is_tax", False) is False:
            return
        threshold = tax_config.get("threshold", 1000000)
        step_coins = tax_config.get("step_coins", 1000000)
        step_rate = tax_config.get("step_rate", 0.01)
        min_rate = tax_config.get("min_rate", 0.001)
        max_rate = tax_config.get("max_rate", 0.35)

        high_value_users = self.user_repo.get_high_value_users(threshold)

        for user in high_value_users:
            tax_rate = 0.0
            # 根据资产确定税率
            if user.coins >= threshold:
                steps = (user.coins - threshold) // step_coins
                tax_rate = min_rate + steps * step_rate
                if tax_rate > max_rate:
                    tax_rate = max_rate
            min_tax_amount = 1
            if tax_rate > 0:
                tax_amount = max(int(user.coins * tax_rate), min_tax_amount)
                original_coins = user.coins
                user.coins -= tax_amount

                self.user_repo.update(user)

                tax_log = TaxRecord(
                    tax_id=0, # DB会自增
                    user_id=user.user_id,
                    tax_amount=tax_amount,
                    tax_rate=tax_rate,
                    original_amount=original_coins,
                    balance_after=user.coins,
                    timestamp=get_now(),
                    tax_type="每日资产税"
                )
                self.log_repo.add_tax_record(tax_log)

    def start_auto_fishing_task(self):
        """启动自动钓鱼的后台线程。"""
        if self.auto_fishing_thread and self.auto_fishing_thread.is_alive():
            logger.info("自动钓鱼线程已在运行中")
            return

        self.auto_fishing_running = True
        self.auto_fishing_thread = threading.Thread(target=self._auto_fishing_loop, daemon=True)
        self.auto_fishing_thread.start()
        logger.info("自动钓鱼线程已启动")

    def stop_auto_fishing_task(self):
        """停止自动钓鱼的后台线程。"""
        self.auto_fishing_running = False
        if self.auto_fishing_thread:
            self.auto_fishing_thread.join(timeout=1.0)
            logger.info("自动钓鱼线程已停止")

    def _auto_fishing_loop(self):
        """自动钓鱼循环任务，由后台线程执行。"""
        fishing_config = self.config.get("fishing", {})
        cooldown = fishing_config.get("cooldown_seconds", 180)
        cost = fishing_config.get("cost", 10)

        while self.auto_fishing_running:
            try:
                today = get_today()
                if today != self.today:
                    # 如果今天日期变了，重置今日稀有鱼捕获数量
                    self.today = today
                    zone2 = self.inventory_repo.get_zone_by_id(2)
                    zone3 = self.inventory_repo.get_zone_by_id(3)
                    zone2.rare_fish_caught_today = 0
                    zone3.rare_fish_caught_today = 0
                    self.inventory_repo.update_fishing_zone(zone2)
                    self.inventory_repo.update_fishing_zone(zone3)
                    # 每次循环开始时检查是否需要应用每日税收
                    self.apply_daily_taxes()
                # 获取所有开启自动钓鱼的用户
                auto_users_ids = self.user_repo.get_all_user_ids(auto_fishing_only=True)

                for user_id in auto_users_ids:
                    user = self.user_repo.get_by_id(user_id)
                    if not user:
                        continue

                    # 检查CD
                    now_ts = get_now().timestamp()
                    last_ts = user.last_fishing_time.timestamp() if user.last_fishing_time else 0
                    # 检查用户是否装备了海洋之心
                    _cooldown = cooldown
                    equipped_accessory = self.inventory_repo.get_user_equipped_accessory(user_id)
                    if equipped_accessory:
                        accessory_template = self.item_template_repo.get_accessory_by_id(equipped_accessory.accessory_id)
                        if accessory_template and accessory_template.name == "海洋之心":
                            # 海洋之心装备时，CD时间减半
                            _cooldown /= 2
                    if now_ts - last_ts < _cooldown:
                        continue # CD中，跳过

                    # 检查成本
                    if not user.can_afford(cost):
                        # 金币不足，关闭其自动钓鱼
                        user.auto_fishing_enabled = False
                        self.user_repo.update(user)
                        logger.warning(f"用户 {user_id} 金币不足，已关闭自动钓鱼")
                        continue

                    # 执行钓鱼
                    self.go_fish(user_id)
                    # if result['success']:
                    #     fish = result["fish"]
                    #     logger.info(f"用户 {user_id} 自动钓鱼成功: {fish['name']}")
                    # else:
                    #      logger.info(f"用户 {user_id} 自动钓鱼失败: {result['message']}")

                # 每轮检查间隔
                time.sleep(40)

            except Exception as e:
                logger.error(f"自动钓鱼任务出错: {e}")
                # 打印堆栈信息
                import traceback
                logger.error(traceback.format_exc())
                time.sleep(60)
