import re
import socket
import os
import platform
import signal
import subprocess
import time

import aiohttp
import asyncio

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
            except aiohttp.ClientError as e:
                logger.warning(f"获取公网IP时请求 {api} 失败: {e}")
                continue

    return None

async def _is_port_available(port: int) -> bool:
    """异步检查端口是否可用，避免阻塞事件循环"""
    
    def check_sync():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False
            
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, check_sync)
    except Exception as e:
        logger.warning(f"检查端口 {port} 可用性时出错: {e}")
        return False

async def _get_pids_listening_on_port(port: int):
    """返回正在监听指定端口的进程PID列表。"""
    pids = set()
    system_name = platform.system().lower()

    try:
        if "windows" in system_name:
            # Windows: 尝试 netstat
            try:
                process = await asyncio.create_subprocess_exec(
                    "netstat", "-ano",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await process.communicate()
                result = stdout.decode(errors="ignore")
                
                for line in result.splitlines():
                    parts = line.split()
                    if len(parts) >= 5 and parts[0] in ("TCP", "UDP"):
                        local_addr = parts[1]
                        state = parts[3] if parts[0] == "TCP" else "LISTENING"
                        pid = parts[-1]
                        if f":{port}" in local_addr and state.upper() == "LISTENING" and pid.isdigit():
                            pids.add(int(pid))
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                logger.warning("netstat 不可用或执行失败")
        else:
            # Unix-like: 依次尝试多种方法
            methods = [
                # 方法1: lsof（常见但在容器中可能缺失）
                ("lsof", ["-i", f":{port}", "-sTCP:LISTEN", "-t"]),
                # 方法2: ss（更现代，通常可用）
                ("ss", ["-ltnp", f"sport = {port}"]),
                # 方法3: netstat（传统工具）
                ("netstat", ["-tlnp"])
            ]
            
            for i, (cmd, args) in enumerate(methods):
                try:
                    process = await asyncio.create_subprocess_exec(
                        cmd, *args,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, _ = await process.communicate()
                    result = stdout.decode(errors="ignore")
                    
                    if i == 0:  # lsof
                        for line in result.splitlines():
                            if line.strip().isdigit():
                                pids.add(int(line.strip()))
                        break
                    elif i == 1:  # ss
                        for line in result.splitlines():
                            if f":{port} " in line or line.strip().endswith(f":{port}"):
                                # 查找 pid=XXXX 或 users:(("进程名",pid=XXXX,fd=X))
                                pid_match = re.search(r'pid=(\d+)', line)
                                if pid_match:
                                    pids.add(int(pid_match.group(1)))
                        break
                    elif i == 2:  # netstat
                        for line in result.splitlines():
                            if f":{port} " in line and "LISTEN" in line:
                                parts = line.split()
                                if len(parts) >= 7 and "/" in parts[-1]:
                                    pid_str = parts[-1].split("/")[0]
                                    if pid_str.isdigit():
                                        pids.add(int(pid_str))
                        break
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                    continue
            

    except Exception as e:
        logger.warning(f"获取端口 {port} 占用进程时出错: {e}")

    # 排除当前进程，避免误杀自身
    current_pid = os.getpid()
    if current_pid in pids:
        pids.discard(current_pid)
    return list(pids)

async def kill_processes_on_port(port: int):
    """尝试终止监听指定端口的进程。返回 (success, killed_pids)。"""
    pids = await _get_pids_listening_on_port(port)
    if not pids:
        return True, []

    system_name = platform.system().lower()
    killed = []

    for pid in pids:
        try:
            if "windows" in system_name:
                # Windows: 使用 taskkill
                try:
                    process = await asyncio.create_subprocess_exec(
                        "taskkill", "/PID", str(pid), "/F",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await process.communicate()
                    killed.append(pid)
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    logger.warning(f"taskkill 不可用或超时，尝试直接终止进程 {pid}")
                    # 必要时可尝试其他方法
                    pass
            else:
                # Unix-like: 优雅终止 -> 强制终止
                success = False
                try:
                    os.kill(pid, signal.SIGTERM)
                    # 等待进程响应 SIGTERM
                    for _ in range(10):  # 1秒内检查
                        try:
                            os.kill(pid, 0)  # 检查进程是否存在
                            await asyncio.sleep(0.1)
                        except ProcessLookupError:
                            success = True
                            break
                    
                    if not success:
                        # 进程未响应，强制终止
                        os.kill(pid, signal.SIGKILL)
                    
                    killed.append(pid)
                except ProcessLookupError:
                    # 进程已不存在
                    killed.append(pid)
                except PermissionError:
                    logger.warning(f"权限不足，无法终止进程 {pid}")
                except Exception as e:
                    logger.warning(f"终止进程 {pid} 失败: {e}")
        except Exception as e:
            logger.warning(f"处理进程 {pid} 时出错: {e}")

    # 等待端口释放
    deadline = time.time() + 3
    while time.time() < deadline:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            sock.bind(("0.0.0.0", port))
            sock.close()
            return True, killed
        except Exception:
            await asyncio.sleep(0.2)
            continue

    return len(killed) > 0, killed  # 即使端口未释放，如果杀死了进程也算部分成功

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
        except ValueError as e:
            logger.error(f"Failed to format datetime: {time_input} with error: {e}")
            return None

    logger.error(f"Unsupported time input type: {type(time_input)}")
    # 无法处理的类型
    return None
