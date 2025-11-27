import requests
import random
import json
from typing import Dict, Any, Optional, TYPE_CHECKING
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
from ..domain.models import WipeBombLog, User
from ...core.utils import get_now, get_today

if TYPE_CHECKING:
    from ..repositories.sqlite_user_repo import SqliteUserRepository

def weighted_random_choice(choices: list[tuple[any, any, float]]) -> tuple[any, any, float]:
    """
    带权重的随机选择。
    :param choices: 一个列表，每个元素是一个元组 (min_val, max_val, weight)。
    :return: 选中的元组。
    """
    total_weight = sum(w for _, _, w in choices)
    if total_weight == 0:
        raise ValueError("Total weight cannot be zero")
    rand_val = random.uniform(0, total_weight)
    
    current_weight = 0
    for choice in choices:
        current_weight += choice[2] # weight is the 3rd element
        if rand_val <= current_weight:
            return choice
    
    # Fallback in case of floating point inaccuracies
    return choices[-1]

class GameMechanicsService:
    """封装特殊或独立的游戏机制"""

    FORTUNE_TIERS = {
        "kyokudaikichi": {"min": 200.0, "max": 1500.0, "label": "極大吉", "message": "🔮 沙漏中爆发出天界般的神圣光辉，预示着天降横财，这是上天的恩赐！"},
        "chodaikichi": {"min": 50.0, "max": 200.0, "label": "超大吉", "message": "🔮 沙漏中爆发出神迹般的光芒，预示着传说中的财富即将降临！这是千载难逢的机会！"},
        "daikichi": {"min": 15.0, "max": 50.0, "label": "大吉", "message": "🔮 沙漏中爆发出神圣的光芒，预示着天降横财，这是神明赐予的奇迹！"},
        "chukichi": {"min": 6.0, "max": 15.0, "label": "中吉", "message": "🔮 沙漏中降下璀璨的星辉，预示着一笔泼天的横财即将到来。莫失良机！"},
        "kichi": {"min": 3.0, "max": 6.0, "label": "吉", "message": "🔮 金色的流沙汇成满月之形，预示着时运亨通，机遇就在眼前。"},
        "shokichi": {"min": 2.0, "max": 3.0, "label": "小吉", "message": "🔮 沙漏中的光芒温暖而和煦，预示着前路顺遂，稳中有进。"},
        "suekichi": {"min": 1.0, "max": 2.0, "label": "末吉", "message": "🔮 流沙平稳，波澜不惊。预示着平安喜乐，凡事皆顺。"},
        "kyo": {"min": 0.0, "max": 1.0, "label": "凶", "message": "🔮 沙漏中泛起一丝阴霾，预示着运势不佳，行事务必三思。"},
        "daikyo": {"min": 0.0, "max": 0.8, "label": "大凶", "message": "🔮 暗色的流沙汇成不祥之兆，警示着灾祸将至，请务必谨慎避让！"},
    }

    # --- 新增：命运之轮游戏内置配置 ---
    WHEEL_OF_FATE_CONFIG = {
        "min_entry_fee": 500,
        "max_entry_fee": 50000,
        "cooldown_seconds": 60,
        "timeout_seconds": 60,
        "levels": [
            { "level": 1, "success_rate": 0.65, "multiplier": 1.55 },  # 高风险起点，期望微盈利0.75%
            { "level": 2, "success_rate": 0.60, "multiplier": 1.45 },  # 开始亏损，防止稳赚
            { "level": 3, "success_rate": 0.55, "multiplier": 1.55 },  # 风险递增
            { "level": 4, "success_rate": 0.50, "multiplier": 1.70 },  # 中等风险
            { "level": 5, "success_rate": 0.45, "multiplier": 1.90 },  # 较高风险
            { "level": 6, "success_rate": 0.40, "multiplier": 2.15 },  # 高风险
            { "level": 7, "success_rate": 0.35, "multiplier": 2.50 },  # 极高风险
            { "level": 8, "success_rate": 0.30, "multiplier": 3.00 },  # 冒险者区域
            { "level": 9, "success_rate": 0.25, "multiplier": 3.70 },  # 追梦者区域
            { "level": 10, "success_rate": 0.20, "multiplier": 4.80 }  # 通关巨奖
        ]
    }
    # ------------------------------------

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
        # 服务器级别的抑制状态
        self._server_suppressed = False
        self._last_suppression_date = None
        self.thread_pool = ThreadPoolExecutor(max_workers=5)

    def _check_server_suppression(self) -> bool:
        """检查服务器级别的抑制状态，如果需要则重置"""
        today = get_today()
        
        # 如果是新的一天，重置抑制状态
        if self._last_suppression_date is None or self._last_suppression_date < today:
            self._server_suppressed = False
            self._last_suppression_date = today
        
        return self._server_suppressed
    
    def _trigger_server_suppression(self):
        """触发服务器级别的抑制状态"""
        self._server_suppressed = True
        self._last_suppression_date = get_today()

    def _get_fortune_tier_for_multiplier(self, multiplier: float) -> str:
        if multiplier >= 200.0: return "kyokudaikichi"    # 極大吉 (200-1500倍)
        if multiplier >= 50.0: return "chodaikichi"       # 超大吉 (50-200倍)
        if multiplier >= 15.0: return "daikichi"          # 大吉 (15-50倍)
        if multiplier >= 6.0: return "chukichi"           # 中吉 (6-15倍)
        if multiplier >= 3.0: return "kichi"              # 吉 (3-6倍)
        if multiplier >= 2.0: return "shokichi"           # 小吉 (2-3倍)
        if multiplier >= 1.0: return "suekichi"           # 末吉 (1.0-2倍)
        return "kyo"                                       # 凶 (0-1倍)
    
    def _parse_wipe_bomb_forecast(self, forecast_value: Optional[str]) -> Optional[Dict[str, Any]]:
        """解析存储在用户上的擦弹预测信息，兼容旧格式。"""
        if not forecast_value:
            return None

        if isinstance(forecast_value, dict):
            return forecast_value

        try:
            data = json.loads(forecast_value)
            if isinstance(data, dict) and data.get("mode"):
                return data
        except (TypeError, json.JSONDecodeError):
            pass

        # 兼容旧版本仅存储等级字符串的情况
        return {"mode": "legacy", "tier": forecast_value}


    def forecast_wipe_bomb(self, user_id: str) -> Dict[str, Any]:
        """
        预知下一次擦弹的结果是"吉"还是"凶"。
        削弱版本：33.3%准确率 + 33.3%占卜失败 + 33.4%错误预测，保持详细等级
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        # 检查是否已有预测结果
        if user.wipe_bomb_forecast:
            return {"success": False, "message": "你已经预知过一次了，请先去擦弹吧！"}

        # 模拟一次随机过程来决定结果
        wipe_bomb_config = self.config.get("wipe_bomb", {})
        # 使用与 perform_wipe_bomb 相同的新配置以确保一致性
        # 使用与perform_wipe_bomb相同的权重系统
        normal_ranges = [
            (0.0, 0.2, 10000),     # 严重亏损
            (0.2, 0.5, 18000),     # 普通亏损
            (0.5, 0.8, 15000),     # 小亏损
            (0.8, 1.2, 25000),     # 小赚
            (1.2, 2.0, 14100),     # 中赚（修正）
            (2.0, 3.0, 4230),      # 大赚（修正）
            (3.0, 6.0, 705),       # 超大赚（修正）
            (6.0, 15.0, 106),      # 高倍率（修正）
            (15.0, 50.0, 21),      # 超级头奖（修正）
            (50.0, 200.0, 7),      # 传说级奖励（修正）
            (200.0, 1500.0, 1),    # 神话级奖励（修正）
        ]
        
        suppressed_ranges = [
            (0.0, 0.2, 10000),     # 严重亏损
            (0.2, 0.5, 18000),     # 普通亏损
            (0.5, 0.8, 15000),     # 小亏损
            (0.8, 1.2, 25000),     # 小赚
            (1.2, 2.0, 20000),     # 中赚
            (2.0, 3.0, 6000),      # 大赚
            (3.0, 6.0, 1000),      # 超大赚
            (6.0, 15.0, 150),      # 高倍率
            (15.0, 50.0, 0),       # 超级头奖（禁用）
            (50.0, 200.0, 0),      # 传说级奖励（禁用）
            (200.0, 1500.0, 0),    # 神话级奖励（禁用）
        ]
        
        # 检查服务器级别的抑制状态
        suppressed = self._check_server_suppression()
        ranges = wipe_bomb_config.get(
            "suppressed_ranges" if suppressed else "normal_ranges",
            suppressed_ranges if suppressed else normal_ranges
        )
        
        # 模拟一次抽奖来决定运势
        try:
            chosen_range = weighted_random_choice(ranges)
            simulated_multiplier = random.uniform(chosen_range[0], chosen_range[1])
        except (ValueError, IndexError) as e:
            logger.error(f"擦弹预测时随机选择出错: {e}", exc_info=True)
            return {"success": False, "message": "占卜失败，似乎天机不可泄露..."}

        # 获取真实的运势等级
        real_tier_key = self._get_fortune_tier_for_multiplier(simulated_multiplier)
        
        # 削弱机制：33.3%准确率 + 33.3%占卜失败
        prediction_accuracy = 0.333  # 33.3%准确率
        divination_failure_rate = 0.333  # 33.3%占卜失败率
        random_value = random.random()
        
        if random_value < divination_failure_rate:
            # 占卜失败：无法获得预测结果
            user.wipe_bomb_forecast = None
            message = "❌ 占卜失败,"
            failure_messages = [
                "🔮 沙漏中的流沙突然变得混乱不堪，天机被遮蔽，无法窥探未来...",
                "🔮 沙漏中泛起诡异的迷雾，占卜之力被干扰，预测失败...",
                "🔮 沙漏中的光芒瞬间熄灭，似乎有什么力量阻止了预知...",
                "🔮 沙漏中的流沙停滞不前，占卜仪式未能完成...",
                "🔮 沙漏中传来低沉的嗡鸣声，预知之力被封印，占卜失败..."
            ]
            message += random.choice(failure_messages)
        elif random_value < divination_failure_rate + prediction_accuracy:
            # 准确预测：使用真实的详细运势等级
            user.wipe_bomb_forecast = json.dumps({
                "mode": "accurate",
                "tier": real_tier_key,
                "multiplier": simulated_multiplier
            })
            message = self.FORTUNE_TIERS[real_tier_key]["message"]
        else:
            # 错误预测：随机选择一个详细运势等级
            all_tiers = [t for t in self.FORTUNE_TIERS.keys() if t != real_tier_key]
            # 在消息中添加不确定性提示
            message = "⚠️ 注意：沙漏的样子有些奇怪..."
            wrong_tier_key = random.choice(all_tiers) if all_tiers else real_tier_key
            user.wipe_bomb_forecast = json.dumps({
                "mode": "inaccurate",
                "tier": wrong_tier_key
            })
            message += self.FORTUNE_TIERS[wrong_tier_key]["message"]
        
        # 保存预测结果
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

        # 2. 检查每日次数限制 (性能优化)
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
        
        # 获取今天的日期字符串
        today_str = get_today().strftime('%Y-%m-%d')
        
        # 检查是否是新的一天，如果是，则重置用户的每日擦弹计数
        if user.last_wipe_bomb_date != today_str:
            user.wipe_bomb_attempts_today = 0
            user.last_wipe_bomb_date = today_str

        # 使用用户对象中的计数值进行判断，不再查询日志
        if user.wipe_bomb_attempts_today >= total_max_attempts:
            return {
                "success": False, 
                "message": f"你今天的擦弹次数已用完({user.wipe_bomb_attempts_today}/{total_max_attempts})，明天再来吧！"
            }
        
        # 3. 计算随机奖励倍数 (使用加权随机)
        # 默认奖励范围和权重: (min_multiplier, max_multiplier, weight)
        # 专家建议配置：根据计算结果重新调整的权重分布
        # 使用整数权重（放大1000倍）避免小数计算
        normal_ranges = [
            (0.0, 0.2, 10000),     # 严重亏损
            (0.2, 0.5, 18000),     # 普通亏损
            (0.5, 0.8, 15000),     # 小亏损
            (0.8, 1.2, 25000),     # 小赚
            (1.2, 2.0, 14100),     # 中赚（增加）
            (2.0, 3.0, 4230),      # 大赚（增加）
            (3.0, 6.0, 705),       # 超大赚（增加）
            (6.0, 15.0, 106),      # 高倍率（增加）
            (15.0, 50.0, 21),      # 超级头奖（维持）
            (50.0, 200.0, 7),      # 传说级奖励（维持）
            (200.0, 1500.0, 1),    # 神话级奖励（维持）
        ]

        # 抑制模式：当一天内已开出≥15x高倍率后，禁用高倍率区间
        suppressed_ranges = [
            (0.0, 0.2, 10000),     # 严重亏损
            (0.2, 0.5, 18000),     # 普通亏损
            (0.5, 0.8, 15000),     # 小亏损
            (0.8, 1.2, 25000),     # 小赚
            (1.2, 2.0, 20000),     # 中赚
            (2.0, 3.0, 6000),      # 大赚
            (3.0, 6.0, 1000),      # 超大赚
            (6.0, 15.0, 150),      # 高倍率
            (15.0, 50.0, 0),       # 超级头奖（禁用）
            (50.0, 200.0, 0),      # 传说级奖励（禁用）
            (200.0, 1500.0, 0),    # 神话级奖励（禁用）
        ]

        # 检查服务器级别的抑制状态
        suppressed = self._check_server_suppression()

        # 根据抑制状态选择权重表
        if suppressed:
            ranges = wipe_bomb_config.get("suppressed_ranges", suppressed_ranges)
        else:
            ranges = wipe_bomb_config.get("normal_ranges", normal_ranges)

        # 4. 处理预知结果 (使用详细逻辑)
        forecast_info = self._parse_wipe_bomb_forecast(user.wipe_bomb_forecast)
        predetermined_multiplier: Optional[float] = None

        if forecast_info:
            mode = forecast_info.get("mode")
            if mode == "accurate":
                predetermined_multiplier = forecast_info.get("multiplier")
                if predetermined_multiplier is None:
                    # 兼容没有存储 multiplier 的情况，基于等级随机一个值
                    tier_key = forecast_info.get("tier")
                    tier_info = self.FORTUNE_TIERS.get(tier_key) if tier_key else None
                    if tier_info:
                        predetermined_multiplier = random.uniform(
                            tier_info.get("min", 0.0), tier_info.get("max", 1.0)
                        )
            # 使用后清空预测
            user.wipe_bomb_forecast = None

        # 5. 计算随机奖励倍数 (使用加权随机)
        try:
            if predetermined_multiplier is not None:
                reward_multiplier = predetermined_multiplier
            else:
                chosen_range = weighted_random_choice(ranges)
                reward_multiplier = random.uniform(chosen_range[0], chosen_range[1])
        except (ValueError, IndexError) as e:
            logger.error(f"擦弹时随机选择出错: {e}", exc_info=True)
            return {"success": False, "message": "擦弹失败，似乎时空发生了扭曲..."}

        # 6. 计算最终金额并执行事务
        reward_amount = int(contribution_amount * reward_multiplier)
        profit = reward_amount - contribution_amount

        # 检查是否触发服务器级别抑制（开出≥15x高倍率）
        suppression_triggered = False
        if reward_multiplier >= 15.0 and not suppressed:
            self._trigger_server_suppression()
            suppression_triggered = True

        # 7. 在同一个 user 对象上更新所有需要修改的属性
        user.coins += profit
        user.wipe_bomb_attempts_today += 1 # 增加当日计数

        if reward_multiplier > user.max_wipe_bomb_multiplier:
            user.max_wipe_bomb_multiplier = reward_multiplier
    
        if user.min_wipe_bomb_multiplier is None or reward_multiplier < user.min_wipe_bomb_multiplier:
            user.min_wipe_bomb_multiplier = reward_multiplier
        
        # 8. 一次性将所有用户数据的变更保存到数据库
        self.user_repo.update(user)

        # 9. 记录日志
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

        # 10. 构建返回结果
        result = {
            "success": True,
            "contribution": contribution_amount,
            "multiplier": reward_multiplier,
            "reward": reward_amount,
            "profit": profit,
            # 使用 user 对象中的新计数值来计算剩余次数
            "remaining_today": total_max_attempts - user.wipe_bomb_attempts_today,
        }
        
        if suppression_triggered:
            result["suppression_notice"] = "✨ 天界之力降临！你的惊人运气触发了时空沙漏的平衡法则！为了避免时空扭曲，命运女神暂时调整了概率之流，但宝藏之门依然为你敞开！"
        
        return result

    # ============================================================
    # ================= 新增功能：命运之轮 (交互版) 开始 ===========
    # ============================================================
    
    def _reset_wof_state(self, user: User, cash_out_prize: int = 0) -> None:
        """内部辅助函数，用于重置用户的游戏状态并保存。"""
        if cash_out_prize > 0:
            user.coins += cash_out_prize
        user.in_wheel_of_fate = False
        user.last_wof_play_time = get_now()
        user.wof_last_action_time = None
        self.user_repo.update(user)

    def handle_wof_timeout(self, user_id: str) -> Dict[str, Any] | None:
        """检查并处理指定用户的游戏超时。如果处理了超时，返回一个结果字典。"""
        user = self.user_repo.get_by_id(user_id)
        if not hasattr(user, 'in_wheel_of_fate') or not user.in_wheel_of_fate or not user.wof_last_action_time:
            return None

        config = self.WHEEL_OF_FATE_CONFIG
        timeout_seconds = config.get("timeout_seconds", 60)
        now = get_now()
        
        if (now - user.wof_last_action_time).total_seconds() > timeout_seconds:
            prize = user.wof_current_prize
            self._reset_wof_state(user, cash_out_prize=prize)
            
            message = f"[CQ:at,qq={user_id}] ⏰ 你的操作已超时，系统已自动为你结算当前奖金 {prize} 金币。"
            logger.info(f"用户 {user_id} 命运之轮超时，自动结算 {prize} 金币。")
            
            return {"success": True, "status": "timed_out", "message": message}
        return None

    def start_wheel_of_fate(self, user_id: str, entry_fee: int) -> Dict[str, Any]:
        """开始一局“命运之轮”游戏。"""
        user = self.user_repo.get_by_id(user_id)
        if not user: return {"success": False, "message": "用户不存在"}
        
        # 检查 User 对象是否具有所需属性，提供向后兼容性
        if not all(hasattr(user, attr) for attr in ['in_wheel_of_fate', 'wof_last_action_time', 'last_wof_play_time', 'wof_plays_today', 'last_wof_date']):
             return {"success": False, "message": "错误：用户数据结构不完整，请联系管理员更新数据库。"}

        timeout_result = self.handle_wof_timeout(user_id)
        if timeout_result:
            user = self.user_repo.get_by_id(user_id)

        if user.in_wheel_of_fate:
            return {"success": False, "message": f"[CQ:at,qq={user_id}] 你已经在游戏中了，请回复【继续】或【放弃】。"}

        # --- [新功能] 每日次数限制逻辑 ---
        wheel_of_fate_daily_limit = self.config.get("wheel_of_fate_daily_limit", 3)
        today_str = get_today().strftime('%Y-%m-%d')

        # 如果记录的日期不是今天，重置计数器
        if user.last_wof_date != today_str:
            user.wof_plays_today = 0
            user.last_wof_date = today_str

        # 检查次数是否已达上限
        if user.wof_plays_today >= wheel_of_fate_daily_limit:
            return {"success": False, "message": f"今天的运气已经用光啦！你今天已经玩了 {user.wof_plays_today}/{wheel_of_fate_daily_limit} 次命运之轮，请明天再来吧。"}
        # --- 限制逻辑结束 ---

        config = self.WHEEL_OF_FATE_CONFIG
        min_fee = config.get("min_entry_fee", 500)
        max_fee = config.get("max_entry_fee", 50000)
        cooldown = config.get("cooldown_seconds", 60)
        now = get_now()

        if user.last_wof_play_time and (now - user.last_wof_play_time).total_seconds() < cooldown:
            remaining = int(cooldown - (now - user.last_wof_play_time).total_seconds())
            return {"success": False, "message": f"[CQ:at,qq={user_id}] 命运之轮冷却中，请等待 {remaining} 秒后再试。"}

        if not min_fee <= entry_fee <= max_fee:
            return {"success": False, "message": f"[CQ:at,qq={user_id}] 入场费必须在 {min_fee} 到 {max_fee} 金币之间。"}
        if not user.can_afford(entry_fee):
            return {"success": False, "message": f"[CQ:at,qq={user_id}] 金币不足，当前拥有 {user.coins} 金币。"}

        user.coins -= entry_fee
        user.in_wheel_of_fate = True
        user.wof_current_level = 0
        user.wof_current_prize = entry_fee
        user.wof_entry_fee = entry_fee
        user.wof_last_action_time = now
        
        # [新功能] 游戏次数加一
        user.wof_plays_today += 1
        
        self.user_repo.update(user) # 保存所有更新

        return self.continue_wheel_of_fate(user_id, user_obj=user)

    def continue_wheel_of_fate(self, user_id: str, user_obj: User | None = None) -> Dict[str, Any]:
        """在命运之轮中继续挑战下一层。"""

        if timeout_result := self.handle_wof_timeout(user_id):
            return timeout_result

        user = user_obj if user_obj else self.user_repo.get_by_id(user_id)
        if not hasattr(user, 'in_wheel_of_fate') or not user.in_wheel_of_fate:
            return {"success": False, "status": "not_in_game", "message": "⚠️ 你当前不在命运之轮游戏中，无法继续。"}

        config = self.WHEEL_OF_FATE_CONFIG
        levels = config.get("levels", [])
        
        next_level_index = user.wof_current_level
        if next_level_index >= len(levels):
            return self.cash_out_wheel_of_fate(user_id, is_final_win=True)

        level_data = levels[next_level_index]
        success_rate = level_data.get("success_rate", 0.5)
        multiplier = level_data.get("multiplier", 1.0)
        
        if random.random() < success_rate:
            # 成功
            user.wof_current_level += 1
            user.wof_current_prize = round(user.wof_current_prize * multiplier)
            user.wof_last_action_time = get_now()
            
            if user.wof_current_level == len(levels):
                self.user_repo.update(user)
                return self.cash_out_wheel_of_fate(user_id, is_final_win=True)
            
            self.user_repo.update(user)
            
            next_level_data = levels[user.wof_current_level]
            next_success_rate = int(next_level_data.get("success_rate", 0.5) * 100)
            
            return {
                "success": True, "status": "ongoing",
                "message": (f"[CQ:at,qq={user_id}] 🎯 第 {user.wof_current_level} 层幸存！ (下一层成功率: {next_success_rate}%)\n"
                            f"💰 当前累积奖金 {user.wof_current_prize} 金币。\n"
                            f"⏱️ 请在{config.get('timeout_seconds', 60)}秒内回复【继续】或【放弃】！")
            }
        else:
            # 失败
            lost_amount = user.wof_entry_fee
            self._reset_wof_state(user)
            return {
                "success": True, "status": "lost",
                "message": (f"[CQ:at,qq={user_id}] 💥 湮灭！ "
                            f"你在通往第 {user.wof_current_level + 1} 层的路上失败了，失去了入场的 {lost_amount} 金币..."),
            }

    def cash_out_wheel_of_fate(self, user_id: str, is_final_win: bool = False) -> Dict[str, Any]:
        """从命运之轮中提现并结束游戏。"""

        if timeout_result := self.handle_wof_timeout(user_id):
            return timeout_result

        user = self.user_repo.get_by_id(user_id)
        if not hasattr(user, 'in_wheel_of_fate') or not user.in_wheel_of_fate:
            return {"success": False, "status": "not_in_game", "message": "⚠️ 你当前不在命运之轮游戏中，无法继续。"}

        prize = user.wof_current_prize
        entry = user.wof_entry_fee
        self._reset_wof_state(user, cash_out_prize=prize)

        if is_final_win:
            message = (f"🏆 [CQ:at,qq={user_id}] 命运的宠儿诞生了！ "
                       f"你成功征服了命运之轮的10层，最终赢得了 {prize} 金币的神话级奖励！")
        else:
            message = (f"✅ [CQ:at,qq={user_id}] 明智的选择！ "
                       f"你成功将 {prize} 金币带回了家，本次游戏净赚 {prize - entry} 金币。")
        
        return {"success": True, "status": "cashed_out", "message": message}

    # ============================================================
    # ================== 新增功能：命运之轮 结束 ==================
    # ============================================================

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
        处理"偷鱼"的逻辑。
        """
        if thief_id == victim_id:
            return {"success": False, "message": "不能偷自己的鱼！"}

        thief = self.user_repo.get_by_id(thief_id)
        if not thief:
            return {"success": False, "message": "偷窃者用户不存在"}

        victim = self.user_repo.get_by_id(victim_id)
        if not victim:
            return {"success": False, "message": "目标用户不存在"}

        # 0. 首先检查偷窃CD
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

        # 1. 检查受害者是否受保护，以及偷窃者是否有反制能力
        protection_buff = self.buff_repo.get_active_by_user_and_type(
            victim_id, "STEAL_PROTECTION_BUFF"
        )
        
        penetration_buff = self.buff_repo.get_active_by_user_and_type(
            thief_id, "STEAL_PENETRATION_BUFF"
        )
        shadow_cloak_buff = self.buff_repo.get_active_by_user_and_type(
            thief_id, "SHADOW_CLOAK_BUFF"
        )
        
        if protection_buff:
            if not penetration_buff and not shadow_cloak_buff:
                return {"success": False, "message": f"❌ 无法偷窃，【{victim.nickname}】的鱼塘似乎被神秘力量守护着！"}
            else:
                if shadow_cloak_buff:
                    self.buff_repo.delete(shadow_cloak_buff.id)

        # 2. 检查受害者是否有鱼可偷
        victim_inventory = self.inventory_repo.get_fish_inventory(victim_id)
        if not victim_inventory:
            return {"success": False, "message": f"目标用户【{victim.nickname}】的鱼塘是空的！"}

        # 3. 随机选择一条鱼偷取
        stolen_fish_item = random.choice(victim_inventory)
        stolen_fish_template = self.item_template_repo.get_fish_by_id(stolen_fish_item.fish_id)

        if not stolen_fish_template:
            return {"success": False, "message": "发生内部错误，无法识别被偷的鱼"}

        # 4. 执行偷窃事务（保持品质属性）
        self.inventory_repo.update_fish_quantity(victim_id, stolen_fish_item.fish_id, delta=-1, quality_level=stolen_fish_item.quality_level)
        self.inventory_repo.add_fish_to_inventory(thief_id, stolen_fish_item.fish_id, quantity=1, quality_level=stolen_fish_item.quality_level)

        # 5. 更新偷窃者的CD时间
        thief.last_steal_time = now
        self.user_repo.update(thief)

        # 6. 生成成功消息
        counter_message = ""
        if protection_buff:
            if penetration_buff:
                counter_message = "⚡ 破灵符的力量穿透了海灵守护！"
            elif shadow_cloak_buff:
                counter_message = "🌑 暗影斗篷让你在阴影中行动！"

        # 构建品质信息
        quality_info = ""
        actual_value = stolen_fish_template.base_value
        if stolen_fish_item.quality_level == 1:
            quality_info = "（✨高品质）"
            actual_value = stolen_fish_template.base_value * 2
        
        return {
            "success": True,
            "message": f"{counter_message}✅ 成功从【{victim.nickname}】的鱼塘里偷到了一条{stolen_fish_template.rarity}★【{stolen_fish_template.name}】{quality_info}！价值 {actual_value} 金币",
        }

    # ============================================================
    # ==================== 新增功能：电鱼 开始 ====================
    # ============================================================
    def electric_fish(self, thief_id: str, victim_id: str) -> Dict[str, Any]:
        """
        处理"电鱼"的逻辑。
        - 基础成功率，受多种因素影响
        - 失败会扣除金币作为设备损坏费
        - 成功有三个档次：大成功、普通成功、小成功
        - 对鱼塘内鱼数>=100的目标随机偷取
        - 其中最多只能包含一条5星及以上的鱼
        """
        if thief_id == victim_id:
            return {"success": False, "message": "不能电自己的鱼！"}
    
        thief = self.user_repo.get_by_id(thief_id)
        if not thief:
            return {"success": False, "message": "使用者用户不存在"}
    
        victim = self.user_repo.get_by_id(victim_id)
        if not victim:
            return {"success": False, "message": "目标用户不存在"}
    
        # 0. 检查电鱼CD
        cooldown_seconds = self.config.get("electric_fish", {}).get("cooldown_seconds", 10800) # 默认3小时
        now = get_now()
    
        last_electric_fish_time = thief.last_electric_fish_time
        if last_electric_fish_time and last_electric_fish_time.tzinfo is None and now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        elif last_electric_fish_time and last_electric_fish_time.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=last_electric_fish_time.tzinfo)
    
        if last_electric_fish_time and (now - last_electric_fish_time).total_seconds() < cooldown_seconds:
            remaining = int(cooldown_seconds - (now - last_electric_fish_time).total_seconds())
            return {"success": False, "message": f"电鱼冷却中，请等待 {remaining // 60} 分钟后再试"}
    
        # 1. 检查受害者是否受保护，逻辑同偷鱼
        protection_buff = self.buff_repo.get_active_by_user_and_type(
            victim_id, "STEAL_PROTECTION_BUFF"
        )
        
        penetration_buff = self.buff_repo.get_active_by_user_and_type(
            thief_id, "STEAL_PENETRATION_BUFF"
        )
        shadow_cloak_buff = self.buff_repo.get_active_by_user_and_type(
            thief_id, "SHADOW_CLOAK_BUFF"
        )
        
        if protection_buff:
            if not penetration_buff and not shadow_cloak_buff:
                return {"success": False, "message": f"❌ 无法电鱼，【{victim.nickname}】的鱼塘似乎被神秘力量守护着！"}
            else:
                if shadow_cloak_buff:
                    self.buff_repo.delete(shadow_cloak_buff.id)
    
        # 2. 检查受害者鱼塘数量是否达标
        victim_inventory = self.inventory_repo.get_fish_inventory(victim_id)
        if not victim_inventory:
            return {"success": False, "message": f"目标用户【{victim.nickname}】的鱼塘是空的！"}
        
        total_fish_count = sum(item.quantity for item in victim_inventory)
        if total_fish_count < 100:
            return {"success": False, "message": f"目标用户【{victim.nickname}】的鱼塘里鱼太少了（{total_fish_count}/100），电不到什么好东西，还是放过他吧。"}
        
        # 3. 计算成功率并进行判定
        # 所有目标用户的成功率相同，只使用基础成功率
        final_success_rate = self.config.get("electric_fish", {}).get("base_success_rate", 0.6)
        
        # 进行随机判定
        roll = random.random()
        
        # 失败处理
        if roll > final_success_rate:
            # 使用正态分布计算天罚百分比（0-max_rate之间）
            max_penalty_rate = self.config.get("electric_fish", {}).get("failure_penalty_max_rate", 0.5)
            
            # 正态分布，均值在中间（max_rate/2），标准差使得95%的值在0到max_rate之间
            mean = max_penalty_rate / 2
            std_dev = max_penalty_rate / 4  # 约95%的值在[0, max_rate]之间
            
            # 使用random.gauss生成正态分布的惩罚比例，并限制在[0, max_rate]范围内
            penalty_rate = random.gauss(mean, std_dev)
            penalty_rate = max(0.0, min(max_penalty_rate, penalty_rate))
            
            # 计算实际扣除的金币
            penalty_coins = int(thief.coins * penalty_rate)
            
            thief.coins -= penalty_coins
            thief.last_electric_fish_time = now  # 失败也要更新CD
            self.user_repo.update(thief)
            
            # 根据惩罚程度显示不同的消息（动态基于配置的最大天罚）
            # 轻微: 0-20%的max, 中度: 20-50%的max, 严重: 50-80%的max, 毁灭性: 80-100%的max
            relative_penalty = penalty_rate / max_penalty_rate if max_penalty_rate > 0 else 0
            if relative_penalty < 0.2:
                severity = "⚡ 轻微天罚"
            elif relative_penalty < 0.5:
                severity = "⚡⚡ 中度天罚"
            elif relative_penalty < 0.8:
                severity = "⚡⚡⚡ 严重天罚"
            else:
                severity = "⚡⚡⚡⚡ 毁灭性天罚"
            
            return {
                "success": False,
                "message": f"❌ 电鱼失败！{severity}降临，雷电击中了你，损失了 {penalty_coins} 金币（{penalty_rate*100:.1f}%）！\n💡 本次成功率为 {final_success_rate*100:.1f}%"
            }

        # 4. 成功了！根据成功度（roll值）决定收益档次
        # roll越接近0表示越幸运，获得的收益越高
        success_quality = roll / final_success_rate  # 归一化到0-1之间
        
        # 分段式收益：
        # - 大成功（0-0.3）：15%-20%的鱼
        # - 普通成功（0.3-0.7）：10%-15%的鱼
        # - 小成功（0.7-1.0）：5%-10%的鱼
        success_type = ""
        multiplier_range = (0, 0)
        
        if success_quality <= 0.3:
            success_type = "⭐大成功"
            multiplier_range = (0.15, 0.20)
        elif success_quality <= 0.7:
            success_type = "✅普通成功"
            multiplier_range = (0.10, 0.15)
        else:
            success_type = "🔹小成功"
            multiplier_range = (0.05, 0.10)
        
        # 5. 准备数据：获取鱼模板并将鱼塘扁平化
        fish_templates = {
            item.fish_id: self.item_template_repo.get_fish_by_id(item.fish_id)
            for item in victim_inventory
        }
        all_fish_in_pond = []
        for item in victim_inventory:
            all_fish_in_pond.extend([item.fish_id] * item.quantity)

        # 6. 决定偷取数量并进行初次完全随机抽样
        num_to_steal = 0
        if total_fish_count > 400:
            # 如果鱼数大于400，按成功档次的百分比计算
            lower_bound = max(1, int(total_fish_count * multiplier_range[0]))
            upper_bound = max(lower_bound, int(total_fish_count * multiplier_range[1]))
            num_to_steal = random.randint(lower_bound, upper_bound)
        else:
            # 鱼数较少时，使用固定数量区间
            if success_quality <= 0.3:
                num_to_steal = random.randint(20, 30)  # 大成功
            elif success_quality <= 0.7:
                num_to_steal = random.randint(10, 20)  # 普通成功
            else:
                num_to_steal = random.randint(5, 10)   # 小成功

        actual_num_to_steal = min(num_to_steal, len(all_fish_in_pond))
        initial_catch = random.sample(all_fish_in_pond, actual_num_to_steal)

        # 7. 检查并修正高星鱼数量
        high_rarity_caught = []
        low_rarity_caught = []
        for fish_id in initial_catch:
            template = fish_templates.get(fish_id)
            if template and template.rarity >= 5:
                high_rarity_caught.append(fish_id)
            else:
                low_rarity_caught.append(fish_id)
        
        final_stolen_fish_ids = []
        if len(high_rarity_caught) <= 1:
            final_stolen_fish_ids = initial_catch
        else:
            random.shuffle(high_rarity_caught)
            final_stolen_fish_ids.append(high_rarity_caught.pop(0))
            final_stolen_fish_ids.extend(low_rarity_caught)
            
            num_to_replace = len(high_rarity_caught)

            from collections import Counter
            pond_counts = Counter(all_fish_in_pond)
            initial_catch_counts = Counter(initial_catch)
            pond_counts.subtract(initial_catch_counts)

            replacement_pool = []
            for fish_id, count in pond_counts.items():
                if count > 0:
                    template = fish_templates.get(fish_id)
                    if template and template.rarity < 5:
                        replacement_pool.extend([fish_id] * count)
            
            if replacement_pool:
                num_can_replace = min(num_to_replace, len(replacement_pool))
                replacements = random.sample(replacement_pool, num_can_replace)
                final_stolen_fish_ids.extend(replacements)

        # 8. 统计最终偷到的鱼
        stolen_fish_counts = {}
        for fish_id in final_stolen_fish_ids:
            stolen_fish_counts[fish_id] = stolen_fish_counts.get(fish_id, 0) + 1
    
        # 9. 执行电鱼事务并计算总价值
        stolen_summary = []
        total_value_stolen = 0
    
        for fish_id, count in stolen_fish_counts.items():
            self.inventory_repo.update_fish_quantity(victim_id, fish_id, delta=-count, quality_level=0)
            self.inventory_repo.add_fish_to_inventory(thief_id, fish_id, quantity=count, quality_level=0)
            
            template = fish_templates.get(fish_id)
            if template:
                stolen_summary.append(f"【{template.name}】x{count}")
                total_value_stolen += template.base_value * count
    
        # 10. 更新电鱼的CD时间并保存
        thief.last_electric_fish_time = now
        self.user_repo.update(thief)
    
        # 11. 生成成功消息
        counter_message = ""
        if protection_buff:
            if penetration_buff:
                counter_message = "⚡ 破灵符的力量穿透了海灵守护！\n"
            elif shadow_cloak_buff:
                counter_message = "🌑 暗影斗篷让你在阴影中行动！\n"
    
        stolen_details = "、".join(stolen_summary)
        actual_stolen_count = len(final_stolen_fish_ids)
        
        # 计算收益占比
        steal_percentage = (actual_stolen_count / total_fish_count) * 100
        
        return {
            "success": True,
            "message": f"{counter_message}{success_type}！成功对【{victim.nickname}】的鱼塘进行了电击，捕获了{actual_stolen_count}条鱼（占其总数的{steal_percentage:.1f}%），总价值 {total_value_stolen} 金币！\n分别是：{stolen_details}。\n💡 本次成功率为 {final_success_rate*100:.1f}%",
        }
    # ============================================================
    # ===================== 新增功能：电鱼 结束 =====================
    # ============================================================

    def dispel_steal_protection(self, target_id: str) -> Dict[str, Any]:
        """
        驱散目标的海灵守护效果
        """
        target = self.user_repo.get_by_id(target_id)
        if not target:
            return {"success": False, "message": "目标用户不存在"}

        protection_buff = self.buff_repo.get_active_by_user_and_type(
            target_id, "STEAL_PROTECTION_BUFF"
        )
        
        if not protection_buff:
            return {"success": False, "message": f"【{target.nickname}】没有海灵守护效果"}
        
        self.buff_repo.delete(protection_buff.id)
        
        return {
            "success": True, 
            "message": f"成功驱散了【{target.nickname}】的海灵守护效果"
        }

    def check_steal_protection(self, target_id: str) -> Dict[str, Any]:
        """
        检查目标是否有海灵守护效果
        """
        target = self.user_repo.get_by_id(target_id)
        if not target:
            return {"has_protection": False, "target_name": "未知用户", "message": "目标用户不存在"}

        protection_buff = self.buff_repo.get_active_by_user_and_type(
            target_id, "STEAL_PROTECTION_BUFF"
        )
        
        return {
            "has_protection": protection_buff is not None,
            "target_name": target.nickname,
            "message": f"【{target.nickname}】{'有' if protection_buff else '没有'}海灵守护效果"
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
        sell_price_config = self.config.get("sell_prices", {})
        
        base_prices = sell_price_config.get(item_type, {})
        base_price = base_prices.get(str(rarity), 0)

        # 如果配置中没有该稀有度的基础价格，使用基于稀有度的公式计算默认值
        # 公式：基础价 = 100 * (2.5 ^ (rarity - 1))，确保高稀有度物品有合理的价格
        if base_price <= 0:
            # 使用指数增长公式：1星=100, 2星≈250, 3星≈625, 4星≈1562, 5星≈3906, 6星≈9765, 7星≈24414, 8星≈61035, 9星≈152587, 10星≈381469
            base_price = int(100 * (2.5 ** (rarity - 1)))
            # 确保最低价格为 100
            base_price = max(100, base_price)

        refine_multipliers = sell_price_config.get("refine_multiplier", {})
        refine_multiplier = refine_multipliers.get(str(refine_level), 1.0)

        final_price = int(base_price * refine_multiplier)

        # 确保最终价格至少为 30 金币（防止计算错误导致负值或零值）
        if final_price <= 0:
            return 30  # 默认最低价格

        return final_price

    # ============================================================
    # ==================== 新增功能：骰宝 (大小) 开始 ====================
    # ============================================================
    def play_sicbo(self, user_id: str, bet_type: str, amount: int) -> Dict[str, Any]:
        """处理骰宝（押大小）游戏的核心逻辑"""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "❌ 用户不存在。"}

        # 1. 冷却时间检查 (例如：5秒)
        cooldown_seconds = 5
        now = get_now()
        if user.last_sicbo_time and (now - user.last_sicbo_time).total_seconds() < cooldown_seconds:
            remaining = int(cooldown_seconds - (now - user.last_sicbo_time).total_seconds())
            return {"success": False, "message": f"⏳ 操作太快了，请等待 {remaining} 秒后再试。"}

        # 2. 验证下注
        valid_bets = ['大', '小']
        if bet_type not in valid_bets:
            return {"success": False, "message": "❌ 押注类型错误！只能押 `大` 或 `小`。"}
        if amount <= 0:
            return {"success": False, "message": "❌ 押注金额必须大于0！"}
        if not user.can_afford(amount):
            return {"success": False, "message": f"💰 你的金币不足！当前拥有 {user.coins:,} 金币。"}

        # 3. 扣除押金并开始游戏
        user.coins -= amount
        
        # 4. 投掷三个骰子
        dice = [random.randint(1, 6) for _ in range(3)]
        total = sum(dice)
        
        # 5. 判断结果
        is_triple = (dice[0] == dice[1] == dice[2])
        
        if 4 <= total <= 10:
            result_type = '小'
        elif 11 <= total <= 17:
            result_type = '大'
        else: # 只有豹子会落到这个区间外
            result_type = '豹子'

        # 6. 判断输赢
        # 规则：如果开出豹子，庄家通吃
        win = False
        if not is_triple and bet_type == result_type:
            win = True

        # 7. 结算
        profit = 0
        if win:
            winnings = amount * 2 # 1:1赔率，返还本金+1倍奖金
            profit = amount
            user.coins += winnings
        else:
            profit = -amount # 输了，损失本金

        # 8. 更新用户状态并保存
        user.last_sicbo_time = now
        self.user_repo.update(user)

        # 9. 返回详细的游戏结果
        return {
            "success": True,
            "win": win,
            "dice": dice,
            "total": total,
            "result_type": result_type,
            "is_triple": is_triple,
            "profit": profit,
            "new_balance": user.coins
        }