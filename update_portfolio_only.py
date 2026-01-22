#!/usr/bin/env python3
"""
快速生成持仓数据到market_data.json
"""
import json
import sys
sys.path.insert(0, '/home/kk/n8n')

from market_scanner import check_my_portfolio

if __name__ == "__main__":
    print("正在生成持仓数据...")
    portfolio_data = check_my_portfolio()
    
    # 读取现有的market_data.json
    try:
        with open('market_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        data = {}
    
    # 更新持仓数据
    data['my_portfolio'] = portfolio_data
    
    # 写回
    with open('market_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 持仓数据已更新到 market_data.json")
    print(f"   总计: {portfolio_data['summary']['total']} 只")
    print(f"   成功: {len(portfolio_data['stocks'])} 只")
    if portfolio_data['stocks']:
        for stock in portfolio_data['stocks']:
            print(f"   - {stock['name']}: {stock['status_text']} {stock['change_pct']:+.2f}%")
