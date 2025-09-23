import json
import random
import threading
import time
from typing import Dict, Any, Optional
from datetime import timedelta
from astrbot.api import logger

# 导入仓储接口和领域模型
from ..repositories.abstract_repository import (
    AbstractUserRepository,
    AbstractInventoryRepository,
    AbstractItemTemplateRepository,
    AbstractLogRepository,
    AbstractUserBuffRepository,
)
from ..domain.models import FishingRecord, TaxRecord, FishingZone
from ..services.fishing_zone_service import FishingZoneService
from ..utils import get_now, get_fish_template, get_today, calculate_after_refine


class FishingService:
    """封装核心的钓鱼动作及后台任务"""

    def __init__(
        self,
        user_repo: AbstractUserRepository,
        inventory_repo: AbstractInventoryRepository,
        item_template_repo: AbstractItemTemplateRepository,
        log_repo: AbstractLogRepository,
        buff_repo: AbstractUserBuffRepository,
        fishing_zone_service: FishingZoneService,
        config: Dict[str, Any],
    ):
        self.user_repo = user_repo
        self.inventory_repo = inventory_repo
        self.item_template_repo = item_template_repo
        self.log_repo = log_repo
        self.buff_repo = buff_repo
        self.fishing_zone_service = fishing_zone_service
        self.config = config

        self.today = get_today()
        # 自动钓鱼线程相关属性
        self.auto_fishing_thread: Optional[threading.Thread] = None
        self.auto_fishing_running = False
        # 可选的消息通知回调：签名 (target: str, message: str) -> None，用于消息通知
        self._notifier = None
        # 通知目标可配置，默认群聊。可由 config['notifications']['relocation_target'] 覆盖
        notifications_cfg = self.config.get("notifications", {}) if isinstance(self.config, dict) else {}
        self._notification_target = notifications_cfg.get("relocation_target", "group")
        

    def register_notifier(self, notifier, default_target: Optional[str] = None):
        """
        注册一个用于发送系统消息的回调（如群聊推送）。
        回调应为同步函数，签名为 (target: str, message: str) -> None。
        默认目标可通过参数或配置指定。
        """
        self._notifier = notifier
        if default_target:
            self._notification_target = default_target

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

        # 1. 检查成本（从区域配置中读取）
        zone = self.inventory_repo.get_zone_by_id(user.fishing_zone_id)
        if not zone:
            return {"success": False, "message": "钓鱼区域不存在"}
        
        fishing_cost = zone.fishing_cost
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

        # --- 新增：应用 Buff 效果 ---
        active_buffs = self.buff_repo.get_all_active_by_user(user_id)
        for buff in active_buffs:
            if buff.buff_type == "RARE_FISH_BOOST":
                try:
                    payload = json.loads(buff.payload) if buff.payload else {}
                    multiplier = payload.get("multiplier", 1.0)
                    # 这里的实现是直接增加到 rare_chance
                    # 注意：如果基础值是0，乘法无意义，所以用加法或更复杂的逻辑
                    # 假设 payload 的 multiplier 是一个额外的概率加成
                    rare_chance += multiplier
                    logger.info(
                        f"用户 {user_id} 的 RARE_FISH_BOOST 生效，稀有几率增加 {multiplier}"
                    )
                except (json.JSONDecodeError, TypeError):
                    logger.error(f"解析 buff payload 失败: {buff.payload}")
        # --- Buff 应用结束 ---

        logger.debug(
            f"当前钓鱼概率： base_success_rate={base_success_rate}, quality_modifier={quality_modifier}, quantity_modifier={quantity_modifier}, rare_chance={rare_chance}, coins_chance={coins_chance}"
        )
        # 获取装备鱼竿并应用加成
        equipped_rod_instance = self.inventory_repo.get_user_equipped_rod(user.user_id)
        if equipped_rod_instance:
            rod_template = self.item_template_repo.get_rod_by_id(equipped_rod_instance.rod_id)
            if rod_template:
                quality_modifier *= calculate_after_refine(rod_template.bonus_fish_quality_modifier, refine_level= equipped_rod_instance.refine_level, rarity=rod_template.rarity)
                quantity_modifier *= calculate_after_refine(rod_template.bonus_fish_quantity_modifier, refine_level= equipped_rod_instance.refine_level, rarity=rod_template.rarity)
                rare_chance += calculate_after_refine(rod_template.bonus_rare_fish_chance, refine_level= equipped_rod_instance.refine_level, rarity=rod_template.rarity)
        logger.debug(f"装备鱼竿加成后： quality_modifier={quality_modifier}, quantity_modifier={quantity_modifier}, rare_chance={rare_chance}")
        # 获取装备饰品并应用加成
        equipped_accessory_instance = self.inventory_repo.get_user_equipped_accessory(user.user_id)
        if equipped_accessory_instance:
            acc_template = self.item_template_repo.get_accessory_by_id(equipped_accessory_instance.accessory_id)
            if acc_template:
                quality_modifier *= calculate_after_refine(acc_template.bonus_fish_quality_modifier, refine_level= equipped_accessory_instance.refine_level, rarity=acc_template.rarity)
                quantity_modifier *= calculate_after_refine(acc_template.bonus_fish_quantity_modifier, refine_level= equipped_accessory_instance.refine_level, rarity=acc_template.rarity)
                rare_chance += calculate_after_refine(acc_template.bonus_rare_fish_chance, refine_level= equipped_accessory_instance.refine_level, rarity=acc_template.rarity)
                coins_chance += calculate_after_refine(acc_template.bonus_coin_modifier, refine_level= equipped_accessory_instance.refine_level, rarity=acc_template.rarity)
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
        # 使用区域策略获取基础稀有度分布
        strategy = self.fishing_zone_service.get_strategy(user.fishing_zone_id)
        rarity_distribution = strategy.get_fish_rarity_distribution(user)
        
        zone = self.inventory_repo.get_zone_by_id(user.fishing_zone_id)
        is_rare_fish_available = zone.rare_fish_caught_today < zone.daily_rare_fish_quota
        
        if not is_rare_fish_available:
            # 稀有鱼定义：4星及以上（包括5星和6+星组合）
            # 若达到配额，屏蔽4星、5星和6+星概率，其它星级不受影响
            if len(rarity_distribution) >= 4:
                rarity_distribution[3] = 0.0  # 4星
            if len(rarity_distribution) >= 5:
                rarity_distribution[4] = 0.0  # 5星
            if len(rarity_distribution) >= 6:
                rarity_distribution[5] = 0.0  # 6+星
            # 重新归一化概率分布
            total = sum(rarity_distribution)
            if total > 0:
                rarity_distribution = [x / total for x in rarity_distribution]
        
        # 根据分布抽取稀有度
        rarity_index = random.choices(range(len(rarity_distribution)), weights=rarity_distribution, k=1)[0]
        
        if rarity_index == 5:  # 抽中6+星组合
            # 从6星及以上的鱼中随机选择，兼容区域限定鱼
            rarity = self._get_random_high_rarity(zone)
        else:
            # 1-5星直接对应
            rarity = rarity_index + 1
            
        fish_template = self._get_fish_template(rarity, zone, coins_chance)

        if not fish_template:
             return {"success": False, "message": "错误：当前条件下没有可钓的鱼！"}

        # 如果有垃圾鱼减少修正，则应用，价值 < 5则被视为垃圾鱼
        if garbage_reduction_modifier is not None and fish_template.base_value < 5:
            # 根据垃圾鱼减少修正值决定是否重新选择一次
            if random.random() < garbage_reduction_modifier:
                # 重新选择一条鱼
                new_rarity = random.choices(range(1, len(rarity_distribution) + 1), weights=rarity_distribution, k=1)[0]
                new_fish_template = self._get_fish_template(new_rarity, zone, coins_chance)

                if new_fish_template:
                    fish_template = new_fish_template

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

        if fish_template.rarity >= 4:
            # 如果是4星及以上稀有鱼，增加用户的稀有鱼捕获计数
            zone = self.inventory_repo.get_zone_by_id(user.fishing_zone_id)
            if zone:
                zone.rare_fish_caught_today += 1
                self.inventory_repo.update_fishing_zone(zone)

        # 4.2 按品质加成给予额外质量（重量/价值）奖励
        quality_bonus = False
        if quality_modifier > 1.0:
            quality_bonus = random.random() <= (quality_modifier - 1.0)
        if quality_bonus:
            extra_weight = random.randint(fish_template.min_weight, fish_template.max_weight)
            extra_value = fish_template.base_value
            weight += extra_weight
            value += extra_value

        # 4.3 按数量加成决定额外渔获数量
        total_catches = 1
        if quantity_modifier > 1.0:
            # 整数部分-1 为保证的额外数量；小数部分为额外+1的概率
            guaranteed_extra = max(0, int(quantity_modifier) - 1)
            total_catches += guaranteed_extra
            fractional = quantity_modifier - int(quantity_modifier)
            if fractional > 0 and random.random() < fractional:
                total_catches += 1

        # 5. 更新数据库
        self.inventory_repo.add_fish_to_inventory(user.user_id, fish_template.fish_id, quantity= total_catches)

        # 更新用户统计数据
        user.total_fishing_count += total_catches
        user.total_weight_caught += weight
        user.total_coins_earned += value
        user.last_fishing_time = get_now()
        
        # 处理装备耐久度消耗
        equipment_broken_messages = []

        # 判断用户的鱼竿是否存在并处理耐久度
        if user.equipped_rod_instance_id:
            rod_instance = self.inventory_repo.get_user_rod_instance_by_id(user.user_id, user.equipped_rod_instance_id)
            if not rod_instance:
                user.equipped_rod_instance_id = None
            else:
                # 减少鱼竿耐久度（仅当为有限耐久时）
                if rod_instance.current_durability is not None and rod_instance.current_durability > 0:
                    rod_instance.current_durability -= 1
                    self.inventory_repo.update_rod_instance(rod_instance)

                # 无论是刚减为0，还是之前就是0，都进行一次破损检查与卸下，保证一致性
                if rod_instance.current_durability is not None and rod_instance.current_durability <= 0:
                    # 鱼竿损坏，自动卸下（同步 user 与实例 is_equipped 状态）
                    user.equipped_rod_instance_id = None
                    # 统一使用仓储方法重置装备状态，避免前端/状态页不一致
                    self.inventory_repo.set_equipment_status(
                        user.user_id,
                        rod_instance_id=None,
                        accessory_instance_id=user.equipped_accessory_instance_id
                    )
                    rod_template = self.item_template_repo.get_rod_by_id(rod_instance.rod_id)
                    rod_name = rod_template.name if rod_template else "鱼竿"
                    equipment_broken_messages.append(f"⚠️ 您的{rod_name}已损坏，自动卸下！")
        
        # 判断用户的饰品是否存在（饰品暂时不消耗耐久度）
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
        result = {
            "success": True,
            "fish": {
                "name": fish_template.name,
                "rarity": fish_template.rarity,
                "weight": weight,
                "value": value
            }
        }
        
        # 添加装备损坏消息
        if equipment_broken_messages:
            result["equipment_broken_messages"] = equipment_broken_messages
        
        return result

    def get_user_pokedex(self, user_id: str) -> Dict[str, Any]:
        """获取用户的图鉴信息。"""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        # 使用聚合统计作为图鉴数据来源
        stats = self.log_repo.get_user_fish_stats(user_id)
        if not stats:
            return {"success": True, "pokedex": []}
        all_fish_count = len(self.item_template_repo.get_all_fish())
        unlock_fish_count = len(stats)
        pokedex = []
        for stat in stats:
            fish_template = self.item_template_repo.get_fish_by_id(stat.fish_id)
            if fish_template:
                pokedex.append({
                    "fish_id": stat.fish_id,
                    "name": fish_template.name,
                    "rarity": fish_template.rarity,
                    "description": fish_template.description,
                    "value": fish_template.base_value,
                    "first_caught_time": stat.first_caught_at,
                    "last_caught_time": stat.last_caught_at,
                    "max_weight": stat.max_weight,
                    "min_weight": stat.min_weight,
                    "total_caught": stat.total_caught,
                    "total_weight": stat.total_weight,
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

        fishing_zones = self.inventory_repo.get_all_zones()
        zones_info = []
        
        for zone in fishing_zones:
            # 获取通行证道具名称
            required_item_name = None
            if zone.requires_pass and zone.required_item_id:
                item_template = self.item_template_repo.get_item_by_id(zone.required_item_id)
                required_item_name = item_template.name if item_template else f"道具ID{zone.required_item_id}"
            
            zones_info.append({
                "zone_id": zone.id,
                "name": zone.name,
                "description": zone.description,
                "daily_rare_fish_quota": zone.daily_rare_fish_quota,
                "rare_fish_caught_today": zone.rare_fish_caught_today,
                "whether_in_use": zone.id == user.fishing_zone_id,
                "is_active": zone.is_active,
                "requires_pass": zone.requires_pass,
                "required_item_id": zone.required_item_id,
                "required_item_name": required_item_name,
                "fishing_cost": zone.fishing_cost,
                "available_from": zone.available_from,
                "available_until": zone.available_until,
            })

        return {
            "success": True,
            "zones": zones_info
        }

    def _get_fish_template(self, rarity: int, zone: FishingZone, coins_chance: float):
        """根据稀有度和区域配置获取鱼类模板"""
        
        # 检查 FishingZone 对象是否有 'specific_fish_ids' 属性
        specific_fish_ids = getattr(zone, 'specific_fish_ids', [])

        if specific_fish_ids:
            # 如果是区域限定鱼，那么就在限定的鱼里面抽
            fish_list = [self.item_template_repo.get_fish_by_id(fish_id) for fish_id in specific_fish_ids]
            fish_list = [fish for fish in fish_list if fish and fish.rarity == rarity]
        else:
            # 否则就在全局鱼里面抽
            fish_list = self.item_template_repo.get_fishes_by_rarity(rarity)

        if not fish_list:
            # 如果限定鱼或全局鱼列表为空，则从所有鱼中随机抽取一条
            return self.item_template_repo.get_random_fish(rarity)

        return get_fish_template(fish_list, coins_chance)

    def _get_random_high_rarity(self, zone: FishingZone = None) -> int:
        """从6星及以上鱼类中随机选择一个稀有度，兼容区域限定鱼"""
        # 检查是否有区域限定鱼
        specific_fish_ids = getattr(zone, 'specific_fish_ids', []) if zone else []
        
        if specific_fish_ids:
            # 如果是区域限定鱼，只在限定鱼中查找高星级
            fish_list = [self.item_template_repo.get_fish_by_id(fish_id) for fish_id in specific_fish_ids]
            fish_list = [fish for fish in fish_list if fish]
        else:
            # 否则在全局鱼池中查找
            fish_list = self.item_template_repo.get_all_fish()
        
        # 找出所有6星及以上的稀有度
        high_rarities = set()
        for fish in fish_list:
            if fish.rarity >= 6:
                high_rarities.add(fish.rarity)
        
        if not high_rarities:
            # 如果没有6星及以上的鱼，返回5星
            return 5
            
        # 从高稀有度中随机选择一个
        return random.choice(list(high_rarities))

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

        # 检查区域是否激活
        if not zone.is_active:
            return {"success": False, "message": "该钓鱼区域暂未开放"}

        # 检查时间限制
        now = get_now()
        if zone.available_from and now < zone.available_from:
            return {"success": False, "message": f"该钓鱼区域将在 {zone.available_from.strftime('%Y-%m-%d %H:%M')} 开放"}
        
        if zone.available_until and now > zone.available_until:
            return {"success": False, "message": f"该钓鱼区域已于 {zone.available_until.strftime('%Y-%m-%d %H:%M')} 关闭"}

        # 检查通行证要求（从数据库读取）
        pass_consumed = False
        consumed_item_name = None
        if zone.requires_pass and zone.required_item_id:
            # 获取用户道具库存
            user_items = self.inventory_repo.get_user_item_inventory(user_id)
            current_quantity = user_items.get(zone.required_item_id, 0)
            
            if current_quantity < 1:
                # 获取道具名称用于显示
                item_template = self.item_template_repo.get_item_by_id(zone.required_item_id)
                item_name = item_template.name if item_template else f"道具ID{zone.required_item_id}"
                return {
                    "success": False, 
                    "message": f"❌ 进入该区域需要 {item_name}，您当前拥有 {current_quantity} 个"
                }
            
            # 消耗一个通行证道具
            self.inventory_repo.decrease_item_quantity(user_id, zone.required_item_id, 1)
            
            # 获取道具名称用于提示
            item_template = self.item_template_repo.get_item_by_id(zone.required_item_id)
            consumed_item_name = item_template.name if item_template else f"道具ID{zone.required_item_id}"
            pass_consumed = True
            
            # 记录日志
            self.log_repo.add_log(user_id, "zone_entry", f"使用通行证进入 {zone.name}")

        user.fishing_zone_id = zone.id
        self.user_repo.update(user)

        # 构建成功消息
        success_message = f"✅已将钓鱼区域设置为 {zone.name}"
        if pass_consumed and consumed_item_name:
            success_message += f"\n🔑 已消耗 1 个 {consumed_item_name}"

        return {"success": True, "message": success_message}

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

    def enforce_zone_pass_requirements_for_all_users(self) -> None:
        """
        每日检查：若用户当前所在钓鱼区域需要通行证，但其背包中已无对应道具，
        则将用户传送回 1 号钓鱼地，并通过群聊@通知相关玩家。
        """
        logger.info("开始执行每日区域通行证检查...")
        try:
            all_user_ids = self.user_repo.get_all_user_ids()
            logger.info(f"找到 {len(all_user_ids)} 个用户需要检查")
        except Exception as e:
            logger.error(f"获取用户列表失败: {e}")
            return

        relocated_users = []  # 存储被传送的用户信息
        consumed_users = []  # 存储消耗道具的用户信息

        for user_id in all_user_ids:
            try:
                user = self.user_repo.get_by_id(user_id)
                if not user:
                    continue

                zone = self.inventory_repo.get_zone_by_id(user.fishing_zone_id)
                if not zone or not getattr(zone, "requires_pass", False) or not getattr(zone, "required_item_id", None):
                    continue

                user_items = self.inventory_repo.get_user_item_inventory(user_id)
                current_quantity = user_items.get(zone.required_item_id, 0) if user_items else 0

                if current_quantity < 1:
                    # 移动到 1 号区域
                    user.fishing_zone_id = 1
                    self.user_repo.update(user)
                    
                    # 记录日志
                    try:
                        item_template = self.item_template_repo.get_item_by_id(zone.required_item_id)
                        item_name = item_template.name if item_template else f"道具ID{zone.required_item_id}"
                    except Exception:
                        item_name = f"道具ID{zone.required_item_id}"
                    self.log_repo.add_log(user_id, "zone_relocation", f"缺少 {item_name}，已被传送至 1 号钓鱼地")
                    
                    # 收集被传送用户信息
                    relocated_users.append({
                        "user_id": user_id,
                        "nickname": user.nickname,
                        "zone_name": zone.name,
                        "item_name": item_name
                    })
                else:
                    # 用户有道具，扣除一个通行证
                    self.inventory_repo.decrease_item_quantity(user_id, zone.required_item_id, 1)
                    
                    # 记录日志
                    try:
                        item_template = self.item_template_repo.get_item_by_id(zone.required_item_id)
                        item_name = item_template.name if item_template else f"道具ID{zone.required_item_id}"
                    except Exception:
                        item_name = f"道具ID{zone.required_item_id}"
                    self.log_repo.add_log(user_id, "daily_pass_consumption", f"每日消耗 {item_name} 继续留在 {zone.name}")
                    
                    # 收集消耗道具用户信息
                    consumed_users.append({
                        "user_id": user_id,
                        "nickname": user.nickname,
                        "zone_name": zone.name,
                        "item_name": item_name
                    })
                    logger.info(f"用户 {user.nickname} 消耗 {item_name} 继续留在 {zone.name}")
            except Exception:
                # 单个用户异常不影响其他用户
                continue

        # 记录检查结果
        logger.info(f"每日检查完成：{len(relocated_users)} 个用户被传送，{len(consumed_users)} 个用户消耗道具")
        
        # 如果有被传送的用户，发送群聊通知
        if relocated_users and self._notifier:
            try:
                self._send_relocation_notification(relocated_users)
            except Exception as e:
                logger.error(f"发送传送通知失败: {e}")

    def _send_relocation_notification(self, relocated_users: list) -> None:
        """
        发送传送通知到群聊，以符合世界观的方式@相关玩家。
        """
        if not relocated_users:
            return

        try:
            if self._notifier:
                group_message = self._build_relocation_notification_message(relocated_users)
                self._notifier(self._notification_target, group_message)
        except Exception as e:
            logger.error(f"发送传送通知失败: {e}")

    def _build_relocation_notification_message(self, relocated_users: list) -> str:
        """构建每日传送通知的消息文本。"""
        # 动态获取 1 号区域名称（读取失败时回退为“区域一”）
        try:
            home_zone = self.inventory_repo.get_zone_by_id(1)
            home_zone_name = home_zone.name if home_zone and getattr(home_zone, "name", None) else "区域一"
        except Exception:
            home_zone_name = "区域一"

        message_parts = [
            "🌅【每日区域检查】🌅\n",
            "黎明时分，钓鱼协会的巡查员开始检查各区域的准入资格...\n\n",
            f"以下玩家因缺少必要的通行证，已被安全传送回{home_zone_name}：\n",
        ]

        for user_info in relocated_users:
            message_parts.extend([
                f"• @{user_info['user_id']} ({user_info['nickname']})",
                f"  从 {user_info['zone_name']} 传送至 {home_zone_name}",
                f"  缺少：{user_info['item_name']}\n",
            ])
        return "".join(message_parts)

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
                    logger.info(f"检测到日期变更，从 {self.today} 到 {today}，开始执行每日任务...")
                    
                    # 重置所有受配额限制区域的稀有鱼计数（4星及以上）
                    all_zones = self.inventory_repo.get_all_zones()
                    for zone in all_zones:
                        if zone.daily_rare_fish_quota > 0:  # 只重置有配额的区域
                            zone.rare_fish_caught_today = 0
                            self.inventory_repo.update_fishing_zone(zone)
                    
                    # 每次循环开始时检查是否需要应用每日税收
                    self.apply_daily_taxes()
                    
                    # 每日检查：需要通行证的区域玩家是否仍持有通行证
                    self.enforce_zone_pass_requirements_for_all_users()
                
                # 获取所有开启自动钓鱼的用户
                auto_users_ids = self.user_repo.get_all_user_ids(auto_fishing_only=True)

                for user_id in auto_users_ids:
                    user = self.user_repo.get_by_id(user_id)
                    if not user:
                        continue

                    # 检查CD
                    now_ts = get_now().timestamp()
                    last_ts = 0
                    if user.last_fishing_time and user.last_fishing_time.year > 1:
                        last_ts = user.last_fishing_time.timestamp()
                    elif user.last_fishing_time and user.last_fishing_time.year <= 1:
                        # 若 last_fishing_time 被重置为极早时间，将时间设为当前时间减去冷却时间，
                        # 这样下一轮自动钓鱼就能正常工作了
                        cooldown = fishing_config.get("cooldown_seconds", 180)
                        user.last_fishing_time = get_now() - timedelta(seconds=cooldown)
                        self.user_repo.update(user)
                        last_ts = user.last_fishing_time.timestamp()
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

                    # 检查成本（从区域配置中读取）
                    zone = self.inventory_repo.get_zone_by_id(user.fishing_zone_id)
                    if not zone:
                        continue
                    fishing_cost = zone.fishing_cost
                    if not user.can_afford(fishing_cost):
                        # 金币不足，关闭其自动钓鱼
                        user.auto_fishing_enabled = False
                        self.user_repo.update(user)
                        logger.warning(f"用户 {user_id} 金币不足（需要 {fishing_cost} 金币），已关闭自动钓鱼")
                        continue

                    # 执行钓鱼
                    result = self.go_fish(user_id)
                    # 自动钓鱼时，如装备损坏，尝试进行消息推送
                    if result and result.get("equipment_broken_messages"):
                        for msg in result["equipment_broken_messages"]:
                            try:
                                if self._notifier:
                                    self._notifier(user_id, msg)
                            except Exception:
                                # 通知失败不影响主流程
                                pass
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
