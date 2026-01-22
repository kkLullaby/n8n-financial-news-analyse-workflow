#!/usr/bin/env python3
"""
测试 market_scanner.py 的 check_my_portfolio 函数
"""
import sys
import json

# 导入market_scanner模块
sys.path.insert(0, '/home/kk/n8n')
from market_scanner import check_my_portfolio

if __name__ == "__main__":
    print("测试 check_my_portfolio() 函数...")
    print("="*60)
    
    result = check_my_portfolio()
    
    print("\n返回结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    print("\n" + "="*60)
    if result['stocks']:
        print(f"✅ 成功获取 {len(result['stocks'])} 只股票数据")
        for stock in result['stocks']:
            print(f"  - {stock['name']} ({stock['code']}): {stock['status_text']} {stock['change_pct']:+.2f}%")
    else:
        print(f"❌ 未能获取股票数据")
        if 'message' in result['summary']:
            print(f"   原因: {result['summary']['message']}")
