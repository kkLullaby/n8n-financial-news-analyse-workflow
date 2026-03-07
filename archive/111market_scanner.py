import sys
import os
import json
import time
import datetime
import pandas as pd
import akshare as ak
import requests

# ==========================================
# 🚑 基础配置
# ==========================================
OUTPUT_FILE = "/home/kk/n8n/market_data.json"
HISTORY_FILE = "/home/kk/n8n/history_data.csv"
STOCK_FILE = "/home/kk/n8n/my_stocks.txt"

# 强力反爬设置
os.environ['NO_PROXY'] = '*'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.eastmoney.com/'
}

# 🎯 你的核心关注池 (保留，但只有涨的时候才推)
TECH_POLICY_POOL = {
    "AI算力": ["300308", "000977", "603083", "600941"],
    "低空经济": ["002085", "688220", "002985", "002313"],
    "固态电池": ["300750", "002460", "688063"],
    "人形机器人": ["300024", "002527", "300775"],
    "半导体": ["688981", "300661", "688012"],
    "量子科技": ["600522", "688027", "300077"]
}

# ==========================================
# 🚀 核心：上帝视角数据源 (God Mode)
# ==========================================
GLOBAL_MARKET_MAP = {}

def load_global_market_data():
    """一次性拉取全市场实时数据（含涨幅、量比、换手率）"""
    print("⏳ 正在建立全市场上帝视角 (拉取量比/换手)...")
    try:
        # 东财实时数据，包含：代码,名称,最新价,涨跌幅,量比,换手率
        df = ak.stock_zh_a_spot_em()
        
        for _, row in df.iterrows():
            code = str(row['代码'])
            # 建立全局字典，方便毫秒级查询
            GLOBAL_MARKET_MAP[code] = {
                "name": row['名称'],
                "price": row['最新价'],
                "change_pct": row['涨跌幅'],
                "volume_ratio": row['量比'],   # 真实的量比！
                "turnover": row['换手率'],      # 真实的换手！
                "amount": row['成交额']
            }
        print(f"✅ 全市场数据加载完毕，覆盖 {len(GLOBAL_MARKET_MAP)} 只股票")
        return True
    except Exception as e:
        print(f"❌ 全市场数据拉取失败: {e}")
        return False

def get_real_data(code):
    """从上帝视角获取单只股票数据"""
    # 兼容带前缀的代码
    clean_code = code
    if code.startswith('sh') or code.startswith('sz') or code.startswith('bj'):
        clean_code = code[2:]
    
    return GLOBAL_MARKET_MAP.get(clean_code, None)

# ==========================================
# 🛠️ 逻辑处理
# ==========================================

def analyze_sector(name, codes, source_type="user_pool"):
    """分析单个板块，返回清洗后的数据"""
    stocks = []
    
    for code in codes:
        data = get_real_data(code)
        if not data: continue
        
        # 排除停牌或无数据
        if data['price'] == '-' or data['price'] is None: continue
        
        # 狙击评级逻辑 (Python硬核计算)
        stars = "⭐⭐"
        advice = "观察"
        reason = "跟随"
        
        pct = float(data['change_pct'])
        vr = float(data['volume_ratio']) if data['volume_ratio'] != '-' else 1.0
        tr = float(data['turnover']) if data['turnover'] != '-' else 0.0
        
        if pct >= 9.8:
            stars = "⭐⭐⭐⭐⭐"
            advice = "龙头封板，排队"
            reason = "涨停确认"
        elif pct > 5 and vr > 2:
            stars = "⭐⭐⭐⭐"
            advice = "放量攻击，跟进"
            reason = "量价齐升"
        elif pct > 2 and vr > 3 and tr > 5:
            stars = "⭐⭐⭐⭐⭐"
            advice = "主力抢筹，低吸"
            reason = "底部巨量"
        elif pct < -2:
            stars = "⭐"
            advice = "破位，规避"
            reason = "趋势走坏"
            
        stocks.append({
            "code": code,
            "name": data['name'],
            "price": data['price'],
            "change_pct": pct,
            "volume_ratio": vr,
            "turnover": tr,
            "stars": stars,
            "advice": advice,
            "reason": reason
        })
    
    if not stocks: return None
    
    # 计算板块平均涨幅
    avg_pct = sum(s['change_pct'] for s in stocks) / len(stocks)
    
    # 🚨 过滤机制：如果板块整体是绿的，且没有涨停股，直接扔掉！不推垃圾！
    has_limit_up = any(s['change_pct'] > 9.5 for s in stocks)
    if avg_pct < 0.5 and not has_limit_up:
        return None
        
    # 按涨幅排序
    stocks.sort(key=lambda x: x['change_pct'], reverse=True)
    
    return {
        "name": name,
        "type": source_type,
        "avg_pct": round(avg_pct, 2),
        "leading_stocks": stocks[:5] # 只取前5
    }

def scan_market():
    """全市场扫描"""
    hot_sectors = []
    
    # 1. 扫描你的科技/政策池
    print("🔍 扫描用户关注池...")
    for sector_name, codes in TECH_POLICY_POOL.items():
        result = analyze_sector(sector_name, codes, "科技(政策)")
        if result:
            hot_sectors.append(result)
            
    # 2. 扫描同花顺/东财概念 (补充热点)
    print("🔍 扫描市场突发热点...")
    try:
        # 获取涨幅前10的概念
        bk_df = ak.stock_board_concept_name_em()
        top_bk = bk_df.sort_values(by='涨跌幅', ascending=False).head(8)
        
        for _, row in top_bk.iterrows():
            bk_name = row['板块名称']
            bk_code = row['板块代码']
            
            # 简单去重
            if any(s['name'] in bk_name for s in hot_sectors): continue
            
            # 获取成分股
            cons_df = ak.stock_board_concept_cons_em(symbol=bk_name)
            codes = cons_df['代码'].tolist()[:10] # 取前10个成分股分析
            
            result = analyze_sector(bk_name, codes, "题材(游资)")
            if result:
                hot_sectors.append(result)
                
    except Exception as e:
        print(f"⚠️ 概念扫描部分失败: {e}")

    # 按板块涨幅排序
    hot_sectors.sort(key=lambda x: x['avg_pct'], reverse=True)
    return hot_sectors[:6] # 只保留最强6个

def main():
    if not load_global_market_data():
        return

    sectors = scan_market()
    
    # 简单的市场情绪
    up_count = sum(1 for v in GLOBAL_MARKET_MAP.values() if v['change_pct'] > 0)
    total = len(GLOBAL_MARKET_MAP)
    sentiment = "🔴 情绪高涨" if up_count/total > 0.6 else ("🟢 情绪低迷" if up_count/total < 0.4 else "⚪ 震荡市")

    final_data = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "market_sentiment": {
            "summary": sentiment,
            "up_ratio": f"{up_count}/{total}"
        },
        "hot_sectors": sectors
    }

    # 保存
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n🚀 报告生成完毕！已过滤掉所有下跌板块，只保留 {len(sectors)} 个强势机会。")

if __name__ == "__main__":
    main()