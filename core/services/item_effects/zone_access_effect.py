import json
from typing import Dict, Any
from .abstract_effect import AbstractItemEffect


class ZoneAccessEffect(AbstractItemEffect):
    """区域访问效果 - 直接切换到指定钓鱼区域"""
    
    def __init__(self, dependencies: Dict[str, Any]):
        super().__init__(dependencies)
        self.fishing_service = dependencies.get("fishing_service")
    
    def get_effect_type(self) -> str:
        return "ZONE_ACCESS"
    
    def apply_effect(self, user_id: str, effect_payload: str) -> Dict[str, Any]:
        """
        应用区域访问效果 - 使用通行证直接传送到对应区域
        
        Args:
            user_id: 用户ID
            effect_payload: 效果载荷，包含zone_id
            
        Returns:
            应用结果
        """
        try:
            payload = json.loads(effect_payload)
            zone_id = payload.get("zone_id")
            
            if not zone_id:
                return {
                    "success": False,
                    "message": "区域ID无效"
                }
            
            # 获取区域信息
            zone = self.fishing_service.inventory_repo.get_zone_by_id(zone_id)
            if not zone:
                return {
                    "success": False,
                    "message": "目标区域不存在"
                }
            
            # 检查区域是否激活
            if not zone.is_active:
                return {
                    "success": False,
                    "message": "该钓鱼区域暂未开放"
                }
            
            # 检查时间限制
            from ..utils import get_now
            now = get_now()
            if zone.available_from and now < zone.available_from:
                return {
                    "success": False,
                    "message": f"该钓鱼区域将在 {zone.available_from.strftime('%Y-%m-%d %H:%M')} 开放"
                }
            
            if zone.available_until and now > zone.available_until:
                return {
                    "success": False,
                    "message": f"该钓鱼区域已于 {zone.available_until.strftime('%Y-%m-%d %H:%M')} 关闭"
                }
            
            # 直接设置用户区域（绕过道具检查，因为已经使用了通行证）
            user = self.fishing_service.user_repo.get_by_id(user_id)
            if not user:
                return {
                    "success": False,
                    "message": "用户不存在"
                }
            
            user.fishing_zone_id = zone_id
            self.fishing_service.user_repo.update(user)
            
            # 记录日志
            self.fishing_service.log_repo.add_log(user_id, "zone_entry", f"使用通行证进入 {zone.name}")
            
            return {
                "success": True,
                "message": f"🎫 使用通行证成功传送到 {zone.name}！"
            }
                
        except json.JSONDecodeError:
            return {
                "success": False,
                "message": "效果配置无效"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"应用效果时出错：{str(e)}"
            }
