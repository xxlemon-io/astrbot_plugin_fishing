import random
import threading
import time
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Any, Optional

from astrbot.api import logger

from ..domain.models import Exchange
from ..repositories.abstract_repository import AbstractExchangeRepository


class ExchangePriceService:
    """交易所价格管理服务"""
    
    def __init__(self, exchange_repo: AbstractExchangeRepository, config: Dict[str, Any]):
        self.exchange_repo = exchange_repo
        self.config = config.get("exchange", {})
        self._update_schedule = self._parse_update_schedule(self.config.get("update_timing"))
        
        # 商品定义
        self.commodities = {
            "dried_fish": {"name": "鱼干", "description": "经过晾晒处理的鱼类，保质期较长"},
            "fish_roe": {"name": "鱼卵", "description": "珍贵的鱼类卵子，营养价值极高"},
            "fish_oil": {"name": "鱼油", "description": "从鱼类中提取的油脂，用途广泛"}
        }
        
        # 价格更新任务
        self._price_update_thread: Optional[threading.Thread] = None
        self._price_update_running = False

    def get_market_status(self) -> Dict[str, Any]:
        """获取市场状态"""
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            prices = self.exchange_repo.get_prices_for_date(today_str)
            
            if not prices:
                # 如果没有今日价格，尝试获取昨日价格
                yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                y_prices = self.exchange_repo.get_prices_for_date(yesterday_str)
                if y_prices:
                    price_data = {p.commodity_id: p.price for p in y_prices}
                    return {
                        "success": True,
                        "prices": price_data,
                        "commodities": self.commodities,
                        "market_sentiment": "neutral",
                        "price_trend": "stable",
                        "supply_demand": "平衡",
                        "date": today_str
                    }
                # 昨日也没有则返回初始价格
                initial_prices = self.config.get("initial_prices", {
                    "dried_fish": 6000,
                    "fish_roe": 12000,
                    "fish_oil": 10000
                })
                return {
                    "success": True,
                    "prices": initial_prices,
                    "commodities": self.commodities,
                    "market_sentiment": "neutral",
                    "price_trend": "stable",
                    "supply_demand": "平衡",
                    "date": today_str
                }

            price_data = {p.commodity_id: p.price for p in prices}
            return {
                "success": True,
                "prices": price_data,
                "commodities": self.commodities,
                "market_sentiment": "neutral",
                "price_trend": "stable",
                "supply_demand": "平衡",
                "date": today_str
            }
        except Exception as e:
            logger.error(f"获取市场状态失败: {e}")
            return {"success": False, "message": f"获取市场状态失败: {e}"}

    def get_price_history(self, days: int = 7) -> Dict[str, Any]:
        """获取价格历史"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days-1)  # 包含今天
            
            history = {}
            labels = []
            all_updates = []  # 存储所有价格更新点
            
            # 获取所有价格更新记录
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                prices = self.exchange_repo.get_prices_for_date(date_str)
                
                for price_obj in prices:
                    all_updates.append({
                        'date': price_obj.date,
                        'time': price_obj.time,
                        'commodity_id': price_obj.commodity_id,
                        'price': price_obj.price,
                        'update_type': price_obj.update_type,
                        'datetime': f"{price_obj.date} {price_obj.time}"
                    })
                
                current_date += timedelta(days=1)
            
            # 按时间排序
            all_updates.sort(key=lambda x: x['datetime'])
            
            # 生成标签（显示日期和时间）
            for update in all_updates:
                date_obj = datetime.strptime(update['date'], "%Y-%m-%d")
                time_obj = datetime.strptime(update['time'], "%H:%M:%S")
                # 统一到秒，避免 "HH:MM:SS" 与 "HH:MM" 的字符串比较问题
                label = f"{date_obj.strftime('%m-%d')} {time_obj.strftime('%H:%M:%S')}"
                if label not in labels:
                    labels.append(label)
            
            # 为每种商品生成价格序列
            for commodity_id in self.commodities.keys():
                history[commodity_id] = []
                commodity_updates = [u for u in all_updates if u['commodity_id'] == commodity_id]
                
                # 为安全起见确保按时间升序（all_updates 已排序，这里等同于稳定过滤）
                # commodity_updates 已按 all_updates 的顺序排列

                last_known_price: Optional[int] = None  # 跨 label 继承用

                # 为每个标签点找到对应的价格
                for label in labels:
                    # 找到该时间点之前的最新价格
                    label_time = label.split(' ')[1]  # 提取时间部分
                    label_date = label.split(' ')[0]  # 提取日期部分
                    
                    # 找到该时间点之前（含该时刻）的最新价格（同一天）
                    latest_price = None
                    for update in commodity_updates:
                        update_date = datetime.strptime(update['date'], "%Y-%m-%d").strftime('%m-%d')
                        if update_date == label_date and update['time'] <= label_time:
                            latest_price = update['price']
                        # 这里不 break，确保拿到“该时刻之前”的最后一条

                    if latest_price is not None:
                        last_known_price = latest_price
                        history[commodity_id].append(latest_price)
                    else:
                        # 没有同日早于该时刻的记录，则延续上一个 label 的价格
                        if last_known_price is not None:
                            history[commodity_id].append(last_known_price)
                        else:
                            # 序列开头仍未知时，才使用初始价格
                            initial_price = self.config.get("initial_prices", {}).get(commodity_id, 1000)
                            last_known_price = initial_price
                            history[commodity_id].append(initial_price)
            
            return {
                "success": True,
                "history": history,
                "labels": labels,
                "days": days,
                "updates": all_updates  # 包含所有更新信息
            }
        except Exception as e:
            logger.error(f"获取价格历史失败: {e}")
            return {"success": False, "message": str(e)}

    def manual_update_prices(self) -> Dict[str, Any]:
        """手动更新价格（管理员）"""
        try:
            logger.info("管理员手动触发价格更新...")
            today_str = datetime.now().strftime("%Y-%m-%d")
            # 为本次批量更新生成统一的批次时间，确保多商品在同一时间点对齐
            batch_now = datetime.now()
            batch_time_str = batch_now.strftime("%H:%M:%S")
            batch_created_at = batch_now.isoformat()
            
            # 先获取“上一次价格”作为基准（优先今日最新，其次昨日，最后初始）
            base_prices: Dict[str, int] = {}
            today_prices = self.exchange_repo.get_prices_for_date(today_str)
            if today_prices:
                # 取今日各商品的最新一条（按时间升序覆盖即可）
                for p in sorted(today_prices, key=lambda x: x.time):
                    base_prices[p.commodity_id] = p.price

            # 对缺失的商品，回退到昨日
            if len(base_prices) < len(self.commodities):
                yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                y_prices = self.exchange_repo.get_prices_for_date(yesterday_str)
                for p in sorted(y_prices, key=lambda x: x.time):
                    if p.commodity_id not in base_prices:
                        base_prices[p.commodity_id] = p.price

            # 仍缺失则使用初始价格
            if len(base_prices) < len(self.commodities):
                for commodity_id in self.commodities.keys():
                    if commodity_id not in base_prices:
                        base_prices[commodity_id] = self.config.get("initial_prices", {}).get(commodity_id, 1000)
            
            logger.info(f"基于当前价格更新：{base_prices}")
            
            # 计算新价格
            new_prices = {}
            for commodity_id in self.commodities.keys():
                last_price = base_prices.get(commodity_id, 100)
                new_price = self._calculate_new_price(commodity_id, last_price)
                new_prices[commodity_id] = new_price
                
                # 记录价格变化
                change_percent = ((new_price - last_price) / last_price) * 100
                logger.info(f"价格变化 {commodity_id}: {last_price} -> {new_price} ({change_percent:+.2f}%)")
                # 使用统一的批次时间写入，避免同一批次内不同商品 time 不一致
                self.exchange_repo.add_exchange_price(Exchange(
                    date=today_str,
                    time=batch_time_str,
                    commodity_id=commodity_id,
                    price=new_price,
                    update_type="manual",
                    created_at=batch_created_at
                ))
            
            logger.info(f"强制价格更新完成，新价格：{new_prices}")
            
            return {
                "success": True,
                "message": "价格更新成功",
                "prices": new_prices
            }
        except Exception as e:
            logger.error(f"手动更新价格失败: {e}")
            return {"success": False, "message": f"更新失败: {str(e)}"}

    def reset_prices_to_initial(self) -> Dict[str, Any]:
        """重置价格到初始值（管理员）"""
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            # 统一批次时间，确保写入的 time 一致
            batch_now = datetime.now()
            batch_time_str = batch_now.strftime("%H:%M:%S")
            batch_created_at = batch_now.isoformat()
            
            # 删除今日现有价格
            self.exchange_repo.delete_prices_for_date(today_str)
            
            # 设置初始价格
            initial_prices = self.config.get("initial_prices", {
                "dried_fish": 6000,
                "fish_roe": 12000,
                "fish_oil": 10000
            })
            
            for commodity_id, price in initial_prices.items():
                self.exchange_repo.add_exchange_price(Exchange(
                    date=today_str,
                    time=batch_time_str,
                    commodity_id=commodity_id,
                    price=price,
                    update_type="manual",
                    created_at=batch_created_at
                ))
            
            return {
                "success": True,
                "message": "价格已重置到初始值",
                "prices": initial_prices
            }
        except Exception as e:
            logger.error(f"重置价格失败: {e}")
            return {"success": False, "message": f"重置失败: {str(e)}"}

    def _calculate_new_price(self, commodity_id: str, current_price: int) -> int:
        """计算新价格"""
        # 获取商品配置
        commodity_config = self.config.get("commodities", {}).get(commodity_id, {})
        volatility = commodity_config.get("volatility", 0.1)
        max_change_rate = self.config.get("max_change_rate", 0.2)
        
        # 随机调整
        random_factor = random.uniform(-1, 1)
        change_rate = random_factor * volatility
        
        # 应用变化率限制
        change_rate = max(-max_change_rate, min(max_change_rate, change_rate))
        
        # 计算新价格
        new_price = int(current_price * (1 + change_rate))
        
        # 确保价格不会过低
        min_price = max(1, int(current_price * 0.1))
        new_price = max(min_price, new_price)
        
        return new_price

    def start_daily_price_update_task(self):
        """启动每日价格更新任务"""
        if self._price_update_thread and self._price_update_thread.is_alive():
            logger.info("价格更新线程已在运行中")
            return

        self._price_update_running = True
        self._price_update_thread = threading.Thread(target=self._daily_price_update_loop, daemon=True)
        self._price_update_thread.start()
        logger.info("价格更新线程已启动")

    def stop_daily_price_update_task(self):
        """停止每日价格更新任务"""
        self._price_update_running = False
        if self._price_update_thread:
            self._price_update_thread.join(timeout=1.0)
            logger.info("价格更新线程已停止")

    def _daily_price_update_loop(self):
        """每日价格更新循环"""
        # 启动时立即检查是否需要更新价格
        logger.info("价格更新线程启动，检查当前价格状态...")
        try:
            self.update_daily_prices()
        except Exception as e:
            logger.error(f"启动时价格检查失败: {e}")
        
        while self._price_update_running:
            try:
                # 等待到下一个更新时间
                now = datetime.now()
                next_update = self._get_next_update_time(now)
                wait_seconds = (next_update - now).total_seconds()
                
                if wait_seconds > 0:
                    logger.info(f"等待 {wait_seconds/3600:.1f} 小时后进行下次价格更新")
                    # 分段等待，以便能够及时响应停止信号
                    while wait_seconds > 0 and self._price_update_running:
                        sleep_time = min(60, wait_seconds)  # 最多等待60秒
                        time.sleep(sleep_time)
                        wait_seconds -= sleep_time
                
                if not self._price_update_running:
                    break
                
                # 更新价格（内部已有重复检查机制）
                logger.info("开始执行价格更新...")
                self.update_daily_prices()
                logger.info("价格更新完成")
                
            except Exception as e:
                # 记录错误但继续运行
                logger.error(f"交易所价格更新任务出错: {e}")
                logger.error("堆栈信息:", exc_info=True)
                time.sleep(3600)  # 出错后等待1小时再重试

    def _parse_update_schedule(self, value: Any) -> List[dt_time]:
        """Parse update_timing config into a sorted list of time objects."""
        candidates: List[str] = []
        if isinstance(value, str):
            normalized = value.replace("、", ",")
            normalized = normalized.replace("，", ",")
            candidates = [part.strip() for part in normalized.split(",") if part.strip()]
        elif isinstance(value, (list, tuple)):
            for item in value:
                if item is None:
                    continue
                for sub_part in str(item).replace("、", ",").split(","):
                    sub_part = sub_part.strip()
                    if sub_part:
                        candidates.append(sub_part)

        parsed: List[dt_time] = []
        for candidate in candidates:
            try:
                parsed_time = datetime.strptime(candidate, "%H:%M").time()
            except ValueError:
                try:
                    parsed_time = datetime.strptime(candidate, "%H").time()
                except ValueError:
                    logger.warning(f"Invalid update_timing entry skipped: {candidate}")
                    continue
            parsed.append(parsed_time.replace(second=0, microsecond=0))

        if not parsed:
            return [dt_time(hour=9), dt_time(hour=15), dt_time(hour=21)]

        unique_sorted = sorted({(t.hour, t.minute) for t in parsed})
        return [dt_time(hour=hour, minute=minute) for hour, minute in unique_sorted]

    def get_update_schedule(self) -> List[dt_time]:
        """Expose configured update schedule as datetime.time objects."""
        return list(self._update_schedule)

    def _get_update_times(self) -> List[dt_time]:
        if not self._update_schedule:
            self._update_schedule = [dt_time(hour=9), dt_time(hour=15), dt_time(hour=21)]
        return self._update_schedule

    def _get_next_update_time(self, now: datetime) -> datetime:
        """获取下一个更新时间"""
        update_times = self._get_update_times()

        for scheduled_time in update_times:
            next_update = now.replace(
                hour=scheduled_time.hour,
                minute=scheduled_time.minute,
                second=0,
                microsecond=0,
            )
            if next_update > now:
                return next_update
        
        # 如果今天的所有更新时间都过了，返回明天的第一个更新时间
        tomorrow = now + timedelta(days=1)
        first_time = update_times[0]
        return tomorrow.replace(
            hour=first_time.hour,
            minute=first_time.minute,
            second=0,
            microsecond=0,
        )

    def _get_current_update_window(self, now: datetime) -> Optional[tuple[str, Optional[str]]]:
        """
        返回当前更新时间窗口 (start_time_str, end_time_str)
        - 区间为左闭右开 [start, end)
        - 最后一个窗口 end 为 None，表示到当天结束
        - 若当前不在任何窗口（如 09:00 前），返回 None
        """
        update_times = self._get_update_times()
        if not update_times:
            return None

        starts = [t for t in sorted(update_times)]
        now_time = now.time()

        # 若当前早于第一个窗口，返回 None（不更新）
        if now_time < starts[0]:
            return None

        for i, start in enumerate(starts):
            # 计算下一个窗口的开始
            end = starts[i + 1] if i + 1 < len(starts) else None
            # 判断是否落在 [start, end)
            if end is None:
                if now_time >= start:
                    return (start.strftime("%H:%M:%S"), None)
            elif start <= now_time < end:
                return (start.strftime("%H:%M:%S"), end.strftime("%H:%M:%S"))
        return None

    def update_daily_prices(self):
        """更新每日价格"""
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            now = datetime.now()

            # 确定当前是否处于允许的更新时间窗口
            window = self._get_current_update_window(now)
            if window is None:
                logger.info("当前不在自动更新时间窗口内，跳过自动更新")
                return
            window_start, window_end = window
            # 使用窗口开始时间作为本批次的统一时间戳，确保对齐
            batch_time_str = window_start
            batch_created_at = now.isoformat()

            # 检查今日是否已有当前窗口的自动更新
            existing_prices = self.exchange_repo.get_prices_for_date(today_str)
            if existing_prices:
                auto_updates_in_window = [
                    p for p in existing_prices
                    if p.update_type == "auto"
                    and p.time >= window_start
                    and (window_end is None or p.time < window_end)
                ]
                if auto_updates_in_window:
                    logger.info(f"今日在窗口 {window_start} - {window_end or '24:00:00'} 已更新，跳过自动更新")
                    return
            
            # 以“上一次价格”为基准：优先取今日最新记录；若无则回退到昨日；再无则初始
            last_prices: Dict[str, int] = {}
            # 今日最新
            if existing_prices:
                for p in sorted(existing_prices, key=lambda x: x.time):
                    last_prices[p.commodity_id] = p.price

            # 回退到昨日（仅填补缺失的商品）
            if len(last_prices) < len(self.commodities):
                yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                y_prices = self.exchange_repo.get_prices_for_date(yesterday_str)
                for p in sorted(y_prices, key=lambda x: x.time):
                    if p.commodity_id not in last_prices:
                        last_prices[p.commodity_id] = p.price

            # 最后使用初始价格补齐
            if len(last_prices) < len(self.commodities):
                init_prices = self.config.get("initial_prices", {
                    "dried_fish": 6000,
                    "fish_roe": 12000,
                    "fish_oil": 10000
                })
                for commodity_id in self.commodities.keys():
                    if commodity_id not in last_prices:
                        last_prices[commodity_id] = init_prices.get(commodity_id, 1000)

            logger.info(f"基于上一次价格更新：{last_prices}")

            # 如果没有商品数据，跳过价格更新
            if not self.commodities:
                return

            # 计算新价格
            new_prices = {}
            for commodity_id in self.commodities.keys():
                last_price = last_prices.get(commodity_id, self.config.get("initial_prices", {}).get(commodity_id, 100))
                new_price = self._calculate_new_price(commodity_id, last_price)
                new_prices[commodity_id] = new_price
                
                self.exchange_repo.add_exchange_price(Exchange(
                    date=today_str,
                    time=batch_time_str,
                    commodity_id=commodity_id,
                    price=new_price,
                    update_type="auto",
                    created_at=batch_created_at
                ))
            
            logger.info(f"价格更新完成，新价格：{new_prices}")

        except Exception as e:
            logger.error(f"更新每日价格失败: {e}")
