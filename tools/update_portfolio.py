import re

file_path = '/home/kk/n8n/market_scanner.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

pattern = r'(def check_my_portfolio\(\):.*?)(# 新闻关键词配置 \(Pro增强版\))'
replacement = r'''def check_my_portfolio():
    """4. 持仓哨兵 (增强技术面分析)"""
    my_stocks = load_my_stocks() 
    print(f"正在巡查持仓 ({len(my_stocks)} 只)...")
    
    if not my_stocks:
        return {"stocks": [], "summary": {"message": "暂无持仓监控"}}

    # 改为使用新浪批量接口，速度更快且稳定
    realtime_data = get_stocks_realtime_sina(my_stocks)
    stock_map = {s['code']: s for s in realtime_data}
    
    portfolio_list = []
    up_count, down_count, flat_count = 0, 0, 0
    danger_alerts = []
    
    for code in my_stocks:
        try:
            # 基础数据
            stock_rt = stock_map.get(code, {})
            name = stock_rt.get('name', '未知')
            price = stock_rt.get('price', 0)
            pct = stock_rt.get('change_pct', 0)
            
            # 详细技术分析
            tech_analysis = {}
            advice = "持有"
            
            try:
                hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
                tech = calculate_technical_indicators(hist)
                if tech:
                    tech_analysis = tech
                    # 生成建议
                    score = tech['trend_score']
                    rsi = tech['rsi6']
                    
                    if score >= 4: advice = "坚定持有"
                    elif score <= -1: advice = "考虑减仓"
                    elif rsi > 85: advice = "高抛止盈"
                    elif rsi < 15: advice = "低吸补仓"
                    elif "放量上涨" in tech['signals']: advice = "加仓做T"
            except:
                pass

            item = {
                "name": name,
                "code": code,
                "price": price,
                "change_pct": pct,
                "technical": tech_analysis,
                "advice": advice
            }
            portfolio_list.append(item)
            
            if pct > 0: up_count += 1
            elif pct < 0: down_count += 1
            else: flat_count += 1
            
            if pct < -5 or (tech_analysis and tech_analysis.get('rsi6', 50) < 20):
                danger_alerts.append(f"{name} 处于弱势 ({pct}%)")
                
            print(f"  -> {code} {name}: {pct}% [{advice}]")
            
        except Exception as e:
            print(f"  -> {code} 分析失败: {e}")
            continue
            
    summary = {
        "total": len(my_stocks),
        "up_count": up_count, 
        "down_count": down_count,
        "danger_alerts": danger_alerts,
        "has_danger": len(danger_alerts) > 0,
        "strategy_suggestion": "持仓稳健" if up_count > down_count else "注意风险控制"
    }

    return {"stocks": portfolio_list, "summary": summary}

\g<2>'''

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)
print("Updated check_my_portfolio")
