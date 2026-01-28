import sys
import os  # <--- 关键！补回了这个库
import json
import time
import re
import datetime
import pandas as pd
import akshare as ak
import requests
import requests.utils
import builtins
import argparse
import random
import urllib3

# ==========================================
# 🔌 N8N 适配补丁
# ==========================================
# 如果检测到 --std-json 参数：
# 1. 所有的 print() 日志会自动重定向到 stderr (不干扰数据流)
# 2. 最后会自动通过 stdout 输出干净的 JSON
_N8N_MODE = "--std-json" in sys.argv
_original_print = builtins.print

if _N8N_MODE:
    def _stderr_print(*args, **kwargs):
        # 除非显式指定输出流，否则默认打印到 stderr
        if "file" not in kwargs:
            kwargs["file"] = sys.stderr
        _original_print(*args, **kwargs)
    builtins.print = _stderr_print

# ==========================================
# 🚑 网络修复 v4.0 (回归稳定版)
# ==========================================

# # 1. 强制清理代理环境变量 (防止 ProxyError)
# # 告诉 requests 库：别管系统代理，直接用网卡发请求
# os.environ['NO_PROXY'] = '*'
# os.environ.pop('http_proxy', None)
# os.environ.pop('https_proxy', None)
# os.environ.pop('all_proxy', None)

# 2. 注入全局 User-Agent (解决 RemoteDisconnected)
# 这是一个标准的 Chrome 浏览器身份标识
# FAKE_HEADERS = {
#     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
#     'Accept': 'application/json, text/javascript, */*; q=0.01',
#     'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
#     'Referer': 'https://www.eastmoney.com/'
# }

# ==========================================
# 1. 网络设置 (修复 NameError 版)
# ==========================================

# 禁用安全警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 定义 UA 池
UA_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0'
]

def get_random_headers(referer='https://quote.eastmoney.com/'):
    return {
        'User-Agent': random.choice(UA_POOL),
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        # 🔥 修改点1：恢复长连接，模拟真实浏览器行为
        'Connection': 'keep-alive',
        'Referer': referer
    }

FAKE_HEADERS = get_random_headers()

_original_session_init = requests.Session.__init__

def _patched_session_init(self, *args, **kwargs):
    _original_session_init(self, *args, **kwargs)
    self.headers.update(get_random_headers())
    self.verify = False 
    
    # 🔥 修改点2：增大重试间隔
    # backoff_factor=2 意味着重试间隔是 1s, 2s, 4s... 给服务器喘息时间
    retry_strategy = urllib3.util.retry.Retry(
        total=3, 
        backoff_factor=2, 
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
    self.mount("https://", adapter)
    self.mount("http://", adapter)

requests.Session.__init__ = _patched_session_init

print("✅ 网络配置优化完成 (Keep-Alive + 智能退避重试)")

# ==========================================
# 👇 下面接着你的配置代码 (从 OUTPUT_FILE 开始)
# ==========================================
# (请保留你后面原有的代码，不要删除)

# ... 后面的代码完全不用动 ...

# 1. 文件保存路径
OUTPUT_FILE = "/home/kk/n8n/market_data.json"
HISTORY_FILE = "/home/kk/n8n/history_data.csv"
STOCK_FILE = "/home/kk/n8n/my_stocks.txt"

# 2. 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 2  # 秒

# 3. 科技/政策热点概念池 (2025-2026 核心赛道，手动维护)
# 🎯 散户最关注的高弹性题材，优先级高于传统行业
TECH_POLICY_HOT_STOCKS = {
    "AI算力/CPO/光模块": ["300308", "603083", "000977", "600941", "002475"],
    "人形机器人/具身智能": ["300024", "002527", "300775", "603901", "688161"],
    "低空经济/eVTOL": ["002097", "688220", "002985", "002313", "300034"],
    "DeepSeek/国产大模型": ["300229", "002230", "300418", "300496", "688083"],
    "量子计算/量子通信": ["600522", "688027", "300077", "600990", "002224"],
    "固态电池/钠电池": ["300750", "002460", "688063", "002074", "300014"],
    "半导体/先进封装": ["688981", "603986", "688012", "300661", "688041"],
    "卫星互联网/6G": ["600118", "600990", "002025", "600879", "000547"],
}

# 传统行业备用池（仅当科技热点不足时启用）
FALLBACK_HOT_STOCKS = {
    "可控核聚变/核电": ["601985", "000969", "002438", "002355", "688120"],
    "油气开采/能源": ["601857", "600028", "600938", "600583", "600256"],
    "贵金属/黄金": ["601899", "600547", "002716", "600489", "002155"],
    "新能源车/智驾": ["002594", "601238", "002869", "300750", "600009"]
}

# ==========================================
# 🔧 工具函数
# ==========================================

def calculate_stock_rating(pct, vol_ratio, trend_score, rsi):
    """【升级】量化评级算法 (0-100分) - 增加颗粒度区分"""
    score = 50.0 # 基础分
    
    # 1. 趋势得分 (权重最高)
    if trend_score >= 3: score += 20      # 均线多头
    elif trend_score >= 1: score += 10    # 企稳
    elif trend_score <= -2: score -= 15   # 破位下跌
    
    # 2. 涨幅动能 (使用精确涨幅加分，区分 5% 和 9%)
    # 涨幅每 1%，加 1.5 分；跌幅同理
    score += (pct * 1.5)
    
    # 3. 量能评分 (量价配合)
    # 量比每增加 0.1，加 1 分 (上限 15分)
    if vol_ratio > 0.8:
        vol_score = min((vol_ratio - 0.8) * 10, 15)
        score += vol_score
    else:
        score -= 5 # 缩量
    
    # 过大放量惩罚
    if vol_ratio > 4.0: score -= 5
    
    # 4. RSI修正
    if rsi > 85: score -= 10              # 超买风险
    elif rsi < 20: score += 10            # 超卖反弹机会
    
    # 限制范围
    score = max(0, min(100, score))
    
    # 评级标签
    comment = ""
    if score >= 90: 
        rating = "⭐⭐⭐⭐⭐(妖股)"
        comment = "主升浪 | 极强"
    elif score >= 80: 
        rating = "⭐⭐⭐⭐(强推)"
        comment = "多头加速 | 推荐"
    elif score >= 65: 
        rating = "⭐⭐⭐(买入)"
        comment = "趋势向上 | 温和"
    elif score >= 50: 
        rating = "⭐⭐(持有)"
        comment = "震荡整理 | 观望"
    elif score >= 35: 
        rating = "⭐(观望)"
        comment = "走势偏弱 | 谨慎"
    else: 
        rating = "☠️(卖出)"
        comment = "破位下跌 | 规避"
    
    # 特殊注脚
    if vol_ratio > 3: comment += " | 放量"
    if rsi > 85: comment += " | 超买"
    
    return round(score, 1), rating, comment

# def calculate_technical_indicators(df):
#     """【升级】计算技术指标 (MA, RSI, VOL) 并生成严格评级"""
#     if df is None or len(df) < 30:
#         return None
        
#     try:
#         # 1. 均线 MA
#         df['MA5'] = df['收盘'].rolling(window=5).mean()
#         df['MA10'] = df['收盘'].rolling(window=10).mean()
#         df['MA20'] = df['收盘'].rolling(window=20).mean()
        
#         # 2. RSI (相对强弱指标)
#         delta = df['收盘'].diff()
#         gain = (delta.where(delta > 0, 0)).rolling(window=6).mean()
#         loss = (-delta.where(delta < 0, 0)).rolling(window=6).mean()
#         rs = gain / loss
#         df['RSI6'] = 100 - (100 / (1 + rs))
        
#         # 3. 趋势判定
#         latest = df.iloc[-1]
#         prev = df.iloc[-2]
        
#         trend_score = 0
#         signals = []
#         risk_warnings = []
        
#         # MA多头排列
#         if latest['MA5'] > latest['MA10'] > latest['MA20']:
#             trend_score += 3
#             signals.append("多头")
        
#         # 金叉
#         if prev['MA5'] < prev['MA10'] and latest['MA5'] > latest['MA10']:
#             trend_score += 2
#             signals.append("金叉")
            
#         # 量价配合
#         vol_mean = df['成交量'].tail(5).mean()
#         vol_ratio = latest['成交量'] / vol_mean if vol_mean > 0 else 0
        
#         if latest['收盘'] > prev['收盘'] and vol_ratio > 1.2:
#             trend_score += 1
#             signals.append("放量")
            
#         # RSI分析
#         rsi = latest['RSI6'] if not pd.isna(latest['RSI6']) else 50
#         if rsi > 80:
#             risk_warnings.append("超买")
#         elif rsi < 20:
#             signals.append("超卖")
#             trend_score += 1 # 超卖反弹算正向
            
#         # 计算综合评级
#         pct = (latest['收盘'] - prev['收盘']) / prev['收盘'] * 100
#         score, rating_label, rating_comment = calculate_stock_rating(pct, vol_ratio, trend_score, rsi)

#         return {
#             "ma5": round(latest['MA5'], 2),
#             "ma20": round(latest['MA20'], 2),
#             "rsi6": round(rsi, 2),
#             "trend_score": trend_score,
#             "signals": signals,
#             "risks": risk_warnings,
#             "volume_ratio": round(vol_ratio, 2),
#             "rating_score": score,      # 0-100 分数
#             "rating_label": rating_label, # 星级文本
#             "rating_comment": rating_comment # 短评
#         }
#     except:
#         return None

import pandas as pd
import datetime
import numpy as np

# ==========================================
# 🔧 核心工具函数 (已修正)
# ==========================================

def get_market_progress():
    """
    【新增】计算当前交易日的时间进度 (0.0 ~ 1.0)
    用于在盘中估算全天成交量，修复量比失真问题。
    """
    now = datetime.datetime.now()
    
    # 1. 如果是周末或非交易时段（晚上），直接视为已收盘 (进度 1.0)
    if now.weekday() >= 5 or now.hour >= 15:
        return 1.0
    if now.hour < 9 or (now.hour == 9 and now.minute < 30):
        return 0.01 # 开盘前给个极小值防止除零
        
    # 2. 计算已开盘分钟数 (A股交易时间: 9:30-11:30, 13:00-15:00)
    minutes_passed = 0
    
    # 上午场
    morning_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
    morning_end = now.replace(hour=11, minute=30, second=0, microsecond=0)
    
    # 下午场
    afternoon_start = now.replace(hour=13, minute=0, second=0, microsecond=0)
    afternoon_end = now.replace(hour=15, minute=0, second=0, microsecond=0)
    
    if now < morning_end:
        # 还在上午
        delta = now - morning_start
        minutes_passed = max(0, delta.total_seconds() / 60)
    elif now < afternoon_start:
        # 中午休市，按上午满场算 (120分钟)
        minutes_passed = 120
    else:
        # 下午
        delta = now - afternoon_start
        minutes_passed = 120 + max(0, delta.total_seconds() / 60)
        
    # A股全天交易240分钟
    progress = min(1.0, minutes_passed / 240.0)
    return max(0.01, progress) # 保底返回 1% 进度

def calculate_technical_indicators(df):
    """
    【升级版】计算技术指标 (MA, RSI-EMA, 动态量比)
    """
    # 基础数据清洗
    if df is None or len(df) < 30:
        return None
    
    # 确保收盘价是浮点数
    df['收盘'] = pd.to_numeric(df['收盘'], errors='coerce')
    df['成交量'] = pd.to_numeric(df['成交量'], errors='coerce')
    
    try:
        # 1. 均线 MA (算法不变)
        df['MA5'] = df['收盘'].rolling(window=5).mean()
        df['MA10'] = df['收盘'].rolling(window=10).mean()
        df['MA20'] = df['收盘'].rolling(window=20).mean()
        
        # 2. RSI (相对强弱指标) - 【已修正为 EMA 算法】
        # 同花顺/通达信使用的是 Wilder's Smoothing，等价于 alpha=1/N 的 EMA
        delta = df['收盘'].diff()
        
        # 将涨跌分开
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        
        # 使用 EWM 计算 (com=5 对应 window=6 的权重)
        # adjust=False 是关键，确保递归计算与软件一致
        ema_up = up.ewm(com=5, adjust=False).mean()
        ema_down = down.ewm(com=5, adjust=False).mean()
        
        # 计算 RS 和 RSI
        rs = ema_up / ema_down
        df['RSI6'] = 100 - (100 / (1 + rs))
        
        # 3. 获取最新数据点
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # 4. 动态量比计算 - 【已修正盘中逻辑】
        # 获取过去 5 天的平均成交量 (不包含今天，防止被今天的实时量拉低均值)
        # shift(1) 确保取的是“昨天及之前”的5天
        vol_ma5 = df['成交量'].shift(1).rolling(window=5).mean().iloc[-1]
        
        current_vol = latest['成交量']
        
        # 判断最后一行是否为“今天”的数据 (假设df有日期列，或者默认最后一行是最新)
        # 获取时间进度 (如果在盘中，progress 会是 0.x)
        market_progress = get_market_progress()
        
        # 估算全天成交量 = 当前成交量 / 时间进度
        # 如果是收盘后，progress为1，projected_vol 就是 current_vol
        if market_progress < 1.0:
            projected_vol = current_vol / market_progress
        else:
            projected_vol = current_vol
            
        # 计算真实量比
        if vol_ma5 > 0:
            vol_ratio = projected_vol / vol_ma5
        else:
            vol_ratio = 0
            
        # 5. 趋势信号判定 (逻辑保持一致)
        trend_score = 0
        signals = []
        risk_warnings = []
        
        # MA多头排列
        if latest['MA5'] > latest['MA10'] > latest['MA20']:
            trend_score += 3
            signals.append("多头")
        
        # 金叉
        if prev['MA5'] < prev['MA10'] and latest['MA5'] > latest['MA10']:
            trend_score += 2
            signals.append("金叉")
            
        # 放量判断 (使用修正后的量比)
        if latest['收盘'] > prev['收盘'] and vol_ratio > 1.2:
            trend_score += 1
            signals.append("放量")
            
        # RSI分析
        rsi = latest['RSI6'] if not pd.isna(latest['RSI6']) else 50
        if rsi > 85: # 提高一点阈值，EMA算法通常波动更灵敏
            risk_warnings.append("超买")
        elif rsi < 20:
            signals.append("超卖")
            trend_score += 1 
            
        # 6. 调用评级
        pct = (latest['收盘'] - prev['收盘']) / prev['收盘'] * 100
        score, rating_label, rating_comment = calculate_stock_rating(pct, vol_ratio, trend_score, rsi)

        return {
            "ma5": round(latest['MA5'], 2),
            "ma20": round(latest['MA20'], 2),
            "rsi6": round(rsi, 2),
            "trend_score": trend_score,
            "signals": signals,
            "risks": risk_warnings,
            "volume_ratio": round(vol_ratio, 2), # 此时输出的是经过修正的有效量比
            "rating_score": score,
            "rating_label": rating_label,
            "rating_comment": rating_comment
        }
    except Exception as e:
        print(f"技术指标计算出错: {e}")
        return None


def safe_float(value, default=0.0):
    """【新增】安全转换浮点数，防止 '-' 或 None 报错"""
    try:
        if value is None:
            return default
        s_val = str(value).strip()
        if s_val == "" or s_val == "-":
            return default
        return float(s_val)
    except:
        return default

def get_latest_trade_date():
    """【新增】智能获取最近交易日（处理周末/节假日逻辑）"""
    # 注意：这是一个简易逻辑，无法处理“周三是春节”这种情况。
    # 生产环境建议使用 chinesecalendar 库，但作为轻量脚本暂时够用。
    now = datetime.datetime.now()
    # 如果是周六(5)或周日(6)，或者周一(0)的早上9点前，推到上周五
    if now.weekday() == 5:  # 周六
        target = now - datetime.timedelta(days=1)
    elif now.weekday() == 6:  # 周日
        target = now - datetime.timedelta(days=2)
    elif now.weekday() == 0 and now.hour < 15: # 周一未收盘前，看上周五
        target = now - datetime.timedelta(days=3)
    elif now.hour < 15: # 其他工作日未收盘前，看昨天
        target = now - datetime.timedelta(days=1)
    else:
        target = now
    return target.strftime("%Y%m%d")

def retry_on_failure(func, *args, max_retries=MAX_RETRIES, **kwargs):
    """带重试的函数调用"""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"    重试 {attempt + 1}/{max_retries}...")
                time.sleep(RETRY_DELAY)
            else:
                raise e

def get_stocks_realtime_sina(codes):
    """【升级】分批获取新浪行情，防止URL过长，并解析成交量"""
    if not codes:
        return []
    
    # 1. 代码标准化 (添加 sh/sz/bj 前缀)
    sina_codes = []
    for code in codes:
        code = str(code).strip()
        if not code: continue
        
        # 如果已有前缀，直接用
        if code[:2].lower() in ['sh', 'sz', 'bj']:
            sina_codes.append(code)
            continue
            
        # 自动推断前缀
        code_str = code.zfill(6)
        if code_str.startswith('6'):
            sina_codes.append(f"sh{code_str}")
        elif code_str.startswith('5'): # ETF/基金 归为上海
            sina_codes.append(f"sh{code_str}")
        elif code_str.startswith('8') or code_str.startswith('4') or code_str.startswith('92'): 
            # 8/4开头是北交所，920也是北交所，900是B股(归上海，这里暂忽略B股)
            sina_codes.append(f"bj{code_str}")
        else:
            # 00, 30 都是深圳
            sina_codes.append(f"sz{code_str}")

    # 2. 分批请求 (Batching) - 关键修复！
    # 新浪接口限制 URL 长度，建议每批 30 个
    batch_size = 30
    all_results = []
    
    headers = get_random_headers(referer='https://finance.sina.com.cn')

    for i in range(0, len(sina_codes), batch_size):
        batch = sina_codes[i : i + batch_size]
        list_str = ','.join(batch)
        url = f"https://hq.sinajs.cn/list={list_str}"
        
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            # 新浪老接口通常是 GBK 编码
            resp.encoding = 'gbk'
            
            lines = resp.text.strip().split('\n')
            for line in lines:
                if '="' not in line: continue
                
                try:
                    # 解析行: var hq_str_sz000001="平安银行,10.50,10.48,10.55,..."
                    left, right = line.split('="')
                    # 提取代码: hq_str_sz000001 -> sz000001
                    stock_code = left.split('_')[-1]
                    
                    data_str = right.strip('";')
                    data_parts = data_str.split(',')
                    
                    # 确保数据长度足够 (新浪通常有 30+ 个字段)
                    if len(data_parts) < 10:
                        continue
                        
                    # 字段映射:
                    # 0: 股票名称
                    # 1: 今日开盘
                    # 2: 昨日收盘
                    # 3: 当前价格
                    # 8: 成交量 (股数) -> 关键！
                    # 9: 成交额 (元)
                    
                    name = data_parts[0]
                    prev_close = safe_float(data_parts[2])
                    current = safe_float(data_parts[3])
                    volume_shares = safe_float(data_parts[8]) # 股数
                    
                    # 计算涨跌幅
                    pct = 0.0
                    if prev_close > 0:
                        pct = round((current - prev_close) / prev_close * 100, 2)
                    
                    # 注意：新浪不直接返回“量比”和“换手率”，
                    # 这些需要结合你的 history 数据来算。
                    # 这里我们至少返回 volume，让后面的逻辑有米下锅。
                    
                    all_results.append({
                        "name": name,
                        "code": stock_code, # 带前缀的代码
                        "price": current,
                        "change_pct": pct,
                        "volume": volume_shares, # 新增字段：当前成交量
                        "turnover": 0, # 依然缺失，需结合流通股本计算
                        "volume_ratio": 0 # 依然缺失，需结合MA5VOL计算
                    })
                    
                except Exception as parse_err:
                    # 单个解析失败不影响整批
                    print(f"解析错误 {line[:20]}: {parse_err}")
                    continue
                    
        except Exception as e:
            print(f"    批次请求失败: {e}")
            continue

    return all_results

def load_my_stocks():
    """【修复】读取持仓文件"""
    if not os.path.exists(STOCK_FILE):
        return [] 
    stock_list = []
    try:
        with open(STOCK_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        with open(STOCK_FILE, 'r', encoding='gbk') as f:
            lines = f.readlines()
            
    for line in lines:
        code = line.strip()
        if not code: continue
        # 只要包含至少6位数字即可
        if len(re.sub(r"\D", "", code)) >= 6:
            stock_list.append(code)
            
    return list(set(stock_list))

def get_stock_code_by_name(name):
    """【新增】通过新浪搜索接口，由中文名称查找股票代码"""
    try:
        url = f"http://suggest3.sinajs.cn/suggest/type=&key={name}"
        headers = get_random_headers()
        resp = requests.get(url, headers=headers, timeout=3)
        # 匹配 sh/sz/bj + 6位数字
        match = re.search(r'(sh\d{6}|sz\d{6}|bj\d{6})', resp.text)
        if match:
            return match.group(0)
    except:
        pass
    return None

# ==========================================
# 🚀 核心功能函数
# ==========================================

def get_market_sentiment():
    """1. 获取大盘情绪 + 量化指标 (安全版 - 已移除全市场扫描以防封IP)"""
    
    index_value = 0
    change_pct = 0
    volume = 0
    
    # === 方案1: 新浪财经HTTP API (首选，速度快且稳定) ===
    for attempt in range(MAX_RETRIES):
        try:
            sina_url = "https://hq.sinajs.cn/list=sh000001"
            headers = get_random_headers(referer='https://finance.sina.com.cn')
            resp = requests.get(sina_url, headers=headers, timeout=5)
            
            if 'sh000001' in resp.text:
                 data = resp.text.split('"')[1].split(',')
                 if len(data) > 3:
                     prev_close = safe_float(data[2])
                     index_value = safe_float(data[3])
                     volume = safe_float(data[9])
                     if prev_close > 0:
                         change_pct = round((index_value - prev_close) / prev_close * 100, 2)
                     break
        except:
            # 失败后稍作休息
            time.sleep(1)
    
    # === 方案2: 备用 Akshare (仅在方案1失败时运行) ===
    if index_value == 0:
        try:
            print("    -> 正在切换至备用接口获取大盘指数...")
            # 使用轻量级指数接口
            sh_df = ak.stock_zh_index_daily_em(symbol="sh000001")
            latest = sh_df.iloc[-1]
            index_value = safe_float(latest['close'])
            # 注意：daily接口拿不到实时涨跌，这里只能做个大概兜底
            print("    -> ⚠️ 注意：备用接口仅提供昨日收盘数据作为参考")
        except:
            pass

    # === 获取涨跌家数 (🔥 关键修改：安全模式) ===
    # 原有的 ak.stock_zh_a_spot_em() 极易触发封禁，此处直接移除
    
    up_count, down_count = 0, 0
    up_ratio = 50
    
    print("    -> (安全模式) 跳过全市场扫描，基于指数估算市场情绪...")
    
    # 基于大盘涨跌幅的经验估算模型
    if change_pct > 1.5:
        up_ratio = 80 # 大涨
    elif change_pct > 0.5:
        up_ratio = 65 # 普涨
    elif change_pct > 0:
        up_ratio = 55 # 震荡偏强
    elif change_pct > -0.5:
        up_ratio = 45 # 震荡偏弱
    elif change_pct > -1.5:
        up_ratio = 30 # 普跌
    else:
        up_ratio = 10 # 大跌/股灾

    # === 量化评分逻辑 (补全) ===
    # 综合得分 = 涨跌幅权重 + 赚钱效应权重
    temp_score = change_pct * 10 + (up_ratio - 50) * 0.5
    
    # 1. 市场温度
    if temp_score > 15: market_temperature = "🔥 极度亢奋"
    elif temp_score > 8: market_temperature = "🌡️ 偏热"
    elif temp_score > 0: market_temperature = "😊 温和"
    elif temp_score > -8: market_temperature = "😐 冷静"
    elif temp_score > -15: market_temperature = "🥶 偏冷"
    else: market_temperature = "❄️ 极度恐慌"
    
    # 2. 风险等级
    if change_pct < -2:
        risk_level = "🔴 高风险"
        risk_score = 3
    elif change_pct < -0.8:
        risk_level = "🟡 中等风险"
        risk_score = 2
    elif change_pct > 0.8:
        risk_level = "🟢 低风险" # 趋势向上风险反而低
        risk_score = 1
    else:
        risk_level = "⚪ 中性"
        risk_score = 1.5
    
    # 3. 操作建议
    if risk_score >= 3: suggested_action = "🛑 减仓防守"
    elif risk_score >= 2: suggested_action = "⚠️ 谨慎低吸"
    elif change_pct > 1.0: suggested_action = "🚀 积极做多"
    else: suggested_action = "👀 观望/轻仓试错"
    
    return {
        "index_value": index_value,
        "change_pct": change_pct,
        "volume": volume,
        "up_count": up_count, # 估算模式下这两个值为0
        "down_count": down_count,
        "up_ratio": up_ratio,
        "market_temperature": market_temperature,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "suggested_action": suggested_action
    }

def get_tech_policy_sectors():
    """
    【升级】扫描科技热点 
    关键优化：增加延时，防止因请求过快被封IP
    """
    print("正在扫描科技/政策热点...")
    tech_sectors = []
    
    # 限制最大处理板块数，防止超时
    # TECH_POLICY_HOT_STOCKS 最好按优先级排序
    
    for sector_key, codes in TECH_POLICY_HOT_STOCKS.items():
        # 1. 先批量获取实时价格 (这是轻量级操作)
        leading_stocks = get_stocks_realtime_sina(codes)
        
        if not leading_stocks: 
            continue
        
        # 过滤无效股
        leading_stocks = [s for s in leading_stocks if s['price'] > 0]
        if not leading_stocks: 
            continue
            
        avg_pct = sum(s['change_pct'] for s in leading_stocks) / len(leading_stocks)
        
        # 【剪枝策略】如果板块均跌 > 1%，直接跳过，不算技术指标了，节省时间
        if avg_pct < -1.0:
            print(f"  -> 跳过弱势板块: {sector_key} ({avg_pct:.2f}%)")
            continue

        valid_stocks_with_rating = []
        
        for stock in leading_stocks:
            # 【剪枝策略】只对涨幅 > 0 的股票计算技术指标，或者如果是龙头(Code在列表前2位)也计算
            is_key_stock = stock['code'] in codes[:2] # 是否是预设的龙头
            if stock['change_pct'] <= 0 and not is_key_stock:
                stock['recommendation'] = "⚪"
                valid_stocks_with_rating.append(stock)
                continue
                
            try:
                # 提取纯数字代码: sh600519 -> 600519
                # akshare需要纯数字
                c6 = re.sub(r"\D", "", stock['code'])
                
                # 🔥 关键：每次请求历史K线前，休息 0.3 秒，防止被封 🔥
                time.sleep(2)
                
                # 获取历史数据
                hist = ak.stock_zh_a_hist(symbol=c6, period="daily", adjust="qfq")
                
                # 计算指标 (使用 Part 2 的函数)
                tech = calculate_technical_indicators(hist)
                
                if tech:
                    stock['technical'] = tech
                    stock['recommendation'] = tech['rating_label']
                else:
                    stock['recommendation'] = "⚪"
                
                valid_stocks_with_rating.append(stock)
                
            except Exception as e:
                # 单个股票失败不影响整个板块
                print(f"    股票 {stock['name']} 分析失败: {e}")
                stock['recommendation'] = "❓"
                valid_stocks_with_rating.append(stock)
        
        # 排序：优先展示评分高的
        valid_stocks_with_rating.sort(
            key=lambda x: x.get('technical', {}).get('rating_score', 0), 
            reverse=True
        )
        
        # 计算板块热度分
        max_pct = max([s['change_pct'] for s in valid_stocks_with_rating]) if valid_stocks_with_rating else 0
        heat_score = avg_pct * 0.8 + max_pct * 0.2
        if avg_pct > 0.5: heat_score += 5

        sector_name = sector_key.split('/')[0]
        
        tech_sectors.append({
            "name": sector_name,
            "change_pct": round(avg_pct, 2),
            "heat_score": round(heat_score, 2),
            "leading_stocks": valid_stocks_with_rating[:3], # 只保留前3名，减少JSON体积
            "source": "tech_policy"
        })
        print(f"  -> ✅ 板块已分析: {sector_name}")

    # 按热度排序板块
    tech_sectors.sort(key=lambda x: x['heat_score'], reverse=True)
    return tech_sectors

def get_hot_concepts(top_n=5):
    """【升级】同花顺概念资金流向扫描 (自动挖掘成分股，确保每个题材推荐3-5只)"""
    print(f"正在扫描同花顺题材热点...")
    concepts = []
    
    try:
        # 获取即时资金流向 (按涨跌幅排)
        df_flow = ak.stock_fund_flow_concept(symbol="即时")
        if df_flow is None or df_flow.empty:
            return []
            
        # 按 '行业-涨跌幅' 降序排序
        sort_col = '行业-涨跌幅'
        if sort_col not in df_flow.columns:
            return []
            
        df_flow = df_flow.sort_values(by=sort_col, ascending=False).head(top_n)
        
        for _, row in df_flow.iterrows():
            concept_name = row['行业']
            pct = safe_float(row[sort_col])
            
            # 只关注涨幅 > 1% 的概念
            if pct < 1.0: continue
            
            print(f"  -> 深入挖掘题材: {concept_name} (涨{pct}%) ...")
            
            leading_stocks = []
            
            # 【核心修改】尝试获取该概念下的成分股，而不仅是领涨股
            try:
                # 获取该概念板块的所有成分股
                cons_df = ak.stock_board_concept_cons_em(symbol=concept_name)
                if cons_df is not None and not cons_df.empty:
                    # 按涨跌幅倒序
                    cons_df = cons_df.sort_values(by='涨跌幅', ascending=False).head(6) 
                    codes = cons_df['代码'].tolist()
                    
                    # 批量获取实时快照
                    leading_stocks = get_stocks_realtime_sina(codes)
            except Exception as e_cons:
                # 获取成分股失败，回退到只取领涨股
                # print(f"    (成分股获取失败: {e_cons}，回退到单股模式)")
                leader_name = row['领涨股']
                leader_code_full = get_stock_code_by_name(leader_name)
                if leader_code_full:
                    leading_stocks = get_stocks_realtime_sina([leader_code_full])

            if not leading_stocks:
                continue

            # 为获取到的股票计算指标和评级
            valid_stocks = []
            for stock in leading_stocks:
                try:
                    # 过滤一下垃圾股
                    if stock['price'] == 0: continue
                    
                    c6 = stock['code'][-6:] if len(stock['code']) > 6 else stock['code']
                    hist = ak.stock_zh_a_hist(symbol=c6, period="daily", adjust="qfq")
                    tech = calculate_technical_indicators(hist)
                    
                    if tech:
                        stock['technical'] = tech
                        stock['recommendation'] = tech.get('rating_label', "⚪")
                        # 将具体评价也存入，方便后续展示
                        stock['comment'] = tech.get('rating_comment', "")
                        valid_stocks.append(stock)
                    else:
                        stock['recommendation'] = "⚪"
                        stock['comment'] = "数据不足"
                        valid_stocks.append(stock)
                except:
                    pass

            # 如果没有有效计算出的股票，就用原始的
            if not valid_stocks:
                valid_stocks = leading_stocks

            # 按评分高低排序，优中选优
            valid_stocks.sort(key=lambda x: x.get('technical', {}).get('rating_score', 0), reverse=True)
            
            concepts.append({
                "name": f"{concept_name} (题材)",
                "change_pct": pct,
                "heat_score": pct * 0.7 + 10, # 简化热度
                "leading_stocks": valid_stocks[:5], # 取前5只
                "source": "ths_concept"
            })
            
    except Exception as e:
        print(f"⚠️ 同花顺概念扫描失败: {e}")
        
    return concepts

def get_hot_sectors_and_stocks(top_n=6, stocks_per_sector=5):
    """
    2. 获取热点板块及龙头 (双引擎驱动: 科技预设 + 全市场动态)
    已移除不存在的 get_hot_concepts 函数，专注于新浪动态扫描。
    """
    print(f"正在全市场扫描主流热点赛道...")
    
    scanned_sectors = []
    
    # === A. 科技/政策热点扫描 (Part 3 已实现) ===
    # 假设 get_tech_policy_sectors 已经在之前的代码段中定义好了
    try:
        tech_sectors = get_tech_policy_sectors()
        scanned_sectors.extend(tech_sectors)
    except NameError:
        print("  ⚠️ get_tech_policy_sectors 未定义，跳过A阶段")
    except Exception as e:
        print(f"  ⚠️ 科技扫描出错: {e}")
    
    # === B. 同花顺题材扫描 (已移除，因函数未定义) ===
    # ths_concepts = get_hot_concepts(top_n=5) 
    # scanned_sectors.extend(ths_concepts)
    
    # === C. 新浪行业动态扫描 (主力逻辑) ===
    print("启动新浪全市场行业扫描...")
    try:
        # 1. 获取新浪行业涨幅榜
        sina_hy_url = "http://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php"
        headers = get_random_headers(referer='https://finance.sina.com.cn/')
        resp = requests.get(sina_hy_url, headers=headers, timeout=6)
        resp.encoding = 'gbk' # 关键
        
        # 2. 正则提取: key:"code,name,count,avg,pct..."
        import re
        matches = re.findall(r'(?:["\'])?([a-z0-9_]+)(?:["\'])?:"([^"]+)"', resp.text)
        
        sector_list = []
        for key, val_str in matches:
            parts = val_str.split(',')
            if len(parts) > 5:
                # part[1]=name, part[5]=change_percent
                try:
                    name = parts[1]
                    pct = float(parts[5])
                    
                    sector_list.append({
                        "code": key, # 如 new_blhy
                        "name": name,
                        "change_pct": pct,
                    })
                except: continue
        
        # 3. 排序并筛选: 只看涨幅 > 0.5% 的板块，且取前 N 名
        sector_list.sort(key=lambda x: x['change_pct'], reverse=True)
        top_candidates = [s for s in sector_list[:top_n] if s['change_pct'] > 0.5]
        
        if top_candidates:
            print(f"  -> 捕获今日领涨行业: {[s['name'] for s in top_candidates]}")
        else:
            print("  -> 今日市场低迷，无明显强势行业")
        
        # 4. 深入扫描成分股 (关键优化：限制数量，防止封IP)
        for sector in top_candidates:
            # 避免重复：如果科技扫描里已经扫过了这个行业，就跳过
            if any(s['name'] in sector['name'] for s in scanned_sectors):
                continue

            node_api = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
            params = {
                "page": "1", 
                "num": str(stocks_per_sector), # 限制只取前5名
                "sort": "changepercent",
                "asc": "0",
                "node": sector['code']
            }
            
            try:
                # 稍微休息一下，对服务器友好
                time.sleep(0.5) 
                
                r_node = requests.get(node_api, params=params, headers=headers, timeout=5)
                if not r_node.text: continue
                node_stocks = r_node.json()
                
                leading_stocks = []
                # 预处理数据
                for s in node_stocks:
                    try:
                        leading_stocks.append({
                            "name": s.get('name'),
                            "code": s.get('code'), # 6位代码
                            "price": safe_float(s.get('trade')),
                            "change_pct": safe_float(s.get('changepercent')),
                            "turnover": 0 
                        })
                    except: continue
                
                if not leading_stocks: continue
                
                # 计算技术指标 (再次剪枝：只计算前3名，且必须是红盘)
                valid_stocks_with_rating = []
                for i, stock in enumerate(leading_stocks):
                    # 只有前3名 或者 涨幅>3% 的才有资格进行技术分析
                    if i >= 3 and stock['change_pct'] < 3.0:
                        stock['recommendation'] = "⚪"
                        valid_stocks_with_rating.append(stock)
                        continue

                    try:
                        # 再次休息，防止 Akshare 封 IP
                        time.sleep(0.3)
                        
                        hist = ak.stock_zh_a_hist(symbol=stock['code'], period="daily", adjust="qfq")
                        tech = calculate_technical_indicators(hist)
                        if tech:
                            stock['technical'] = tech
                            stock['recommendation'] = tech.get('rating_label', "⚪")
                        else:
                            stock['recommendation'] = "⚪"
                    except Exception as e:
                        print(f"    指标计算跳过 {stock['name']}")
                        stock['recommendation'] = "❓"
                    
                    valid_stocks_with_rating.append(stock)
                
                # 计算热度
                max_pct = max(s['change_pct'] for s in leading_stocks)
                heat_score = sector['change_pct'] * 0.7 + max_pct * 0.3
                
                scanned_sectors.append({
                    "name": sector['name'],
                    "change_pct": round(sector['change_pct'], 2),
                    "heat_score": round(heat_score, 2),
                    "leading_stocks": valid_stocks_with_rating
                })
                print(f"  -> ✅ 行业入库: {sector['name']}")
                
            except Exception as e:
                print(f"    扫描行业 {sector['name']} 失败: {e}")
                continue

    except Exception as e:
        print(f"⚠️ 新浪动态扫描异常: {e}")

    # === D. 兜底逻辑 (静态表补充) ===
    # 只有当扫出来的板块太少 (<3) 时才启动
    if len(scanned_sectors) < 3:
        print("启动备用静态板块扫描 (市场太冷)...")
        # 这里复用你原来写的 FALLBACK 逻辑，只要确保 imports 没问题即可
        # (代码略，假设你原来就有，直接保留即可)
    
    # === E. 最终排序与去重 ===
    # 按照热度排序
    scanned_sectors.sort(key=lambda x: x['heat_score'], reverse=True)
    
    # 简单的去重逻辑 (按名称)
    unique_sectors = []
    seen_names = set()
    for s in scanned_sectors:
        # 模糊匹配去重 (如 "半导体" 和 "半导体产业")
        is_duplicate = False
        for seen in seen_names:
            if s['name'] in seen or seen in s['name']:
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_sectors.append(s)
            seen_names.add(s['name'])
            
    return unique_sectors[:top_n]

def format_money(num):
    """辅助函数：将金额转换为亿/万单位"""
    try:
        if abs(num) >= 100000000:
            return f"{num/100000000:.2f}亿"
        elif abs(num) >= 10000:
            return f"{num/10000:.0f}万"
        else:
            return str(num)
    except:
        return "0"

def get_dragon_tiger_list():
    """
    3. 获取龙虎榜 (Smart Money) - 【深度优化版】
    核心策略：
    1. 智能锁定最近交易日（防止周末/早盘跑空）
    2. 直连东财底层API（速度快，包含机构数据）
    3. 按照【净买入额】排序，只看主力真金白银流入的票
    """
    print("正在挖掘龙虎榜主力资金(Smart Money)...")
    
    # 1. 智能确定日期
    # 如果现在是交易日且不到17:00，大概率龙虎榜没出完，看昨天的
    # 如果是周末，看上周五的
    now = datetime.datetime.now()
    target_date = get_latest_trade_date() # 使用之前的工具函数获取 YYYYMMDD
    
    # 如果今天是交易日但还没到16:30，强制看上一天
    if now.strftime("%Y%m%d") == target_date and now.hour < 16:
        # 简单回推一天（这里简化处理，严谨应用需判断上个交易日）
        dt = datetime.datetime.strptime(target_date, "%Y%m%d") - datetime.timedelta(days=1)
        # 如果回推是周末，再推（简化版）
        if dt.weekday() == 6: dt -= datetime.timedelta(days=2)
        elif dt.weekday() == 5: dt -= datetime.timedelta(days=1)
        target_date = dt.strftime("%Y%m%d")

    print(f"  -> 锁定龙虎榜日期: {target_date}")

    # === 方案: 直连东财底层接口 (最快、最全、含机构数据) ===
    # JMR: 净买入额, JGMMR: 机构买入额, JGMMC: 机构卖出额
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "JMR", # 关键：按净买入排序！
        "sortTypes": "-1",    # 降序，只看买入最多的
        "pageSize": "10",     # 只看全市场前10强
        "pageNumber": "1",
        "reportName": "RPT_DAILYBILLBOARD_DETAILS",
        "columns": "SECURITY_CODE,SECURITY_NAME_ABBR,EXPLANATION,CLOSE_PRICE,CHANGE_RATE,JMR,JGMMR,JGMMC",
        "source": "WEB",
        "client": "WEB",
        "filter": f"(TRADE_DATE='{target_date[0:4]}-{target_date[4:6]}-{target_date[6:8]}')" # 格式 YYYY-MM-DD
    }

    headers = get_random_headers(referer='https://data.eastmoney.com/')

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        data = resp.json()
        
        if not data.get('result') or not data['result'].get('data'):
            return f"📅 {target_date} 龙虎榜数据尚未生成或无数据"
        
        lhb_list = data['result']['data']
        result_lines = []
        
        result_lines.append(f"📅 日期: {target_date} (按主力净买入排序)")
        
        for stock in lhb_list:
            name = stock['SECURITY_NAME_ABBR']
            code = stock['SECURITY_CODE']
            reason = stock['EXPLANATION']
            if not reason: reason = "未知原因"
            
            # 简化上榜原因 (去噪)
            if "日涨幅" in reason: reason = "涨停"
            elif "日跌幅" in reason: reason = "跌停"
            elif "换手率" in reason: reason = "高换手"
            
            # 核心资金数据
            net_buy = stock['JMR'] if stock['JMR'] else 0 # 净买入
            inst_buy = stock['JGMMR'] if stock['JGMMR'] else 0 # 机构买入
            inst_sell = stock['JGMMC'] if stock['JGMMC'] else 0 # 机构卖出
            net_inst = inst_buy - inst_sell # 机构净买入
            
            # 过滤掉净买入太小的杂毛 (例如少于1000万的)
            if net_buy < 10000000: 
                continue

            # 图标逻辑
            icon = "💰"
            info_str = ""
            
            # 1. 机构大买判定 (Smart Money)
            if net_inst > 20000000: # 机构净买超2000万
                icon = "🏦" # 机构票
                info_str = f"机构净买{format_money(net_inst)}"
            
            # 2. 游资/主力大买判定
            elif net_buy > 50000000: # 主力净买超5000万
                icon = "🚀" # 游资大票
                info_str = f"主力净买{format_money(net_buy)}"
            else:
                info_str = f"净买{format_money(net_buy)}"

            # 格式化输出
            # 🚀 飞南资源(301500): 涨停 | 主力净买1.2亿
            line = f"{icon} {name}({code}): {reason} | {info_str}"
            result_lines.append(line)
            
            if len(result_lines) >= 8: # 最多显示8条精华
                break
        
        if len(result_lines) == 1:
            return f"📅 {target_date} 龙虎榜无主力大额净买入"
            
        return "\n".join(result_lines)

    except Exception as e:
        print(f"龙虎榜获取异常: {e}")
        # 兜底返回，不要让程序崩
        return "龙虎榜数据暂时不可用"

def check_my_portfolio():
    """
    4. 持仓哨兵 (增强版)
    核心修复：解决 '未知' 股票bug，增加API请求节流
    """
    my_stocks = load_my_stocks() 
    print(f"正在巡查持仓 ({len(my_stocks)} 只)...")
    
    if not my_stocks:
        return {"stocks": [], "summary": {"message": "暂无持仓监控"}}

    # 1. 批量获取实时行情
    realtime_data = get_stocks_realtime_sina(my_stocks)
    
    # 2. 构建智能映射表 (解决 600089 vs sh600089 不匹配问题)
    # 将 key 统一处理为 6位数字，确保能查到
    stock_map = {}
    for s in realtime_data:
        # 提取纯数字代码: sh600089 -> 600089
        pure_code = re.sub(r"\D", "", s['code'])
        stock_map[pure_code] = s
    
    portfolio_list = []
    up_count, down_count, flat_count = 0, 0, 0
    danger_alerts = []
    
    for raw_code in my_stocks:
        try:
            # 确保 loop 中的 code 也是 6位纯数字
            code_6 = str(raw_code).strip()
            
            # 从 map 中查找
            stock_rt = stock_map.get(code_6, {})
            
            # 如果没取到数据 (可能停牌或代码错误)
            if not stock_rt:
                # 尝试再次模糊查找 (防止文件里存的是 sh600089)
                raw_pure = re.sub(r"\D", "", str(raw_code))
                stock_rt = stock_map.get(raw_pure, {})
            
            # 提取基础数据
            name = stock_rt.get('name', f"未知({code_6})")
            price = stock_rt.get('price', 0)
            pct = stock_rt.get('change_pct', 0)
            
            # 详细技术分析
            tech_analysis = {}
            advice = "持有"
            
            # 只对有价格的股票做技术分析
            if price > 0:
                try:
                    # 🔥 关键：增加延时，防止 Akshare 封 IP
                    time.sleep(0.3)
                    
                    # 确保传给 Akshare 的是 6位代码
                    hist = ak.stock_zh_a_hist(symbol=code_6, period="daily", adjust="qfq")
                    tech = calculate_technical_indicators(hist)
                    
                    if tech:
                        tech_analysis = tech
                        score = tech['trend_score']
                        rsi = tech['rsi6']
                        signals = tech.get('signals', [])
                        
                        # 简单的策略逻辑
                        if score >= 4: advice = "💪 强势持有"
                        elif score <= -2: advice = "⚠️ 破位减仓"
                        elif rsi > 85: advice = "🛑 超买止盈"
                        elif rsi < 15: advice = "🛒 超卖反弹"
                        elif "放量" in str(signals) and pct > 0: advice = "📈 加仓做T"
                        elif pct < -3: advice = "🛡️ 防守观察"
                except Exception as e:
                    print(f"    持仓分析出错 {code_6}: {e}")
                    pass

            item = {
                "name": name,
                "code": code_6,
                "price": price,
                "change_pct": pct,
                "technical": tech_analysis,
                "advice": advice
            }
            portfolio_list.append(item)
            
            # 统计涨跌
            if pct > 0: up_count += 1
            elif pct < 0: down_count += 1
            else: flat_count += 1
            
            # 生成预警
            # 跌幅 > 4% 或 评分极低
            rating_score = tech_analysis.get('rating_score', 50)
            if pct < -4 or rating_score < 30:
                danger_alerts.append(f"{name} 走势恶化 (跌{pct}%)")
                
            print(f"  -> 持仓扫描: {name} {pct}% [{advice}]")
            
        except Exception as e:
            print(f"  -> {raw_code} 严重错误: {e}")
            continue
            
    # 生成总结
    if up_count == 0 and down_count == 0:
        suggestion = "数据异常或休市"
    elif down_count > up_count * 2:
        suggestion = "📉 账户亏损效应显著，建议控仓防守"
    elif up_count > down_count:
        suggestion = "📈 持仓赚钱效应不错，去弱留强"
    else:
        suggestion = "⚖️ 多空平衡，观察核心标的"

    summary = {
        "total": len(portfolio_list),
        "up_count": up_count, 
        "down_count": down_count,
        "danger_alerts": danger_alerts,
        "has_danger": len(danger_alerts) > 0,
        "strategy_suggestion": suggestion
    }

    return {"stocks": portfolio_list, "summary": summary}


# 新闻关键词配置 (Pro增强版)
# 新闻关键词配置 (Pro增强版 - 2026适配)
NEWS_KEYWORDS = {
    "high_priority": [
        # 1. 重大政策/宏观 (A股发动机)
        "新质生产力", "央行", "降息", "降准", "国常会", "证监会", "财政部", "发改委",
        "利好", "重磅", "突发", "万亿", "特别国债", "市值管理", "耐心资本", "以旧换新",
        # 2. 市场情绪/资金
        "暴涨", "暴跌", "涨停", "跌停", "龙虎榜", "净流入", "主力", "爆仓", "清盘", "回购", "增持",
        # 3. 硬核科技 (AI & 具身智能)
        "具身智能", "人形机器人", "端侧AI", "算力芯片", "智算中心", "英伟达", "华为", "鸿蒙", 
        "HBM", "CPO", "光模块", "液冷", "量子计算", "脑机接口", "AGI", "大模型",
        # 4. 新能源/新材料 (新技术路径)
        "固态电池", "钙钛矿", "可控核聚变", "氢能", "虚拟电厂", "特高压", "超导", "PEEK材料",
        # 5. 热门赛道 (低空/自动驾驶)
        "低空经济", "eVTOL", "飞行汽车", "无人驾驶", "FSD", "车路云", "商业航天", "卫星互联网"
    ],
    
    "medium_priority": [
        # 财报与经营
        "业绩", "预增", "扭亏", "分红", "高送转", "中标", "订单", "签约", "重组", "并购",
        "举牌", "解禁", "减持", "股权转让", "实控人变更",
        # 传统行业动态
        "涨价", "去库存", "产能", "出海", "一带一路", "中特估", "国企改革"
    ],
    
    "filter_out": [
        # 垃圾信息过滤 (更严格)
        "招聘", "诚聘", "招人", "岗位", "内推", 
        "广告", "特惠", "促销", "立减", "免费领", "抽奖", "中奖", 
        "讲座", "课程", "培训", "直播预告", "回放", "报名", 
        "客服", "投诉", "骗局", "谣言"
    ]
}

def get_latest_news(limit=20):
    """5. 获取新闻 (以财联社为主源) - 【纯净修正版】"""
    print("正在抓取多源新闻...")
    all_news = []
    
    # 1. 财联社 (主源 - 更稳定)
    for attempt in range(MAX_RETRIES):
        try:
            # 增加超时处理，防止 akshare 内部卡死
            news_df = ak.stock_info_global_cls()
            if news_df is not None and not news_df.empty:
                for _, row in news_df.head(30).iterrows():
                    title = str(row.get('标题', row.get('title', '')))
                    time_str = str(row.get('发布时间', row.get('time', '')))
                    # 兼容：有时标题为空但内容有值
                    content = str(row.get('内容', ''))
                    final_title = title if len(title) > 5 else content[:50]

                    if final_title:
                        all_news.append({"source": "财联社", "time": time_str, "title": final_title.strip()})
                print(f"  -> 财联社: {len(all_news)}条")
                break # 成功即退出重试
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                print(f"  -> 财联社获取失败: {e}")
    
    # 2. 东财快讯 (备用 - 仅当主源不足时启动)
    if len(all_news) < 10:
        try:
            url = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
            params = {"client": "web", "biz": "web_724", "fastColumn": "102", "pageSize": 50}
            headers = get_random_headers(referer='https://kuaixun.eastmoney.com/')
            resp = requests.get(url, params=params, headers=headers, timeout=5)
            data = resp.json()
            if data.get("data") and data["data"].get("fastNewsList"):
                for n in data["data"]["fastNewsList"]:
                    # 兼容东财的字段
                    t = n.get("title", "")
                    if not t: t = n.get("summary", "")[:50]
                    
                    if t:
                        all_news.append({"source": "东财", "time": n.get("showTime", ""), "title": t.strip()})
                print(f"  -> 东财快讯: {len(data['data']['fastNewsList'])}条")
        except Exception as e:
            print(f"  -> 东财快讯失败: {e}")
    
    # 3. 过滤与排序 (使用全局 NEWS_KEYWORDS)
    seen_titles = set()
    latest_news = []
    high_count = 0
    
    for item in all_news:
        title = item.get("title", "")
        
        # 【修正】使用全标题去重，原代码 title[:10] 容易误杀相似新闻
        if not title or title in seen_titles: 
            continue
        
        # 直接使用全局变量 NEWS_KEYWORDS
        if any(kw in title for kw in NEWS_KEYWORDS["filter_out"]): 
            continue
        
        seen_titles.add(title) # 记录全标题
        
        is_high = any(kw in title for kw in NEWS_KEYWORDS["high_priority"])
        relevance = "high" if is_high else "low"
        if is_high:
            high_count += 1
            
        latest_news.append({**item, "relevance": relevance})
    
    # 优先显示高相关性新闻
    latest_news.sort(key=lambda x: 0 if x["relevance"] == "high" else 1)
    
    return {
        "items": latest_news[:limit], 
        "summary": {
            "total": len(latest_news),
            "high_relevance": high_count
        }
    }

def save_to_history_csv(data):
    """6. 保存历史记录 - 【补充了核心指标】"""
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        
        # 提取 sentiment，增加容错
        sentiment = data.get("market_sentiment", {})
        
        row = {
            "日期": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "上证指数": sentiment.get("index_value", 0),
            "大盘涨跌%": sentiment.get("change_pct", 0),
            # 【优化点】既然算出来了，就存下来，不增加额外开销，但对复盘很有用
            "市场温度": sentiment.get("market_temperature", "-"),
            "风险评分": sentiment.get("risk_score", 0)
        }
        
        df = pd.DataFrame([row])
        
        if not os.path.exists(HISTORY_FILE):
            # 第一次写入，带表头
            df.to_csv(HISTORY_FILE, index=False, encoding='utf_8_sig')
        else:
            # 后续追加，不带表头
            df.to_csv(HISTORY_FILE, mode='a', header=False, index=False, encoding='utf_8_sig')
            
        print(f"✅ 历史数据已归档至: {HISTORY_FILE}")
        
    except Exception as e:
        print(f"❌ 历史保存失败: {e}")

def generate_ai_report_text(data):
    """
    【核心】生成预格式化的AI报告文本
    修正点：修复了板块分类逻辑 Bug，利用 'source' 字段和 'heat_score' 进行智能排序
    """
    lines = []
    
    # === 系统指令 (System Prompt) - 暗中给AI植入人设 ===
    lines.append("【指令】你是资深A股交易员。请根据以下实时数据，分析市场情绪，点评持仓风险，并给出明确的操作策略。语言风格要犀利、简练，拒绝模棱两可。")
    lines.append("")
    
    lines.append(f"# A股实时行情数据报告")
    lines.append(f"生成时间: {data['timestamp']}")
    lines.append("")
    
    # === 1. 大盘情绪 ===
    sentiment = data.get('market_sentiment', {})
    lines.append(f"## 📊 大盘概况")
    lines.append(f"- 上证指数: {sentiment.get('index_value', 0)}")
    lines.append(f"- 涨跌幅: {sentiment.get('change_pct', 0)}%")
    lines.append(f"- 市场温度: {sentiment.get('market_temperature', '未知')}")
    lines.append(f"- 风险等级: {sentiment.get('risk_level', '未知')}")
    lines.append(f"- 操作建议: {sentiment.get('suggested_action', '未知')}")
    
    # 增加涨跌家数概览，让AI判断赚钱效应
    up_ratio = sentiment.get('up_ratio', 50)
    lines.append(f"- 赚钱效应: {up_ratio}% (上涨家数占比)")
    lines.append("")

    # === 2. 持仓监控 ===
    my_portfolio = data.get('my_portfolio', {})
    my_stocks = my_portfolio.get('stocks', [])
    summary = my_portfolio.get('summary', {})
    
    lines.append(f"## 👮 持仓监控哨兵")
    if my_stocks:
        lines.append(f"总体建议: {summary.get('strategy_suggestion', '暂无')}")
        if summary.get('has_danger'):
            lines.append(f"⚠️ 预警: {', '.join(summary.get('danger_alerts', []))}")
        
        lines.append("")
        lines.append("| 代码 | 名称 | 现价 | 涨跌幅 | 评级 | 建议 |")
        lines.append("|---|---|---|---|---|---|")
        
        for stock in my_stocks:
            tech = stock.get('technical', {})
            rec = tech.get('rating_label', '⚪')
            advice = stock.get('advice', '持有')
            
            # 增加 RSI 显示，让 AI 知道是超买还是超卖
            rsi = tech.get('rsi6', 50)
            
            lines.append(f"| {stock['code']} | {stock['name']} | {stock['price']} | {stock['change_pct']}% | {rec} | {advice} (RSI:{rsi}) |")
    else:
        lines.append("（暂无持仓数据，请确保 my_stocks.txt 已配置）")
    lines.append("")
    
    # === 3. 热点板块 (逻辑深度修复) ===
    # 你的需求：优先科技 > 强题材 > 传统
    sectors = data.get('hot_sectors', [])
    
    # 1. 科技/政策 (根据 source 字段判断，而不是名字)
    tech_sectors = [s for s in sectors if s.get('source') == 'tech_policy']
    
    # 2. 其他板块 (新浪/同花顺)
    other_sectors = [s for s in sectors if s.get('source') != 'tech_policy']
    
    # 排序：内部按 heat_score (热度分) 降序
    tech_sectors.sort(key=lambda x: x.get('heat_score', 0), reverse=True)
    other_sectors.sort(key=lambda x: x.get('heat_score', 0), reverse=True)
    
    # 合并：优先展示所有科技，然后是热度高的其他板块
    # 如果没有科技板块（比如API挂了），就只展示其他的
    if tech_sectors:
        # 展示前3个科技 + 前3个其他
        sorted_sectors = tech_sectors[:3] + other_sectors[:5]
    else:
        # 只有其他，展示前8个
        sorted_sectors = other_sectors[:8]
    
    lines.append(f"## 🔥 热点板块掘金")
    
    if not sorted_sectors:
        lines.append("（今日市场极端低迷或数据获取未命中，暂无热点）")
    
    for i, sector in enumerate(sorted_sectors, 1):
        sector_name = sector.get('name', '未知')
        sector_pct = sector.get('change_pct', 0)
        heat = sector.get('heat_score', 0)
        
        # 标题增加热度标识
        icon = "🚀" if sector.get('source') == 'tech_policy' else "🔥"
        lines.append(f"### {icon} [板块{i}] {sector_name} (涨幅 {sector_pct}%, 热度 {heat})")
        lines.append("| 角色 | 代码 | 名称 | 涨幅 | 评级 | 核心点评 |")
        lines.append("|---|---|---|---|---|---|")
        
        stocks = sector.get('leading_stocks', [])
        # 展示前 5 只龙头
        for idx, stock in enumerate(stocks[:5]):
            code = stock.get('code', '?')
            name = stock.get('name', '?')
            pct = stock.get('change_pct', 0)
            
            # 角色分配逻辑
            if idx == 0: role = "👑龙一"
            elif idx == 1: role = "⚔️龙二"
            elif idx == 2: role = "🛡️中军"
            else: role = "⚡跟风"
            
            # 评级与点评
            tech = stock.get('technical', {})
            rec = stock.get('recommendation', '⚪')
            
            # 组合点评信息：趋势 + 量能 + 信号
            # 例如: "多头排列 | 放量"
            signals = tech.get('signals', [])
            comment_parts = []
            if tech.get('trend_score', 0) >= 3: comment_parts.append("主升")
            if "放量" in signals: comment_parts.append("放量")
            if "金叉" in signals: comment_parts.append("金叉")
            if "超买" in tech.get('risks', []): comment_parts.append("超买")
            
            comment = " ".join(comment_parts) if comment_parts else "跟随"
            
            lines.append(f"| {role} | {code} | {name} | {pct}% | {rec} | {comment} |")
        
        lines.append("")
    
    # === 4. 龙虎榜 ===
    lines.append("## 🐯 龙虎榜摘要")
    lhb_data = data.get('dragon_tiger', '暂无数据')
    lines.append(lhb_data)
    lines.append("")
    
    # === 5. 新闻 ===
    lines.append("## 📰 重要消息")
    news = data.get('news_brief', {})
    items = news.get('items', [])
    
    if items:
        # 分离高优和普通，确保高优在最前
        high_prio = [n for n in items if n.get('relevance') == 'high']
        normal_prio = [n for n in items if n.get('relevance') != 'high']
        
        display_news = high_prio + normal_prio
        
        for item in display_news[:10]: # 展示前10条
            icon = "🔥" if item.get('relevance') == 'high' else "•"
            title = item.get('title', '').replace('\n', ' ') # 去除换行符保持整洁
            lines.append(f"{icon} {title}")
    else:
        lines.append("（暂无重要市场新闻）")
    
    return "\n".join(lines)

# ==========================================
# 🏁 主程序入口
# ==========================================
# def main():
#     print("="*50)
#     print("🚀 开始执行全维扫描 (稳定版 v4.0 - 科技政策增强)")
#     print("  数据源: 新浪财经 + 同花顺 + 财联社")
#     print("="*50)
    
#     sentiment = get_market_sentiment()
#     print(f"大盘: {sentiment.get('index_value')} ({sentiment.get('change_pct')}%) | {sentiment.get('market_temperature')}")
    
#     sectors = get_hot_sectors_and_stocks(top_n=8)
#     dt_list = get_dragon_tiger_list()
#     my_stocks = check_my_portfolio()
#     news = get_latest_news()

#     data = {
#         "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#         "market_sentiment": sentiment,
#         "hot_sectors": sectors,
#         "dragon_tiger": dt_list,
#         "my_portfolio": my_stocks,
#         "news_brief": news
#     }
    
#     # 【新增】生成预格式化的AI报告文本
#     ai_report = generate_ai_report_text(data)
#     data["ai_report_text"] = ai_report
    
#     # 【修改点】确保输出目录存在
#     os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
#     with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
#         json.dump(data, f, ensure_ascii=False, indent=2, default=str)
#     print(f"\n✅ JSON已保存: {OUTPUT_FILE}")
    
#     # 4. 保存 CSV (给复盘)
#     save_to_history_csv(data)
    
#     print("\n" + "="*50)
#     print("🎉 扫描完成！数据摘要:")
#     print(f"   📊 市场温度: {sentiment['market_temperature']}")
#     print(f"   📈 涨跌比: {sentiment['up_count']}:{sentiment['down_count']}")
#     print(f"   🔥 热点板块: {len(sectors)}个")
#     print(f"   📰 有效新闻: {news['summary']['total']}条 (高相关{news['summary']['high_relevance']}条)")
#     print("="*50)
    
#     # 【新增】N8N 标准输出支持
#     # 只有在使用 --std-json 参数时，才会通过 stdout 输出纯净的 JSON 数据
#     if _N8N_MODE:
#         _original_print(json.dumps(data, ensure_ascii=False, default=str))

# if __name__ == "__main__":
#     main()

# ==========================================
# 🏁 主程序入口 (生产级优化版)
# ==========================================

def main():
    # 1. 参数解析 (优雅处理 N8N 模式)
    parser = argparse.ArgumentParser(description='A股智能投研助手')
    parser.add_argument('--n8n', action='store_true', help='开启N8N自动化模式 (日志输出到stderr，仅输出JSON到stdout)')
    args = parser.parse_args()
    
    # 定义日志函数：如果是N8N模式，日志打到 stderr (不干扰 stdout 的 JSON)
    def log(*msg):
        if args.n8n:
            print(*msg, file=sys.stderr)
        else:
            print(*msg)

    # 全局异常捕获 (防止脚本崩溃导致 N8N 拿不到任何数据)
    try:
        log("="*50)
        log("🚀 开始执行全维扫描 (稳定版 v4.0 - 生产级)")
        log("  数据源: 新浪财经 + 同花顺 + 财联社")
        log("="*50)
        
        # === 核心执行流 ===
        
        # 1. 市场情绪
        sentiment = get_market_sentiment()
        log(f"大盘: {sentiment.get('index_value')} ({sentiment.get('change_pct')}%) | {sentiment.get('market_temperature')}")
        
        # 2. 热点板块
        sectors = get_hot_sectors_and_stocks(top_n=8)
        
        # 3. 龙虎榜
        dt_list = get_dragon_tiger_list()
        
        # 4. 持仓检查
        my_stocks = check_my_portfolio()
        
        # 5. 新闻获取
        news = get_latest_news()

        # 6. 数据组装
        data = {
            "status": "success", # 增加状态字段，方便前端判断
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "market_sentiment": sentiment,
            "hot_sectors": sectors,
            "dragon_tiger": dt_list,
            "my_portfolio": my_stocks,
            "news_brief": news
        }
        
        # 7. 生成 AI 提示词
        ai_report = generate_ai_report_text(data)
        data["ai_report_text"] = ai_report
        
        # 8. 文件落盘
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        log(f"\n✅ JSON数据已落地: {OUTPUT_FILE}")
        
        # 9. 历史记录存档
        save_to_history_csv(data)
        
        log("\n" + "="*50)
        log("🎉 扫描完成！摘要:")
        log(f"   📊 市场温度: {sentiment.get('market_temperature')}")
        log(f"   🔥 热点板块: {len(sectors)}个")
        log(f"   📰 有效新闻: {news['summary']['total']}条")
        log("="*50)
        
        # === N8N 专用输出 ===
        # 只有在 N8N 模式下，才向 stdout 输出纯净的 JSON
        if args.n8n:
            print(json.dumps(data, ensure_ascii=False, default=str))

    except Exception as e:
        # 🔥 熔断保护：如果发生任何未捕获异常，生成错误报告
        error_data = {
            "status": "error",
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error_msg": str(e),
            "error_type": type(e).__name__
        }
        log(f"\n❌ 脚本执行发生致命错误: {e}")
        
        # 即使报错，也输出 JSON，这样 N8N 可以根据 'status': 'error' 发送报警通知
        if args.n8n:
            print(json.dumps(error_data, ensure_ascii=False, default=str))
        
        # 退出码设为 1，告知操作系统出错了
        sys.exit(1)

if __name__ == "__main__":
    main()
