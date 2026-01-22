#!/usr/bin/env python3
"""
测试持仓数据获取功能（使用备用方案）
"""
import akshare as ak
import time
import json

def load_my_stocks():
    """从 my_stocks.txt 加载股票代码"""
    try:
        with open('my_stocks.txt', 'r', encoding='utf-8') as f:
            codes = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        return codes
    except FileNotFoundError:
        return []

def test_portfolio():
    """测试持仓数据获取（双模式）"""
    my_stocks = load_my_stocks()
    
    print(f"📊 测试持仓数据获取 ({len(my_stocks)} 只)")
    print(f"股票代码: {my_stocks}\n")
    
    if not my_stocks:
        print("❌ my_stocks.txt 为空")
        return
    
    # 方案1: 尝试全市场数据
    print("方案1: 尝试获取全市场数据...")
    all_stocks = None
    for attempt in range(2):
        try:
            all_stocks = ak.stock_zh_a_spot_em()
            print(f"✅ 全市场数据获取成功 (共 {len(all_stocks)} 只股票)")
            break
        except Exception as e:
            print(f"❌ 尝试 {attempt+1}/2 失败: {str(e)[:50]}")
            if attempt < 1:
                time.sleep(1)
    
    # 方案2: 逐个查询
    if all_stocks is None:
        print("\n方案2: 切换到逐个查询模式...")
    
    results = []
    for code in my_stocks:
        print(f"\n查询 {code}:")
        try:
            if all_stocks is not None:
                # 从全市场数据中查找
                stock = all_stocks[all_stocks['代码'] == code]
                if stock.empty:
                    print(f"  ❌ 在全市场数据中未找到")
                    continue
                stock = stock.iloc[0]
                name = stock['名称']
                price = float(stock['最新价'])
                pct = float(stock['涨跌幅'])
                turnover = float(stock['换手率'])
                print(f"  ✅ {name}: ¥{price} ({pct:+.2f}%) 换手{turnover:.2f}%")
            else:
                # 逐个查询
                stock_info = ak.stock_individual_info_em(symbol=code)
                name = str(stock_info[stock_info['item'] == '股票简称']['value'].values[0])
                price = float(stock_info[stock_info['item'] == '最新']['value'].values[0])
                
                hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
                if len(hist) >= 2:
                    latest = hist.iloc[-1]
                    prev = hist.iloc[-2]
                    pct = round((float(latest['收盘']) - float(prev['收盘'])) / float(prev['收盘']) * 100, 2)
                    turnover = float(latest['换手率']) if '换手率' in latest else 0
                else:
                    pct = 0
                    turnover = 0
                
                print(f"  ✅ {name}: ¥{price} ({pct:+.2f}%) 换手{turnover:.2f}%")
            
            results.append({
                "code": code,
                "name": name,
                "price": price,
                "change_pct": pct,
                "turnover": turnover
            })
        
        except Exception as e:
            print(f"  ❌ 数据获取失败: {str(e)[:80]}")
    
    print("\n" + "="*50)
    print(f"📈 汇总: 成功获取 {len(results)}/{len(my_stocks)} 只股票")
    if results:
        print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    test_portfolio()
