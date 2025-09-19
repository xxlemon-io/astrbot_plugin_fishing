import re
import socket

import aiohttp

from astrbot.api import logger

async def get_public_ip():
    """异步获取公网IPv4地址"""
    ipv4_apis = [
        "http://ipv4.ifconfig.me/ip",  # IPv4专用接口
        "http://api-ipv4.ip.sb/ip",  # 樱花云IPv4接口
        "http://v4.ident.me",  # IPv4专用
        "http://ip.qaros.com",  # 备用国内服务
        "http://ipv4.icanhazip.com",  # IPv4专用
        "http://4.icanhazip.com"  # 另一个变种地址
    ]

    async with aiohttp.ClientSession() as session:
        for api in ipv4_apis:
            try:
                async with session.get(api, timeout=5) as response:
                    if response.status == 200:
                        ip = (await response.text()).strip()
                        # 添加二次验证确保是IPv4格式
                        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
                            return ip
            except:  # noqa: E722
                continue

    return None

async def _is_port_available(port):
    """检查端口是否可用"""
    try:
        # 尝试绑定到指定端口
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.bind(('0.0.0.0', port))
        sock.close()
        return True
    except:
        return False

# 将1.2等数字转换成百分数
def to_percentage(value: float) -> str:
    """将小数转换为百分比字符串"""
    if value is None:
        return "0%"
    if value < 1:
        return f"{value * 100:.2f}%"
    else:
        return f"{(value - 1) * 100:.2f}%"

def format_rarity_display(rarity: int) -> str:
    """格式化稀有度显示，支持显示到10星，10星以上显示为⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐+"""
    if rarity <= 10:
        return '⭐' * rarity
    else:
        return '⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐+'

def format_accessory_or_rod(accessory_or_rod: dict) -> str:
    """格式化配件信息"""
    message =  f" - ID: {accessory_or_rod['instance_id']}\n"
    message += f" - {accessory_or_rod['name']} (稀有度: {format_rarity_display(accessory_or_rod['rarity'])})\n"
    if accessory_or_rod.get("is_equipped", False):
        message += f"   - {'✅ 已装备'}\n"
    if accessory_or_rod.get("bonus_fish_quality_modifier", 1.0) != 1.0 and accessory_or_rod.get("bonus_fish_quality_modifier", 1) != 1 and accessory_or_rod.get("bonus_fish_quality_modifier", 1) > 0:
        message += f"   - ✨鱼类质量加成: {to_percentage(accessory_or_rod['bonus_fish_quality_modifier'])}\n"
    if accessory_or_rod.get("bonus_fish_quantity_modifier", 1.0) != 1.0 and accessory_or_rod.get("bonus_fish_quantity_modifier", 1) != 1 and accessory_or_rod.get("bonus_fish_quantity_modifier", 1) > 0:
        message += f"   - 📊鱼类数量加成: {to_percentage(accessory_or_rod['bonus_fish_quantity_modifier'])}\n"
    if accessory_or_rod.get("bonus_rare_fish_chance", 1.0) != 1.0 and accessory_or_rod.get("bonus_rare_fish_chance", 1) != 1 and accessory_or_rod.get("bonus_rare_fish_chance", 1) > 0:
        message += f"   - 🎣钓鱼几率加成: {to_percentage(accessory_or_rod['bonus_rare_fish_chance'])}\n"
    if accessory_or_rod.get("description"):
        message += f"   - 📋描述: {accessory_or_rod['description']}\n"
    message += "\n"
    return message

from datetime import datetime, timezone, timedelta  # noqa: E402
from typing import Union, Optional  # noqa: E402

def safe_datetime_handler(
    time_input: Union[str, datetime, None],
    output_format: str = "%Y-%m-%d %H:%M:%S",
    default_timezone: Optional[timezone] = None
) -> Union[str, datetime, None]:
    """
    安全处理各种时间格式，支持字符串与datetime互转

    参数:
        time_input: 输入的时间（字符串、datetime对象或None）
        output_format: 输出的时间格式字符串（默认：'%Y-%m-%d %H:%M:%S'）
        default_timezone: 默认时区，如果输入没有时区信息（默认：None）

    返回:
        根据输入类型:
        - 如果输入是字符串: 返回转换后的datetime对象
        - 如果输入是datetime: 返回格式化后的字符串
        - 出错或None: 返回None
    """
    # 处理空输入
    # logger.info(f"Processing time input: {time_input}")
    if time_input is None:
        logger.warning("Received None as time input, returning None.")
        return None

    # 获取默认时区
    if default_timezone is None:
        default_timezone = timezone(timedelta(hours=8))  # 默认东八区

    # 字符串转datetime
    if isinstance(time_input, str):
        try:
            # 尝试ISO格式解析
            dt = datetime.fromisoformat(time_input)
        except ValueError:
            # 尝试常见格式
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S"
            ]

            for fmt in formats:
                try:
                    dt = datetime.strptime(time_input, fmt)
                    # 添加默认时区
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=default_timezone)
                    break
                except ValueError:
                    continue
            else:
                # 所有格式都失败
                return None
        return dt.strftime(output_format)

    # datetime转字符串
    elif isinstance(time_input, datetime):
        try:
            # 确保有时区信息
            if time_input.tzinfo is None:
                time_input = time_input.replace(tzinfo=default_timezone)
            logger.info(f"Formatting datetime: {time_input}")
            return time_input.strftime(output_format)
        except Exception:
            logger.error(f"Failed to format datetime: {time_input}")
            return None

    logger.error(f"Unsupported time input type: {type(time_input)}")
    # 无法处理的类型
    return None
