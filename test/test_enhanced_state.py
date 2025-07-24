#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版用户状态面板测试文件
测试新增的功能：用户ID、称号、钓鱼统计、签到状态、擦弹剩余次数等
"""

import os
import sys
from datetime import datetime

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
plugin_dir = os.path.dirname(current_dir)
sys.path.insert(0, plugin_dir)

from draw.state import draw_state_image

def test_enhanced_state_panel():
    """测试增强版状态面板的所有新功能"""
    
    # 模拟完整的用户数据，包含所有新增字段
    test_user_data = {
        # 基本信息
        'user_id': '123456789',
        'nickname': '钓鱼大师',
        'coins': 1234567,
        
        # 装备信息
        'current_rod': {
            'name': '传说级黄金鱼竿',
            'rarity': 5,
            'refine_level': 10
        },
        'current_accessory': {
            'name': '神秘钓鱼徽章',
            'rarity': 4,
            'refine_level': 8
        },
        'current_bait': {
            'name': '史诗级万能鱼饵',
            'rarity': 4
        },
        
        # 钓鱼区域
        'fishing_zone': {
            'name': '神秘深海'
        },
        
        # 基本状态信息
        'auto_fishing_enabled': True,
        'steal_cooldown_remaining': 7320,  # 2小时2分钟
        
        # 新增：称号系统
        'current_title': {
            'id': 'legendary_fisher',
            'name': '传说渔夫'
        },
        
        # 新增：游戏统计
        'total_fishing_count': 15847,
        'steal_total_value': 2456789,
        
        # 新增：每日活动状态
        'signed_in_today': True,
        'wipe_bomb_remaining': 2
    }
    
    print("正在生成增强版用户状态面板...")
    
    try:
        # 生成状态图像
        image = draw_state_image(test_user_data)
        
        # 保存图像
        output_path = os.path.join(os.path.dirname(__file__), "test_outputs")
        os.makedirs(output_path, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"enhanced_state_panel_{timestamp}.png"
        full_path = os.path.join(output_path, filename)
        
        image.save(full_path, "PNG", quality=95)
        print(f"✅ 增强版状态面板已保存到: {full_path}")
        
        # 显示图像信息
        print(f"图像尺寸: {image.size}")
        print(f"图像模式: {image.mode}")
        
        return full_path
        
    except Exception as e:
        print(f"❌ 生成状态面板时出错: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_different_scenarios():
    """测试不同用户状态的显示效果"""
    
    scenarios = {
        "新手用户": {
            'user_id': '999999999',
            'nickname': '新手小鱼',
            'coins': 150,
            'current_rod': None,
            'current_accessory': None,
            'current_bait': None,
            'fishing_zone': {'name': '新手池塘'},
            'auto_fishing_enabled': False,
            'steal_cooldown_remaining': 0,
            'current_title': None,
            'total_fishing_count': 5,
            'steal_total_value': 0,
            'signed_in_today': False,
            'wipe_bomb_remaining': 3
        },
        
        "中级玩家": {
            'user_id': '555555555',
            'nickname': '进阶钓手',
            'coins': 45000,
            'current_rod': {
                'name': '精良银鱼竿',
                'rarity': 3,
                'refine_level': 5
            },
            'current_accessory': {
                'name': '幸运钓鱼帽',
                'rarity': 2,
                'refine_level': 3
            },
            'current_bait': {
                'name': '优质蚯蚓',
                'rarity': 2
            },
            'fishing_zone': {'name': '森林湖泊'},
            'auto_fishing_enabled': True,
            'steal_cooldown_remaining': 1800,  # 30分钟
            'current_title': {
                'name': '熟练钓手'
            },
            'total_fishing_count': 1250,
            'steal_total_value': 125000,
            'signed_in_today': True,
            'wipe_bomb_remaining': 1
        },
        
        "资深玩家": {
            'user_id': '111111111',
            'nickname': '钓鱼宗师',
            'coins': 9999999,
            'current_rod': {
                'name': '神器·海皇三叉戟',
                'rarity': 6,
                'refine_level': 15
            },
            'current_accessory': {
                'name': '神话级渔夫勋章',
                'rarity': 6,
                'refine_level': 12
            },
            'current_bait': {
                'name': '传说级龙血鱼饵',
                'rarity': 5
            },
            'fishing_zone': {'name': '远古深渊'},
            'auto_fishing_enabled': True,
            'steal_cooldown_remaining': 0,
            'current_title': {
                'name': '深渊征服者'
            },
            'total_fishing_count': 99999,
            'steal_total_value': 99999999,
            'signed_in_today': True,
            'wipe_bomb_remaining': 0  # 已用完
        }
    }
    
    output_paths = []
    
    for scenario_name, user_data in scenarios.items():
        print(f"\n正在生成 '{scenario_name}' 场景的状态面板...")
        
        try:
            image = draw_state_image(user_data)
            
            output_path = os.path.join(os.path.dirname(__file__), "test_outputs")
            os.makedirs(output_path, exist_ok=True)
            
            filename = f"scenario_{scenario_name.replace(' ', '_')}.png"
            full_path = os.path.join(output_path, filename)
            
            image.save(full_path, "PNG", quality=95)
            print(f"✅ '{scenario_name}' 场景已保存到: {full_path}")
            output_paths.append(full_path)
            
        except Exception as e:
            print(f"❌ 生成 '{scenario_name}' 场景时出错: {e}")
    
    return output_paths

if __name__ == "__main__":
    print("🎣 AstrBot 钓鱼插件 - 增强版状态面板测试")
    print("=" * 50)
    
    # 测试完整功能的状态面板
    print("\n1. 测试完整功能的状态面板")
    main_result = test_enhanced_state_panel()
    
    # 测试不同场景
    print("\n2. 测试不同用户状态场景")
    scenario_results = test_different_scenarios()
    
    print("\n" + "=" * 50)
    print("🎉 测试完成！")
    
    if main_result:
        print(f"主要测试图像: {main_result}")
    
    if scenario_results:
        print("场景测试图像:")
        for path in scenario_results:
            print(f"  - {path}")
    
    print("\n📝 新功能说明:")
    print("✨ 用户ID和称号显示")
    print("📊 总钓鱼次数和偷鱼总价值统计")
    print("📅 每日签到状态显示")
    print("🎯 擦弹剩余次数显示")
    print("🎨 重新设计的两列装备布局")
    print("📐 优化对齐和美观性")
