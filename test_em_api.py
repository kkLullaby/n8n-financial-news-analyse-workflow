import os
import sys
import requests
import akshare as ak
import pandas as pd

# ==========================================
# 🚑 网络修复补丁 (复刻自 market_scanner.py)
# ==========================================
os.environ['NO_PROXY'] = '*'
if 'http_proxy' in os.environ: del os.environ['http_proxy']
if 'https_proxy' in os.environ: del os.environ['https_proxy']
if 'all_proxy' in os.environ: del os.environ['all_proxy']

FAKE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': 'https://www.eastmoney.com/'
}

_original_session_init = requests.Session.__init__
def _patched_session_init(self, *args, **kwargs):
    _original_session_init(self, *args, **kwargs)
    self.headers.update(FAKE_HEADERS)
    self.trust_env = False
requests.Session.__init__ = _patched_session_init

# ==========================================
# 🧪 测试内容
# ==========================================
print("正在测试东财板块接口...")

try:
    print("1. 尝试获取行业板块排行 (ak.stock_board_industry_name_em)...")
    df_industry = ak.stock_board_industry_name_em()
    print(f"✅ 成功! 获取到 {len(df_industry)} 个行业板块")
    print(df_industry[['板块名称', '涨跌幅', '领涨股票']].head(3))
except Exception as e:
    print(f"❌ 行业板块获取失败: {e}")

print("-" * 30)

try:
    print("2. 尝试获取概念板块排行 (ak.stock_board_concept_name_em)...")
    df_concept = ak.stock_board_concept_name_em()
    print(f"✅ 成功! 获取到 {len(df_concept)} 个概念板块")
    print(df_concept[['板块名称', '涨跌幅', '领涨股票']].head(3))
except Exception as e:
    print(f"❌ 概念板块获取失败: {e}")
