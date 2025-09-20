import requests
import random
import json
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor
from astrbot.api import logger

# 导入仓储接口和领域模型
from ..repositories.abstract_repository import (
    AbstractUserRepository,
    AbstractLogRepository,
    AbstractInventoryRepository,
    AbstractItemTemplateRepository,
    AbstractUserBuffRepository,
)
from ..domain.models import WipeBombLog
from ..utils import get_now, weighted_random_choice


class GameMechanicsService:
    """封装特殊或独立的游戏机制"""

    FORTUNE_TIERS = {
        "daikichi": {"min": 15.0, "max": 1000.0, "label": "大吉", "message": "🔮 占卜结果：【大吉】\n神启降临！鸿运当头，是收获泼天富贵的最佳时机！"},
        "chukichi": {"min": 5.0, "max": 15.0, "label": "中吉", "message": "🔮 占卜结果：【中吉】\n时运亨通！有不错的机会获得远超预期的回报。"},
        "kichi":    {"min": 2.0, "max": 5.0, "label": "吉", "message": "🔮 占卜结果：【吉】\n顺风顺水，稳中有进，可以期待一笔可观的盈利。"},
        "shokichi": {"min": 1.0, "max": 2.0, "label": "小吉", "message": "🔮 占卜结果：【小吉】\n平安是福。虽无大喜，但亦无大忧，至少能小有盈余。"},
        "kyo":      {"min": 0.1, "max": 1.0, "label": "凶", "message": "🔮 占卜结果：【凶】\n运势不佳... 行事务必谨慎，否则可能招致损失。"},
        "daikyo":   {"min": 0.0, "max": 0.1, "label": "大凶", "message": "🔮 占卜结果：【大凶】\n灾祸之兆！此刻出手极可能血本无归，请务必避让！"},
    }

    def __init__(
        self,
        user_repo: AbstractUserRepository,
        log_repo: AbstractLogRepository,
        inventory_repo: AbstractInventoryRepository,
        item_template_repo: AbstractItemTemplateRepository,
        buff_repo: AbstractUserBuffRepository,
        config: Dict[str, Any]
    ):
        self.user_repo = user_repo
        self.log_repo = log_repo
        self.inventory_repo = inventory_repo
        self.item_template_repo = item_template_repo
        self.buff_repo = buff_repo
        self.config = config
        self.thread_pool = ThreadPoolExecutor(max_workers=5)

    def _get_fortune_tier_for_multiplier(self, multiplier: float) -> str:
        if multiplier >= 15.0: return "daikichi"
        if multiplier >= 5.0: return "chukichi"
        if multiplier >= 2.0: return "kichi"
        if multiplier >= 1.0: return "shokichi"
        if multiplier >= 0.1: return "kyo"
        return "daikyo"

    def forecast_wipe_bomb(self, user_id: str) -> Dict[str, Any]:
        """
        预知下一次擦弹的结果是“吉”还是“凶”。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        # 检查是否已有预测结果
        if user.wipe_bomb_forecast:
            return {"success": False, "message": "你已经预知过一次了，请先去擦弹吧！"}

        # 模拟一次随机过程来决定结果
        wipe_bomb_config = self.config.get("wipe_bomb", {})
        # 使用 perform_wipe_bomb 的默认概率表以确保一致性
        ranges = wipe_bomb_config.get(
            "reward_ranges",
            [
                (0.0, 0.1, 5),      # 灾难性亏损
                (0.1, 1.0, 55),     # 普通亏损
                (1.0, 2.0, 23),
                (2.0, 3.0, 11),
                (3.0, 4.0, 4),
                (4.0, 5.0, 4),
                (5.0, 15.0, 5),     # 高倍率
                (15.0, 1000.0, 0.1),# 超级头奖
            ],
        )
        
        # 筛选出吉凶区间 (修正临界点判断)
        good_ranges = [r for r in ranges if r[0] >= 1 or (r[0] < 1 and r[1] > 1)]
        bad_ranges = [r for r in ranges if r[1] <= 1]

        # 计算吉凶总权重
        total_good_weight = sum(w for _, _, w in good_ranges)
        total_bad_weight = sum(w for _, _, w in bad_ranges)
        total_weight = total_good_weight + total_bad_weight

        rand_val = random.uniform(0, total_weight)

        if rand_val <= total_bad_weight:
            forecast = "bad"
            message = "🔮 沙漏中的流沙汇聚成一个骷髅的形状...看起来下次擦弹的运气不太好。（凶）"
        else:
            forecast = "good"
            message = "✨ 沙漏中闪耀着金色的光芒！预示着一次不错的收获。（吉）"
            
        # 存储预测结果
        user.wipe_bomb_forecast = forecast
        self.user_repo.update(user)

        return {"success": True, "message": message}

    def perform_wipe_bomb(self, user_id: str, contribution_amount: int) -> Dict[str, Any]:
        """
        处理“擦弹”的完整逻辑。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        # 1. 验证投入金额
        if contribution_amount <= 0:
            return {"success": False, "message": "投入金额必须大于0"}
        if not user.can_afford(contribution_amount):
            return {"success": False, "message": f"金币不足，当前拥有 {user.coins} 金币"}

        # 2. 检查每日次数限制
        wipe_bomb_config = self.config.get("wipe_bomb", {})
        base_max_attempts = wipe_bomb_config.get("max_attempts_per_day", 3)

        # 检查是否有增加次数的 buff
        extra_attempts = 0
        boost_buff = self.buff_repo.get_active_by_user_and_type(
            user_id, "WIPE_BOMB_ATTEMPTS_BOOST"
        )
        if boost_buff and boost_buff.payload:
            try:
                payload = json.loads(boost_buff.payload)
                extra_attempts = payload.get("amount", 0)
            except json.JSONDecodeError:
                logger.warning(f"解析擦弹buff载荷失败: user_id={user_id}")

        total_max_attempts = base_max_attempts + extra_attempts
        attempts_today = self.log_repo.get_wipe_bomb_log_count_today(user_id)
        if attempts_today >= total_max_attempts:
            return {"success": False, "message": f"你今天的擦弹次数已用完({attempts_today}/{total_max_attempts})，明天再来吧！"}

        # 3. 计算随机奖励倍数 (使用加权随机)
        # 默认奖励范围和权重: (min_multiplier, max_multiplier, weight)
        default_ranges = [
            (0.0, 0.1, 5),      # 灾难性亏损
            (0.1, 1.0, 55),     # 普通亏损
            (1.0, 2.0, 23),
            (2.0, 3.0, 11),
            (3.0, 4.0, 4),
            (4.0, 5.0, 4),
            (5.0, 15.0, 5),     # 高倍率
            (15.0, 1000.0, 0.1),# 超级头奖
        ]
        ranges = wipe_bomb_config.get("reward_ranges", default_ranges)

        # 如果有预测结果，则强制使用对应区间的随机
        if user.wipe_bomb_forecast:
            forecast_key = user.wipe_bomb_forecast
            if forecast_key in self.FORTUNE_TIERS:
                tier_info = self.FORTUNE_TIERS[forecast_key]
                min_val, max_val = tier_info["min"], tier_info["max"]
                
                # 筛选出所有与预测结果区间有重叠的原始概率区间
                # 例如，如果预测是吉(2-5)，则需要包括原始的(2-3), (3-4), (4-5)区间
                constrained_ranges = [
                    r for r in default_ranges if max(r[0], min_val) < min(r[1], max_val)
                ]
                if constrained_ranges:
                    ranges = constrained_ranges

            # 使用后清空预测
            user.wipe_bomb_forecast = None

        # 3. 计算随机奖励倍数 (使用加权随机)
        try:
            chosen_range = weighted_random_choice(ranges)
            reward_multiplier = random.uniform(chosen_range[0], chosen_range[1])
        except (ValueError, IndexError) as e:
            logger.error(f"擦弹预测时随机选择出错: {e}", exc_info=True)
            return {"success": False, "message": "占卜失败，似乎天机不可泄露..."}

        # 4. 计算最终金额并执行事务
        reward_amount = int(contribution_amount * reward_multiplier)
        profit = reward_amount - contribution_amount

        user.coins += profit
        self.user_repo.update(user)

        # 5. 记录日志
        log_entry = WipeBombLog(
            log_id=0, # DB自增
            user_id=user_id,
            contribution_amount=contribution_amount,
            reward_multiplier=reward_multiplier,
            reward_amount=reward_amount,
            timestamp=get_now()
        )
        self.log_repo.add_wipe_bomb_log(log_entry)

        # 上传非敏感数据到服务器
        # 在单独线程中异步上传数据
        def upload_data_async():
            upload_data = {
                "user_id": user_id,
                "contribution_amount": contribution_amount,
                "reward_multiplier": reward_multiplier,
                "reward_amount": reward_amount,
                "profit": profit,
                "timestamp": log_entry.timestamp.isoformat()
            }
            api_url = "http://veyu.me/api/record"
            try:
                response = requests.post(api_url, json=upload_data)
                if response.status_code != 200:
                    logger.info(f"上传数据失败: {response.text}")
            except Exception as e:
                logger.error(f"上传数据时发生错误: {e}")

        # 启动异步线程进行数据上传，不阻塞主流程
        self.thread_pool.submit(upload_data_async)


        return {
            "success": True,
            "contribution": contribution_amount,
            "multiplier": reward_multiplier,
            "reward": reward_amount,
            "profit": profit,
            "remaining_today": total_max_attempts - (attempts_today + 1)
        }

    def get_wipe_bomb_history(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """
        获取用户的擦弹历史记录。
        """
        logs = self.log_repo.get_wipe_bomb_logs(user_id, limit)
        return {
            "success": True,
            "logs": [
                {
                    "contribution": log.contribution_amount,
                    "multiplier": log.reward_multiplier,
                    "reward": log.reward_amount,
                    "timestamp": log.timestamp
                } for log in logs
            ]
        }

    def steal_fish(self, thief_id: str, victim_id: str) -> Dict[str, Any]:
        """
        处理“偷鱼”的逻辑。
        """
        if thief_id == victim_id:
            return {"success": False, "message": "不能偷自己的鱼！"}

        thief = self.user_repo.get_by_id(thief_id)
        if not thief:
            return {"success": False, "message": "偷窃者用户不存在"}

        victim = self.user_repo.get_by_id(victim_id)
        if not victim:
            return {"success": False, "message": "目标用户不存在"}

        # 0. 检查受害者是否受保护
        protection_buff = self.buff_repo.get_active_by_user_and_type(
            victim_id, "STEAL_PROTECTION_BUFF"
        )
        if protection_buff:
            return {"success": False, "message": f"❌ 无法偷窃，【{victim.nickname}】的鱼塘似乎被神秘力量守护着！"}

        # 1. 检查偷窃CD
        cooldown_seconds = self.config.get("steal", {}).get("cooldown_seconds", 14400) # 默认4小时
        now = get_now()

        # 修复时区问题
        last_steal_time = thief.last_steal_time
        if last_steal_time and last_steal_time.tzinfo is None and now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        elif last_steal_time and last_steal_time.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=last_steal_time.tzinfo)

        if last_steal_time and (now - last_steal_time).total_seconds() < cooldown_seconds:
            remaining = int(cooldown_seconds - (now - last_steal_time).total_seconds())
            return {"success": False, "message": f"偷鱼冷却中，请等待 {remaining // 60} 分钟后再试"}

        # 2. 检查受害者是否有鱼可偷
        victim_inventory = self.inventory_repo.get_fish_inventory(victim_id)
        if not victim_inventory:
            return {"success": False, "message": f"目标用户【{victim.nickname}】的鱼塘是空的！"}

        # 3. 随机选择一条鱼偷取
        stolen_fish_item = random.choice(victim_inventory)
        stolen_fish_template = self.item_template_repo.get_fish_by_id(stolen_fish_item.fish_id)

        if not stolen_fish_template:
            return {"success": False, "message": "发生内部错误，无法识别被偷的鱼"}

        # 4. 执行偷窃事务
        # 从受害者库存中移除一条鱼
        self.inventory_repo.update_fish_quantity(victim_id, stolen_fish_item.fish_id, delta=-1)
        # 向偷窃者库存中添加一条鱼
        self.inventory_repo.add_fish_to_inventory(thief_id, stolen_fish_item.fish_id, quantity=1)

        # 5. 更新偷窃者的CD时间
        thief.last_steal_time = now
        self.user_repo.update(thief)

        return {
            "success": True,
            "message": f"✅ 成功从【{victim.nickname}】的鱼塘里偷到了一条{stolen_fish_template.rarity}★【{stolen_fish_template.name}】！基础价值 {stolen_fish_template.base_value} 金币",
        }

    def calculate_sell_price(self, item_type: str, rarity: int, refine_level: int) -> int:
        """
        计算物品的系统售价。

        Args:
            item_type: 物品类型 ('rod', 'accessory')
            rarity: 物品稀有度
            refine_level: 物品精炼等级

        Returns:
            计算出的售价。
        """
        # 1. 从配置中获取售价信息
        sell_price_config = self.config.get("sell_prices", {})
        
        # 2. 获取该物品类型的基础售价
        base_prices = sell_price_config.get(item_type, {})
        base_price = base_prices.get(str(rarity), 0)

        # 3. 获取精炼等级的售价乘数
        refine_multipliers = sell_price_config.get("refine_multiplier", {})
        
        # 确保乘数存在，如果不存在则默认为1
        refine_multiplier = refine_multipliers.get(str(refine_level), 1.0)

        # 4. 计算最终价格
        # 最终价格 = 基础价格 * 精炼乘数
        final_price = int(base_price * refine_multiplier)

        # 5. 如果没有找到任何配置，则提供一个最低默认价
        if final_price <= 0:
            return 30  # 默认最低价格

        return final_price