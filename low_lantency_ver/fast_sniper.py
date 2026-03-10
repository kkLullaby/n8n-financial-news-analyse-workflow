import json
import os
import time
import pandas as pd
from pytdx.hq import TdxHq_API

# ==========================================
# 1. 路径配置
# ==========================================
# 读取雷达脚本生成的本地 json
HOT_POOL_PATH = '/home/kk/文档/Obsidian Vault/skills_download/transmit/stocks_analyse_n8n/data/sector_radar.json'
# 狙击手最终生成的分析数据
MARKET_DATA_PATH = '/home/kk/文档/Obsidian Vault/skills_download/transmit/stocks_analyse_n8n/data/market_data.json'

# ==========================================
# 2. 高可用通达信行情服务器池 (分散节点防 Timeout)
# ==========================================
# TDX_SERVERS = [
#     {"name": "深圳招商", "ip": "119.147.212.81", "port": 7709},
#     {"name": "上海华泰", "ip": "101.226.226.225", "port": 7709},
#     {"name": "杭州双线", "ip": "218.108.47.69", "port": 7709},
#     {"name": "武汉电信", "ip": "119.97.185.73", "port": 7709}
# ]
TDX_SERVERS = [
    {'name': '上证云成都电信一', 'ip': '218.6.170.47', 'port': 7709},
    {'name': '上证云北京联通一', 'ip': '123.125.108.14', 'port': 7709},
    {'name': '上海电信主站Z1', 'ip': '180.153.18.170', 'port': 7709},
]

def format_tdx_code(code: str):
    """将标准代码 (sh600000, sz000001) 转为 PyTDX 市场格式"""
    code = code.lower().strip()
    if code.startswith('sh'):
        return (1, code[2:])
    elif code.startswith('sz'):
        return (0, code[2:])
    if code.startswith(('60', '68')):
        return (1, code)
    return (0, code)

def main():
    start_time = time.time()
    
    # --- 步骤 1: 瞬间加载预设池 ---
    try:
        with open(HOT_POOL_PATH, 'r', encoding='utf-8') as f:
            hot_pool = json.load(f)
    except FileNotFoundError:
        print(f"⚠️ 未找到雷达数据，使用空数据池回退进行测试。")
        hot_pool = {"candidate_stocks": [], "my_stocks": [], "news": "No news."}
        
    # 安全提取数据，防止 key 不存在
    candidates = hot_pool.get('candidate_stocks', [])
    my_stocks = hot_pool.get('my_stocks', [])
    news = hot_pool.get('news', '')
    
    all_codes = list(set(candidates + my_stocks))
    if not all_codes:
        print("⚠️ 股票池为空，直接退出。")
        return
        
    query_list = [format_tdx_code(c) for c in all_codes]
    
    # --- 步骤 2: PyTDX 闪电直连与容错轮询 ---
    api = TdxHq_API(auto_retry=True)
    connected = False
    
    for server in TDX_SERVERS:
        print(f"尝试连接 {server['name']} ({server['ip']})...", end="")
        try:
            # 加入 try...except 防止 TimeoutError 砸穿程序
            if api.connect(server['ip'], server['port']):
                print(" ✅ 成功")
                connected = True
                break
        except Exception:
            print(" ❌ 超时")
            
    if not connected:
        print("🚨 所有行情服务器均连接失败，请检查网络或关闭代理！")
        return
        
    # --- 步骤 3: 批量快照请求 ---
    try:
        quotes = api.get_security_quotes(query_list)
    finally:
        api.disconnect() # 确保连接被释放
        
    if not quotes:
        print("⚠️ 未获取到行情数据。")
        return
        
    # --- 步骤 4: Pandas 内存极速过滤 ---
    df = pd.DataFrame(quotes)
    
    # 防爆除零错误：过滤掉昨收为0的异常股票（停牌或新股）
    df['pct_chg'] = df.apply(
        lambda row: (row['price'] - row['last_close']) / row['last_close'] * 100 if row['last_close'] > 0 else 0, 
        axis=1
    )
    def restore_code(row):
        prefix = 'sh' if row['market'] == 1 else 'sz'
        return f"{prefix}{row['code']}"
        
    df['stock_code'] = df.apply(restore_code, axis=1)
    df['is_holding'] = df['stock_code'].isin(my_stocks)
    
    # ==========================================
    # --- 步骤 4: Pandas 内存极速过滤 (活跃度量化版) ---
    # ==========================================
    # 计算主动买盘(外盘)占比: b_vol(主动买入量) / vol(总成交量) * 100
    df['buy_vol_ratio'] = df.apply(
        lambda row: (row['b_vol'] / row['vol'] * 100) if row['vol'] > 0 else 0, 
        axis=1
    )
    
    # 硬逻辑过滤
    mask_holding = df['is_holding'] == True
    
    # 候选股过滤底线：去除涨跌幅限制，仅要求“买盘成交占比严格大于 50%” 且有真实成交
    mask_filtered = (df['is_holding'] == False) & (df['vol'] > 0) & (df['buy_vol_ratio'] > 50.0)
    
    df_final = df[mask_holding | mask_filtered]
    
    # --- 步骤 5: 数据组装与落盘 ---
    result = {
        "timestamp": time.time(),
        "news_catalyst": news,
        # ⚠️ 注意这里：加入了 'buy_vol_ratio' 字段，让 AI 能够看到买盘力量
        "valid_targets": df_final[['stock_code', 'price', 'pct_chg', 'vol', 'buy_vol_ratio', 'is_holding']].to_dict(orient='records')
    }
    
    # 数据落盘
    try:
        with open(MARKET_DATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"📁 狙击手数据已写入: {MARKET_DATA_PATH}")
    except Exception as e:
        print(f"写入失败: {e}")
        with open('./market_data_fallback.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start_time
    print(f"⚡ 狙击手脚本全流程耗时: {elapsed*1000:.2f} ms")


if __name__ == '__main__':  
    main()