import re

file_path = '/home/kk/n8n/market_scanner.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to find the function block
pattern = r'(def get_hot_sectors_and_stocks\(top_n=8, stocks_per_sector=5\):.*?)(def load_my_stocks\(\):)'
replacement = r'''def get_hot_sectors_and_stocks(top_n=8, stocks_per_sector=5):
    """2. 获取热点板块及龙头 (基于精选概念池 + 实时资金流向排序)"""
    print(f"正在扫描主流热点赛道...")
    
    sector_performance = []
    
    # === 使用精选概念池进行全扫描 ===
    # 注意：不再依赖同花顺排榜，而是扫描所有我们关注的"高质量"板块
    for sector_key, codes in FALLBACK_HOT_STOCKS.items():
        # 获取该板块代表股的实时行情
        leading_stocks = get_stocks_realtime_sina(codes)
        
        if not leading_stocks:
            continue
            
        # 计算板块热度：代表股平均涨幅 + 领涨股涨幅
        avg_pct = sum(s['change_pct'] for s in leading_stocks) / len(leading_stocks)
        max_pct = max(s['change_pct'] for s in leading_stocks)
        
        # 简单热度分：平均涨幅*0.6 + 龙头涨幅*0.4
        heat_score = avg_pct * 0.6 + max_pct * 0.4
        
        # 只展示正收益或热度高的板块
        if heat_score > 0 or max_pct > 3:
            # 为每只股票增加技术指标分析（仅对前3只做，避免请求过多）
            for i, stock in enumerate(leading_stocks[:3]):
                try:
                    hist = ak.stock_zh_a_hist(symbol=stock['code'], period="daily", adjust="qfq")
                    tech = calculate_technical_indicators(hist)
                    if tech:
                        stock['technical'] = tech
                        # 如果没有趋势分，初始化
                        if stock.get('technical', {}).get('trend_score', 0) >= 3:
                             stock['recommendation'] = "🌟 强烈关注"
                        elif stock.get('technical', {}).get('trend_score', 0) >= 1:
                             stock['recommendation'] = "👀 观察"
                        else:
                             stock['recommendation'] = "✋ 观望"
                except:
                    pass
            
            sector_name = sector_key.split('/')[0]
            sector_performance.append({
                "name": sector_name,
                "change_pct": round(avg_pct, 2),
                "heat_score": heat_score,
                "leading_stocks": leading_stocks
            })
            print(f"  -> 扫描: {sector_name} (均涨{avg_pct:.2f}%, 龙头{max_pct:.2f}%)")
    
    # 按照热度排序
    sector_performance.sort(key=lambda x: x['heat_score'], reverse=True)
    
    # 去除重复或无效
    unique_sectors = []
    seen = set()
    for s in sector_performance:
        if s['name'] not in seen:
            unique_sectors.append(s)
            seen.add(s['name'])
    
    top_sectors = unique_sectors[:top_n]
    
    # 如果没有找到任何正向板块（极端行情），返回空
    if not top_sectors:
         top_sectors = [{
            "name": "全市场回调",
            "change_pct": 0,
            "leading_stocks": [],
            "data_status": "bear_market"
        }]
    
    return top_sectors

\g<2>'''

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

if new_content != content:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Update success")
else:
    print("Update failed - pattern not found")
