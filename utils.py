import re

import aiohttp


async def get_public_ip():
    """异步获取公网IPv4地址"""
    ipv4_apis = [
        'http://ipv4.ifconfig.me/ip',  # IPv4专用接口
        'http://api-ipv4.ip.sb/ip',  # 樱花云IPv4接口
        'http://v4.ident.me',  # IPv4专用
        'http://ip.qaros.com',  # 备用国内服务
        'http://ipv4.icanhazip.com',  # IPv4专用
        'http://4.icanhazip.com'  # 另一个变种地址
    ]

    async with aiohttp.ClientSession() as session:
        for api in ipv4_apis:
            try:
                async with session.get(api, timeout=5) as response:
                    if response.status == 200:
                        ip = (await response.text()).strip()
                        # 添加二次验证确保是IPv4格式
                        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                            return ip
            except:
                continue

    return None

# 将1.2等数字转换成百分数
def to_percentage(value: float) -> str:
    """将小数转换为百分比字符串"""
    if value is None:
        return "0%"
    return f"{(value - 1) * 100:.2f}%"

def format_accessory_or_rod(accessory_or_rod: dict) -> str:
    """格式化配件信息"""
    message =  f" - ID: {accessory_or_rod['instance_id']}\n"
    message += f" - {accessory_or_rod['name']} (稀有度: {'⭐' * accessory_or_rod['rarity']})\n"
    if accessory_or_rod.get('is_equipped', False):
        message += f"   - {'✅ 已装备'}\n"
    if accessory_or_rod.get('bonus_fish_quality_modifier', 1.0) != 1.0:
        message += f"   - ✨鱼类质量加成: {to_percentage(accessory_or_rod['bonus_fish_quality_modifier'])}\n"
    if accessory_or_rod.get('bonus_fish_quantity_modifier', 1.0) != 1.0:
        message += f"   - 📊鱼类数量加成: {to_percentage(accessory_or_rod['bonus_fish_quantity_modifier'])}\n"
    if accessory_or_rod.get('bonus_rare_fish_chance', 1.0) != 1.0:
        message += f"   - 🎣钓鱼几率加成: {to_percentage(accessory_or_rod['bonus_rare_fish_chance'])}\n"
    message += "\n"
    return message