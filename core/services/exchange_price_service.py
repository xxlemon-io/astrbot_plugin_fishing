import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from astrbot.api import logger

from ..domain.models import Exchange
from ..repositories.abstract_repository import AbstractExchangeRepository


class ExchangePriceService:
    """交易所价格管理服务"""
    
    def __init__(self, exchange_repo: AbstractExchangeRepository, config: Dict[str, Any]):
        self.exchange_repo = exchange_repo
        self.config = config.get("exchange", {})
        
        # 商品定义
        self.commodities = {
            "dried_fish": {"name": "鱼干", "description": "经过晾晒处理的鱼类，保质期较长"},
            "fish_roe": {"name": "鱼卵", "description": "珍贵的鱼类卵子，营养价值极高"},
            "fish_oil": {"name": "鱼油", "description": "从鱼类中提取的油脂，用途广泛"}
        }
        
        # 价格更新任务
        self._price_update_task = None

    def get_market_status(self) -> Dict[str, Any]:
        """获取市场状态"""
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            prices = self.exchange_repo.get_prices_for_date(today_str)
            
            if not prices:
                # 如果没有今日价格，返回初始价格
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
                label = f"{date_obj.strftime('%m-%d')} {time_obj.strftime('%H:%M')}"
                if label not in labels:
                    labels.append(label)
            
            # 为每种商品生成价格序列
            for commodity_id in self.commodities.keys():
                history[commodity_id] = []
                commodity_updates = [u for u in all_updates if u['commodity_id'] == commodity_id]
                
                # 为每个标签点找到对应的价格
                for label in labels:
                    # 找到该时间点之前的最新价格
                    label_time = label.split(' ')[1]  # 提取时间部分
                    label_date = label.split(' ')[0]  # 提取日期部分
                    
                    # 找到该时间点之前的最新价格
                    latest_price = None
                    for update in commodity_updates:
                        update_date = datetime.strptime(update['date'], "%Y-%m-%d").strftime('%m-%d')
                        if update_date == label_date and update['time'] <= label_time:
                            latest_price = update['price']
                    
                    if latest_price is not None:
                        history[commodity_id].append(latest_price)
                    else:
                        # 如果没有价格记录，使用初始价格
                        initial_price = self.config.get("initial_prices", {}).get(commodity_id, 1000)
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
            
            # 删除今日现有价格
            self.exchange_repo.delete_prices_for_date(today_str)
            logger.info("已删除今日现有价格，准备强制更新")
            
            # 获取当前价格作为基础
            current_prices = {}
            for commodity_id in self.commodities.keys():
                # 尝试获取当前价格
                prices = self.exchange_repo.get_prices_for_date(today_str)
                if prices:
                    for price_obj in prices:
                        if price_obj.commodity_id == commodity_id:
                            current_prices[commodity_id] = price_obj.price
                            break
                
                # 如果没有当前价格，使用初始价格
                if commodity_id not in current_prices:
                    current_prices[commodity_id] = self.config.get("initial_prices", {}).get(commodity_id, 1000)
            
            logger.info(f"基于当前价格更新：{current_prices}")
            
            # 计算新价格
            new_prices = {}
            for commodity_id in self.commodities.keys():
                last_price = current_prices.get(commodity_id, 100)
                new_price = self._calculate_new_price(commodity_id, last_price)
                new_prices[commodity_id] = new_price
                
                # 记录价格变化
                change_percent = ((new_price - last_price) / last_price) * 100
                logger.info(f"价格变化 {commodity_id}: {last_price} -> {new_price} ({change_percent:+.2f}%)")
                
                now = datetime.now()
                self.exchange_repo.add_exchange_price(Exchange(
                    date=today_str,
                    time=now.strftime("%H:%M:%S"),
                    commodity_id=commodity_id,
                    price=new_price,
                    update_type="manual",
                    created_at=now.isoformat()
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
            
            # 删除今日现有价格
            self.exchange_repo.delete_prices_for_date(today_str)
            
            # 设置初始价格
            initial_prices = self.config.get("initial_prices", {
                "dried_fish": 6000,
                "fish_roe": 12000,
                "fish_oil": 10000
            })
            
            for commodity_id, price in initial_prices.items():
                now = datetime.now()
                self.exchange_repo.add_exchange_price(Exchange(
                    date=today_str,
                    time=now.strftime("%H:%M:%S"),
                    commodity_id=commodity_id,
                    price=price,
                    update_type="manual",
                    created_at=now.isoformat()
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
        if self._price_update_task is None or self._price_update_task.done():
            self._price_update_task = asyncio.create_task(self._daily_price_update_loop())

    def stop_daily_price_update_task(self):
        """停止每日价格更新任务"""
        if self._price_update_task and not self._price_update_task.done():
            self._price_update_task.cancel()

    async def _daily_price_update_loop(self):
        """每日价格更新循环"""
        while True:
            try:
                # 等待到下一个更新时间
                now = datetime.now()
                next_update = self._get_next_update_time(now)
                wait_seconds = (next_update - now).total_seconds()
                
                if wait_seconds > 0:
                    logger.info(f"等待 {wait_seconds/3600:.1f} 小时后进行下次价格更新")
                    await asyncio.sleep(wait_seconds)
                
                # 更新价格（内部已有重复检查机制）
                logger.info("开始执行价格更新...")
                self.update_daily_prices()
                logger.info("价格更新完成")
                
            except asyncio.CancelledError:
                logger.info("价格更新任务被取消")
                break
            except Exception as e:
                # 记录错误但继续运行
                logger.error(f"交易所价格更新任务出错: {e}")
                await asyncio.sleep(3600)  # 出错后等待1小时再重试

    def _get_next_update_time(self, now: datetime) -> datetime:
        """获取下一个更新时间"""
        update_times = [9, 15, 21]  # 9点、15点、21点
        
        for hour in update_times:
            next_update = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if next_update > now:
                return next_update
        
        # 如果今天的所有更新时间都过了，返回明天的第一个更新时间
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=update_times[0], minute=0, second=0, microsecond=0)

    def update_daily_prices(self):
        """更新每日价格"""
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            # 检查今日是否已有价格更新
            existing_prices = self.exchange_repo.get_prices_for_date(today_str)
            if existing_prices:
                # 检查是否已经有今天的自动更新
                auto_updates = [p for p in existing_prices if p.update_type == "auto"]
                if auto_updates:
                    logger.info("今日价格已更新，跳过自动更新")
                    return
            
            # 获取昨日价格作为基础
            yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            last_prices = {p.commodity_id: p.price for p in self.exchange_repo.get_prices_for_date(yesterday_str)}
            
            if not last_prices:
                # 如果没有昨日价格，使用初始价格
                last_prices = self.config.get("initial_prices", {
                    "dried_fish": 6000,
                    "fish_roe": 12000,
                    "fish_oil": 10000
                })
                logger.info(f"基于初始价格更新：{last_prices}")
            else:
                logger.info(f"基于昨日价格更新：{last_prices}")

            # 如果没有商品数据，跳过价格更新
            if not self.commodities:
                return

            # 计算新价格
            new_prices = {}
            for commodity_id in self.commodities.keys():
                last_price = last_prices.get(commodity_id, self.config.get("initial_prices", {}).get(commodity_id, 100))
                new_price = self._calculate_new_price(commodity_id, last_price)
                new_prices[commodity_id] = new_price
                
                now = datetime.now()
                self.exchange_repo.add_exchange_price(Exchange(
                    date=today_str,
                    time=now.strftime("%H:%M:%S"),
                    commodity_id=commodity_id,
                    price=new_price,
                    update_type="auto",
                    created_at=now.isoformat()
                ))
            
            logger.info(f"价格更新完成，新价格：{new_prices}")

        except Exception as e:
            logger.error(f"更新每日价格失败: {e}")
