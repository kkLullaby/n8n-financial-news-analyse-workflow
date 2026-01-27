import requests
import akshare as ak
import pandas as pd
import time

# Helper for printing
def p(name, df):
    if df is not None and not df.empty:
        print(f"✅ {name} 获取成功 ({len(df)} 条):")
        print(df.head(3))
    else:
        print(f"❌ {name} 获取失败或为空")

print("正在测试概念板块接口...")

# Test 1: Akshare TongHuaShun Concepts
try:
    print("\n[测试 1] 同花顺概念板块 (ak.stock_board_concept_name_ths)...")
    # This function usually returns a dataframe with columns like '日期', '概念名称', '成分股数量', '网址', '涨跌幅', ...
    df_ths = ak.stock_board_concept_name_ths()
    print("Columns:", df_ths.columns.tolist())
    p("同花顺概念", df_ths)
except Exception as e:
    print(f"❌ 同花顺概念出错: {e}")

# Test 2: Sina Concepts (Manual Request)
try:
    print("\n[测试 2] 新浪概念板块 (Direct Requests)...")
    url = "http://vip.stock.finance.sina.com.cn/q/view/newSinaBlock.php"
    # Parameters guessed/inferred from similar endpoints. 
    # Usually it returns a variable like S_Finance_bankuai_sinagn
    params = {
        "page": "1",
        "num": "10",
        "sort": "changepercent",
        "asc": "0",
        "node": "sinagn"  # sinahy=industry, sinagn=concept?
    }
    # Trying the JS endpoint directly as well
    # http://vip.stock.finance.sina.com.cn/q/view/newSinaBlock.php?page=1&num=10&sort=changepercent&asc=0&node=sinagn
    # Or strict newSinaGn.php
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
         'Referer': 'https://finance.sina.com.cn/'
    }
    
    # Attempt A: newSinaGn.php
    url_A = "http://vip.stock.finance.sina.com.cn/q/view/newSinaGn.php" 
    resp_A = requests.get(url_A, headers=headers, timeout=5)
    resp_A.encoding = 'gbk'
    print(f"   -> newSinaGn.php 长度: {len(resp_A.text)}")
    if len(resp_A.text) < 500: print(f"      内容: {resp_A.text[:100]}")

    # Attempt B: API Query
    url_B = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    params_B = {
         "page": "1", "num": "10", "sort": "changepercent", "asc": "0", "node": "sinagn"
    }
    resp_B = requests.get(url_B, params=params_B, headers=headers, timeout=5)
    print(f"   -> API (node=sinagn) 状态: {resp_B.status_code}, 内容长度: {len(resp_B.text)}")
    print(f"      前100字符: {resp_B.text[:100]}")
    
except Exception as e:
    print(f"❌ 新浪概念出错: {e}")
