"""
红包业务逻辑服务层
"""

import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from astrbot.api import logger

from ..domain.models import RedPacket, RedPacketRecord
from ..repositories.sqlite_red_packet_repo import SqliteRedPacketRepository
from ..repositories.sqlite_user_repo import SqliteUserRepository


class RedPacketService:
    """红包服务"""

    def __init__(self, red_packet_repo: SqliteRedPacketRepository, user_repo: SqliteUserRepository):
        self.red_packet_repo = red_packet_repo
        self.user_repo = user_repo
        self.min_amount = 100  # 最低发红包金额
        self.max_packet_count = 200  # 最多红包个数
        self.expire_hours = 24  # 红包过期时间（小时）

    def send_red_packet(
        self, 
        sender_id: str, 
        group_id: str, 
        packet_type: str, 
        amount_per_packet: int, 
        count: int = 1,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送红包
        
        Args:
            sender_id: 发送者ID
            group_id: 群组ID
            packet_type: 红包类型 ('normal', 'lucky', 'password')
            amount_per_packet: 单个红包金额（普通/口令）或总金额（拼手气）
            count: 红包数量
            password: 口令（口令红包必填）
        """
        # 验证红包类型
        if packet_type not in ['normal', 'lucky', 'password']:
            return {"success": False, "message": "❌ 无效的红包类型"}
        
        # 验证口令红包必须有口令
        if packet_type == 'password' and not password:
            return {"success": False, "message": "❌ 口令红包必须设置口令"}
        
        # 验证金额
        if amount_per_packet < self.min_amount:
            return {"success": False, "message": f"❌ 红包金额不能低于 {self.min_amount} 金币"}
        
        # 验证数量
        if count < 1:
            return {"success": False, "message": "❌ 红包数量至少为1个"}
        
        if count > self.max_packet_count:
            return {"success": False, "message": f"❌ 红包数量不能超过 {self.max_packet_count} 个"}
        
        # 计算总金额
        if packet_type in ['normal', 'password']:
            # 普通红包和口令红包：amount_per_packet 是单个红包金额
            total_amount = amount_per_packet * count
        else:
            # 拼手气红包：amount_per_packet 是总金额
            total_amount = amount_per_packet
            # 验证总金额至少要能给每个红包分1金币
            if total_amount < count:
                return {"success": False, "message": f"❌ 拼手气红包总金额必须 ≥ 红包数量（每个至少1金币）"}
        
        # 检查发送者余额
        sender = self.user_repo.get_by_id(sender_id)
        if not sender:
            return {"success": False, "message": "❌ 用户不存在"}
        
        if not sender.can_afford(total_amount):
            return {"success": False, "message": f"❌ 余额不足！需要 {total_amount:,} 金币，当前拥有 {sender.coins:,} 金币"}
        
        # 扣除发送者金币
        sender.coins -= total_amount
        self.user_repo.update(sender)
        
        # 创建红包
        now = datetime.now()
        expires_at = now + timedelta(hours=self.expire_hours)
        
        packet = RedPacket(
            packet_id=0,  # 将由数据库自动生成
            sender_id=sender_id,
            group_id=group_id,
            packet_type=packet_type,
            total_amount=total_amount,
            total_count=count,
            remaining_amount=total_amount,
            remaining_count=count,
            password=password,
            created_at=now,
            expires_at=expires_at,
            is_expired=False
        )
        
        packet_id = self.red_packet_repo.create_red_packet(packet)
        packet.packet_id = packet_id
        
        # 构建返回消息
        type_name = {
            'normal': '普通红包',
            'lucky': '拼手气红包',
            'password': '口令红包'
        }.get(packet_type, '红包')
        
        message = f"🧧 {type_name}发送成功！\n"
        message += f"🆔 红包ID：{packet_id}\n"
        message += f"💰 总金额：{total_amount:,} 金币\n"
        message += f"📦 红包数量：{count} 个\n"
        
        if packet_type == 'normal':
            per_amount = amount_per_packet
            message += f"💵 每个红包：{per_amount:,} 金币\n"
        elif packet_type == 'password':
            per_amount = amount_per_packet
            message += f"💵 每个红包：{per_amount:,} 金币\n"
            message += f"🔑 口令：{password}\n"
        elif packet_type == 'lucky':
            message += f"💰 总额：{total_amount:,} 金币（随机分配）\n"
        
        message += f"⏰ 有效期：{self.expire_hours}小时\n"
        message += f"📝 使用 /领红包 {packet_id} 或 /抢红包 {packet_id} 来领取"
        
        if packet_type == 'password':
            message += f"\n💡 口令红包需要发送：/领红包 {packet_id} {password}"
        
        logger.info(f"用户 {sender_id} 在群 {group_id} 发送了{type_name}，ID: {packet_id}")
        
        return {
            "success": True,
            "message": message,
            "packet_id": packet_id
        }

    def claim_red_packet(
        self, 
        user_id: str, 
        group_id: str,
        packet_id: Optional[int] = None,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        领取红包
        
        Args:
            user_id: 领取者ID
            group_id: 群组ID
            packet_id: 红包ID（可选，指定领取哪个红包）
            password: 口令（用于口令红包）
        """
        # 先过期旧红包
        self.red_packet_repo.expire_old_packets(datetime.now())
        
        # 如果指定了红包ID，直接获取该红包
        if packet_id is not None:
            packet = self.red_packet_repo.get_red_packet_by_id(packet_id)
            if not packet:
                return {"success": False, "message": f"❌ 红包 #{packet_id} 不存在"}
            
            if packet.group_id != group_id:
                return {"success": False, "message": "❌ 该红包不属于当前群组"}
            
            if packet.is_expired:
                return {"success": False, "message": "❌ 该红包已过期"}
            
            if packet.remaining_count == 0:
                return {"success": False, "message": "❌ 该红包已被抢光"}
            
            # 口令红包验证
            if packet.packet_type == 'password':
                if not password or password != packet.password:
                    return {"success": False, "message": f"❌ 口令错误！请使用：/领红包 {packet_id} {packet.password}"}
        else:
            # 没有指定ID，获取群组中的活跃红包
            active_packets = self.red_packet_repo.get_active_red_packets_in_group(group_id)
            
            if not active_packets:
                return {"success": False, "message": "❌ 当前没有可领取的红包"}
            
            # 如果提供了口令，优先匹配口令红包
            if password:
                password_packets = [p for p in active_packets if p.packet_type == 'password' and p.password == password]
                if password_packets:
                    packet = password_packets[0]
                else:
                    return {"success": False, "message": "❌ 口令错误或没有匹配的口令红包"}
            else:
                # 没有口令则领取最新的非口令红包
                non_password_packets = [p for p in active_packets if p.packet_type != 'password']
                if not non_password_packets:
                    return {"success": False, "message": "❌ 当前只有口令红包，请使用：/领红包 [红包ID] [口令]"}
                packet = non_password_packets[0]
        
        # 检查是否已领取
        if self.red_packet_repo.has_user_claimed(packet.packet_id, user_id):
            return {"success": False, "message": f"❌ 你已经领取过红包 #{packet.packet_id} 了"}
        
        # 计算领取金额
        amount = self._calculate_claim_amount(packet)
        
        # 更新红包状态
        packet.remaining_amount -= amount
        packet.remaining_count -= 1
        if packet.remaining_count == 0:
            packet.is_expired = True
        
        self.red_packet_repo.update_red_packet(packet)
        
        # 创建领取记录
        record = RedPacketRecord(
            record_id=0,
            packet_id=packet.packet_id,
            user_id=user_id,
            amount=amount,
            claimed_at=datetime.now()
        )
        self.red_packet_repo.create_claim_record(record)
        
        # 给用户加金币
        user = self.user_repo.get_by_id(user_id)
        if user:
            user.coins += amount
            self.user_repo.update(user)
        
        # 构建返回消息
        type_name = {
            'normal': '普通红包',
            'lucky': '拼手气红包',
            'password': '口令红包'
        }.get(packet.packet_type, '红包')
        
        message = f"🎉 领取成功！\n"
        message += f"💰 获得：{amount:,} 金币\n"
        message += f"🧧 类型：{type_name}\n"
        message += f"📦 剩余：{packet.remaining_count}/{packet.total_count}\n"
        
        if packet.remaining_count == 0:
            message += "\n🎊 红包已被抢光！"
        
        logger.info(f"用户 {user_id} 领取了红包 {packet.packet_id}，获得 {amount} 金币")
        
        return {
            "success": True,
            "message": message,
            "amount": amount,
            "packet_id": packet.packet_id
        }

    def _calculate_claim_amount(self, packet: RedPacket) -> int:
        """计算领取金额"""
        if packet.packet_type in ['normal', 'password']:
            # 普通红包和口令红包：平均分配（总金额 / 总数量）
            return packet.total_amount // packet.total_count
        
        elif packet.packet_type == 'lucky':
            # 拼手气红包：随机分配
            if packet.remaining_count == 1:
                # 最后一个红包，把剩余的都给
                return packet.remaining_amount
            
            # 不是最后一个，随机分配
            # 保证剩余的红包每个至少有1金币
            max_amount = packet.remaining_amount - (packet.remaining_count - 1)
            if max_amount < 1:
                max_amount = 1
            
            # 随机金额，至少1金币
            amount = random.randint(1, max_amount)
            return amount
        
        return 0

    def get_red_packet_details(self, packet_id: int) -> Dict[str, Any]:
        """获取红包详情"""
        packet = self.red_packet_repo.get_red_packet_by_id(packet_id)
        if not packet:
            return {"success": False, "message": "❌ 红包不存在"}
        
        records = self.red_packet_repo.get_claim_records_by_packet(packet_id)
        
        type_name = {
            'normal': '普通红包',
            'lucky': '拼手气红包',
            'password': '口令红包'
        }.get(packet.packet_type, '红包')
        
        # 获取发送者昵称
        sender = self.user_repo.get_by_id(packet.sender_id)
        sender_name = sender.nickname if sender and sender.nickname else packet.sender_id
        
        message = f"🧧 红包详情\n"
        message += f"👤 发送者：{sender_name}\n"
        message += f"🎁 类型：{type_name}\n"
        message += f"💰 总金额：{packet.total_amount:,} 金币\n"
        message += f"📦 总数量：{packet.total_count} 个\n"
        message += f"✅ 已领取：{len(records)}/{packet.total_count}\n"
        message += f"💵 剩余金额：{packet.remaining_amount:,} 金币\n"
        
        if packet.packet_type == 'password':
            message += f"🔑 口令：{packet.password}\n"
        
        message += f"⏰ 创建时间：{packet.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        if packet.is_expired:
            message += "❌ 状态：已过期\n"
        elif packet.remaining_count == 0:
            message += "✅ 状态：已抢完\n"
        else:
            message += "🟢 状态：进行中\n"
        
        if records:
            message += "\n📋 领取记录：\n"
            for idx, record in enumerate(records[:10], 1):
                claimer = self.user_repo.get_by_id(record.user_id)
                claimer_name = claimer.nickname if claimer and claimer.nickname else record.user_id
                message += f"{idx}. {claimer_name}：{record.amount:,} 金币\n"
            
            if len(records) > 10:
                message += f"... 还有 {len(records) - 10} 条记录\n"
        
        return {
            "success": True,
            "message": message,
            "packet": packet,
            "records": records
        }

    def list_group_red_packets(self, group_id: str) -> Dict[str, Any]:
        """列出群组中可领取的红包"""
        packets = self.red_packet_repo.get_active_red_packets_in_group(group_id)
        
        if not packets:
            return {
                "success": True,
                "message": "📭 当前群组暂无可领取的红包"
            }
        
        message = f"🧧 本群可领取红包列表（共 {len(packets)} 个）\n\n"
        
        for packet in packets:
            # 获取发送者昵称
            sender = self.user_repo.get_by_id(packet.sender_id)
            sender_name = sender.nickname if sender and sender.nickname else packet.sender_id[:8]
            
            # 红包类型图标
            type_icon = {
                'normal': '💰',
                'lucky': '🎲',
                'password': '🔐'
            }.get(packet.packet_type, '🧧')
            
            # 红包类型名称
            type_name = {
                'normal': '普通',
                'lucky': '拼手气',
                'password': '口令'
            }.get(packet.packet_type, '红包')
            
            # 计算已领取进度
            claimed_count = packet.total_count - packet.remaining_count
            progress_percent = (claimed_count / packet.total_count * 100) if packet.total_count > 0 else 0
            
            message += f"【ID:{packet.packet_id}】{type_icon} {type_name}红包\n"
            message += f"├ 发送者：{sender_name}\n"
            message += f"├ 剩余：{packet.remaining_count}/{packet.total_count} 个\n"
            message += f"├ 金额：{packet.remaining_amount:,}/{packet.total_amount:,} 币\n"
            message += f"├ 进度：{'█' * int(progress_percent // 10)}{'░' * (10 - int(progress_percent // 10))} {progress_percent:.0f}%\n"
            
            # 显示口令提示
            if packet.packet_type == 'password':
                message += f"├ 口令：{packet.password}\n"
            
            # 计算剩余时间
            now = datetime.now()
            time_left = packet.expires_at - now
            hours_left = time_left.total_seconds() / 3600
            
            if hours_left > 1:
                message += f"└ 剩余：{hours_left:.1f}小时\n"
            else:
                minutes_left = time_left.total_seconds() / 60
                message += f"└ 剩余：{minutes_left:.0f}分钟\n"
            
            message += "\n"
        
        message += "💡 使用 /领红包 [ID] 来领取指定红包\n"
        if any(p.packet_type == 'password' for p in packets):
            message += "💡 口令红包：/领红包 [ID] [口令]"
        
        return {"success": True, "message": message}

    def revoke_red_packet(self, packet_id: int, user_id: str, is_admin: bool = False) -> Dict[str, Any]:
        """
        撤回红包（退还未领取的金额）
        
        Args:
            packet_id: 红包ID
            user_id: 操作者ID
            is_admin: 是否为管理员
        """
        packet = self.red_packet_repo.get_red_packet_by_id(packet_id)
        if not packet:
            return {"success": False, "message": "❌ 红包不存在"}
        
        # 权限检查：必须是发送者或管理员
        if user_id != packet.sender_id and not is_admin:
            return {"success": False, "message": "❌ 只有红包发送者或管理员才能撤回红包"}
        
        # 检查红包状态
        if packet.is_expired:
            return {"success": False, "message": "❌ 红包已过期，无法撤回"}
        
        if packet.remaining_count == 0:
            return {"success": False, "message": "❌ 红包已全部领取完毕，无法撤回"}
        
        # 计算退还金额
        refund_amount = packet.remaining_amount
        claimed_count = packet.total_count - packet.remaining_count
        
        # 标记红包为已过期
        packet.is_expired = True
        packet.remaining_count = 0
        packet.remaining_amount = 0
        self.red_packet_repo.update_red_packet(packet)
        
        # 退还金额给发送者
        sender = self.user_repo.get_by_id(packet.sender_id)
        if sender:
            sender.coins += refund_amount
            self.user_repo.update(sender)
        
        type_name = {
            'normal': '普通红包',
            'lucky': '拼手气红包',
            'password': '口令红包'
        }.get(packet.packet_type, '红包')
        
        message = f"✅ 红包撤回成功！\n"
        message += f"🆔 红包ID：{packet_id}\n"
        message += f"🎁 类型：{type_name}\n"
        message += f"💰 退还金额：{refund_amount:,} 金币\n"
        message += f"✅ 已领取：{claimed_count}/{packet.total_count}\n"
        
        logger.info(f"用户 {user_id} 撤回了红包 {packet_id}，退还 {refund_amount} 金币给 {packet.sender_id}")
        
        return {
            "success": True,
            "message": message,
            "refund_amount": refund_amount
        }

    def clean_group_red_packets(self, group_id: str) -> Dict[str, Any]:
        """
        清理指定群组的红包（撤回未领完的，删除所有记录）
        
        Args:
            group_id: 群组ID
        """
        # 1. 先撤回所有未领完的红包并退款
        refund_count, refund_amount, packets_info = self.red_packet_repo.revoke_group_red_packets(group_id)
        
        # 退款给发送者
        refund_details = {}
        for packet_id, sender_id, amount in packets_info:
            sender = self.user_repo.get_by_id(sender_id)
            if sender:
                sender.coins += amount
                self.user_repo.update(sender)
                refund_details[sender_id] = refund_details.get(sender_id, 0) + amount
        
        # 2. 删除所有红包记录
        deleted_count = self.red_packet_repo.delete_group_red_packets(group_id)
        
        message = f"✅ 群组红包清理完成！\n"
        message += f"📦 退还红包：{refund_count} 个\n"
        message += f"💰 退还总额：{refund_amount:,} 金币\n"
        message += f"🗑️ 删除记录：{deleted_count} 个\n"
        
        if refund_details:
            message += f"\n💵 退款明细：\n"
            for sender_id, amount in list(refund_details.items())[:5]:
                sender = self.user_repo.get_by_id(sender_id)
                name = sender.nickname if sender and sender.nickname else sender_id
                message += f"  • {name}：{amount:,} 金币\n"
            if len(refund_details) > 5:
                message += f"  • ... 还有 {len(refund_details) - 5} 人\n"
        
        logger.info(f"清理了群 {group_id} 的 {deleted_count} 个红包记录，退还 {refund_amount} 金币")
        
        return {
            "success": True,
            "message": message,
            "deleted_count": deleted_count,
            "refund_amount": refund_amount
        }

    def clean_all_red_packets(self) -> Dict[str, Any]:
        """
        清理所有红包（撤回未领完的，删除所有记录）
        """
        # 1. 先撤回所有未领完的红包并退款
        refund_count, refund_amount, packets_info = self.red_packet_repo.revoke_all_red_packets()
        
        # 退款给发送者
        refund_details = {}
        for packet_id, sender_id, amount in packets_info:
            sender = self.user_repo.get_by_id(sender_id)
            if sender:
                sender.coins += amount
                self.user_repo.update(sender)
                refund_details[sender_id] = refund_details.get(sender_id, 0) + amount
        
        # 2. 删除所有红包记录
        deleted_count = self.red_packet_repo.delete_all_red_packets()
        
        message = f"✅ 全局红包清理完成！\n"
        message += f"📦 退还红包：{refund_count} 个\n"
        message += f"💰 退还总额：{refund_amount:,} 金币\n"
        message += f"🗑️ 删除记录：{deleted_count} 个\n"
        
        if refund_details:
            message += f"\n💵 退款明细：\n"
            for sender_id, amount in list(refund_details.items())[:10]:
                sender = self.user_repo.get_by_id(sender_id)
                name = sender.nickname if sender and sender.nickname else sender_id
                message += f"  • {name}：{amount:,} 金币\n"
            if len(refund_details) > 10:
                message += f"  • ... 还有 {len(refund_details) - 10} 人\n"
        
        logger.info(f"清理了所有 {deleted_count} 个红包记录，退还 {refund_amount} 金币")
        
        return {
            "success": True,
            "message": message,
            "deleted_count": deleted_count,
            "refund_amount": refund_amount
        }

    def cleanup_expired_packets(self) -> int:
        """
        清理所有过期红包
        返回清理数量
        """
        result = self.red_packet_repo.cleanup_expired_red_packets()
        return result

    def cleanup_group_packets(self, group_id: str) -> int:
        """
        清理指定群组的所有红包
        返回清理数量
        """
        result = self.clean_group_red_packets(group_id)
        return result.get("deleted_count", 0)
