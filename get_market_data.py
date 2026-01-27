import sys
import os  # <--- 关键！补回了这个库
import json
import time
import datetime
import pandas as pd
import akshare as ak
import requests
import requests.utils
import builtins

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

# 1. 强制清理代理环境变量 (防止 ProxyError)
# 告诉 requests 库：别管系统代理，直接用网卡发请求
os.environ['NO_PROXY'] = '*'
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('all_proxy', None)

# 2. 注入全局 User-Agent (解决 RemoteDisconnected)
# 这是一个标准的 Chrome 浏览器身份标识
FAKE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Referer': 'https://www.eastmoney.com/'
}

# 3. 劫持 Session 创建，确保 akshare 内部所有请求都带上这个头
# (比修改 defaults 更彻底，防止被覆盖)
_original_session_init = requests.Session.__init__

def _patched_session_init(self, *args, **kwargs):
    _original_session_init(self, *args, **kwargs)
    self.headers.update(FAKE_HEADERS)
    # 强制禁用环境代理读取
    self.trust_env = False

requests.Session.__init__ = _patched_session_init

print("✅ 网络环境已净化，反爬虫伪装已激活 (Chrome Mode)")

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

def calculate_technical_indicators(df):
    """【升级】计算技术指标 (MA, RSI, VOL) 并生成严格评级"""
    if df is None or len(df) < 30:
        return None
        
    try:
        # 1. 均线 MA
        df['MA5'] = df['收盘'].rolling(window=5).mean()
        df['MA10'] = df['收盘'].rolling(window=10).mean()
        df['MA20'] = df['收盘'].rolling(window=20).mean()
        
        # 2. RSI (相对强弱指标)
        delta = df['收盘'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=6).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=6).mean()
        rs = gain / loss
        df['RSI6'] = 100 - (100 / (1 + rs))
        
        # 3. 趋势判定
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
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
            
        # 量价配合
        vol_mean = df['成交量'].tail(5).mean()
        vol_ratio = latest['成交量'] / vol_mean if vol_mean > 0 else 0
        
        if latest['收盘'] > prev['收盘'] and vol_ratio > 1.2:
            trend_score += 1
            signals.append("放量")
            
        # RSI分析
        rsi = latest['RSI6'] if not pd.isna(latest['RSI6']) else 50
        if rsi > 80:
            risk_warnings.append("超买")
        elif rsi < 20:
            signals.append("超卖")
            trend_score += 1 # 超卖反弹算正向
            
        # 计算综合评级
        pct = (latest['收盘'] - prev['收盘']) / prev['收盘'] * 100
        score, rating_label, rating_comment = calculate_stock_rating(pct, vol_ratio, trend_score, rsi)

        return {
            "ma5": round(latest['MA5'], 2),
            "ma20": round(latest['MA20'], 2),
            "rsi6": round(rsi, 2),
            "trend_score": trend_score,
            "signals": signals,
            "risks": risk_warnings,
            "volume_ratio": round(vol_ratio, 2),
            "rating_score": score,      # 0-100 分数
            "rating_label": rating_label, # 星级文本
            "rating_comment": rating_comment # 短评
        }
    except:
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
    """【新增】通过新浪财经HTTP API批量获取股票实时行情"""
    if not codes:
        return []
    
    try:
        # 构建新浪代码格式: sh600519, sz000001, bj83xxxx
        sina_codes = []
        for code in codes:
            code = str(code).strip()
            # 如果已经带有前缀，直接使用
            if code.startswith('sh') or code.startswith('sz') or code.startswith('bj'):
                sina_codes.append(code)
                continue
                
            code = code.zfill(6)
            if code.startswith('6') or code.startswith('5'):
                sina_codes.append(f"sh{code}")
            elif code.startswith('8') or code.startswith('4') or code.startswith('9'): # 北交所通常8/4/9开头
                sina_codes.append(f"bj{code}")
            else:
                sina_codes.append(f"sz{code}")
        
        # URL limit check? List can be long.
        list_str = ','.join(sina_codes)
        url = f"https://hq.sinajs.cn/list={list_str}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
            'Referer': 'https://finance.sina.com.cn'
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'gbk'
        
        result = []
        for line in resp.text.strip().split('\n'):
            if '="' not in line:
                continue
            try:
                # 提取代码和数据: var hq_str_bj920729="..."
                # part 1: var hq_str_bj920729
                left_part = line.split('=')[0]
                code_part = left_part.split('_')[-1] # bj920729
                
                # part 2: "..."
                right_part = line.split('"')[1]
                data = right_part.split(',')
                
                if len(data) >= 4:
                    name = data[0]
                    # 北交所和沪深的数据位置略有不同? 
                    # 沪深: [0]name, [1]open, [2]prev_close, [3]current
                    # 北交所测试: "永顺生物,9.290(open?),9.270(prev?),11.790(current?)..."
                    # 对比 SH600519: "茅台,1340(open),1337(prev),1342(curr)"
                    # 看起来是一致的: 1=开盘, 2=昨收, 3=现价
                    
                    prev_close = safe_float(data[2])
                    current = safe_float(data[3])
                    pct = round((current - prev_close) / prev_close * 100, 2) if prev_close > 0 else 0
                    
                    # 提取原始代码 (保留前缀还是去前缀? 既然全流程兼容前缀，保留可能更好，但下游可能因为位数过滤)
                    # 兼容旧逻辑: 返回6位数字? 
                    # 最好返回带前缀的 code，或者单纯数字
                    # 这里稍微保留原始请求的格式
                    
                    result.append({
                        "name": name,
                        "code": code_part, # 返回如 bj920729
                        "price": current,
                        "change_pct": pct,
                        "turnover": 0,
                        "volume_ratio": 0
                    })
            except:
                continue
        
        return result
    except Exception as e:
        print(f"    新浪实时行情失败: {e}")
        return []

# ==========================================
# 🚀 核心功能函数
# ==========================================

def get_market_sentiment():
    """1. 获取大盘情绪 + 量化指标 (使用新浪HTTP API作为主源)"""
    
    index_value = 0
    change_pct = 0
    volume = 0
    prev_close = 0
    
    # === 方案1: 直接使用新浪财经HTTP API（最稳定）===
    for attempt in range(MAX_RETRIES):
        try:
            # 新浪财经实时行情API
            sina_url = "https://hq.sinajs.cn/list=sh000001,sz399001,sz399006"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
                'Referer': 'https://finance.sina.com.cn'
            }
            resp = requests.get(sina_url, headers=headers, timeout=10)
            resp.encoding = 'gbk'
            
            # 解析上证指数: var hq_str_sh000001="上证指数,3122.4082,...,成交量,成交额,..."
            for line in resp.text.strip().split('\n'):
                if 'sh000001' in line:
                    # 提取引号内的数据
                    data = line.split('"')[1].split(',')
                    if len(data) >= 4:
                        # 格式: 名称,开盘,昨收,现价,最高,最低,买入,卖出,成交量,成交额...
                        prev_close = safe_float(data[2])
                        index_value = safe_float(data[3])
                        volume = safe_float(data[9]) if len(data) > 9 else 0
                        if prev_close > 0:
                            change_pct = round((index_value - prev_close) / prev_close * 100, 2)
                        print(f"  -> 新浪指数: {index_value} ({change_pct:+.2f}%)")
                    break
            
            if index_value > 0:
                break
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"    新浪API重试 {attempt + 1}/{MAX_RETRIES}...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"  -> 新浪API失败: {e}")
    
    # === 方案2: 备用东财接口（如果新浪失败）===
    if index_value == 0:
        for attempt in range(MAX_RETRIES):
            try:
                zh_index = ak.stock_zh_index_spot_em(symbol="上证系列指数")
                sh_index = zh_index[zh_index['名称'] == '上证指数'].iloc[0]
                index_value = safe_float(sh_index.get('最新价', sh_index.get('最新', 0)))
                change_pct = safe_float(sh_index.get('涨跌幅', 0))
                volume = safe_float(sh_index.get('成交额', 0))
                print(f"  -> 东财指数: {index_value} ({change_pct:+.2f}%)")
                break
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    print(f"  -> 东财API也失败: {e}")
    
    # === 获取涨跌家数（尝试，失败使用默认值）===
    up_count, down_count, limit_up, limit_down = 0, 0, 0, 0
    up_ratio = 50
    
    try:
        # 尝试快速获取市场宽度数据
        all_stocks = ak.stock_zh_a_spot_em()
        pct_col = '涨跌幅'
        up_count = len(all_stocks[all_stocks[pct_col] > 0])
        down_count = len(all_stocks[all_stocks[pct_col] < 0])
        limit_up = len(all_stocks[all_stocks[pct_col] >= 9.9])
        limit_down = len(all_stocks[all_stocks[pct_col] <= -9.9])
        total_count = len(all_stocks)
        up_ratio = round(up_count / total_count * 100, 1) if total_count > 0 else 50
    except:
        print("    -> 全市场统计超时，使用默认值")
        # 根据大盘涨跌估算
        if change_pct > 1:
            up_ratio = 65
        elif change_pct > 0:
            up_ratio = 55
        elif change_pct < -1:
            up_ratio = 35
        else:
            up_ratio = 45
    
    # === 量化指标计算 ===
    temp_score = change_pct * 10 + (up_ratio - 50) * 0.5
    
    if temp_score > 15: market_temperature = "🔥 极度亢奋"
    elif temp_score > 8: market_temperature = "🌡️ 偏热"
    elif temp_score > 0: market_temperature = "😊 温和"
    elif temp_score > -8: market_temperature = "😐 冷静"
    elif temp_score > -15: market_temperature = "🥶 偏冷"
    else: market_temperature = "❄️ 极度恐慌"
    
    if change_pct < -2 or limit_down > 50:
        risk_level = "🔴 高风险"
        risk_score = 3
    elif change_pct < -1 or down_count > up_count * 1.5:
        risk_level = "🟡 中等风险"
        risk_score = 2
    elif change_pct > 1 and up_count > down_count * 1.2:
        risk_level = "🟢 低风险"
        risk_score = 1
    else:
        risk_level = "⚪ 中性"
        risk_score = 1.5
    
    if risk_score >= 3: suggested_action = "🛑 减仓观望"
    elif risk_score >= 2: suggested_action = "⚠️ 谨慎操作"
    elif change_pct > 1.5 and up_ratio > 60: suggested_action = "🚀 积极参与"
    elif change_pct > 0.5: suggested_action = "👍 正常交易"
    else: suggested_action = "👀 观望为主"
    
    return {
        "index_value": index_value,
        "change_pct": change_pct,
        "volume": volume,
        "up_count": up_count,
        "down_count": down_count,
        "limit_up": limit_up,
        "limit_down": limit_down,
        "up_ratio": up_ratio,
        "market_temperature": market_temperature,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "suggested_action": suggested_action
    }

def get_stock_code_by_name(name):
    """【新增】通过新浪搜索接口，由中文名称查找股票代码"""
    try:
        url = f"http://suggest3.sinajs.cn/suggest/type=&key={name}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=3)
        resp.encoding = 'gbk'
        # content: var suggestvalue="...;601318,sh601318,中国平安,..."
        # 匹配 sh/sz/bj + 6位数字
        import re
        match = re.search(r'(sh\d{6}|sz\d{6}|bj\d{6})', resp.text)
        if match:
            return match.group(0) # 返回 sh601318
    except:
        pass
    return None

def get_tech_policy_sectors():
    """【升级】扫描科技/政策热点板块 (去除硬性推荐，改为基于表现筛选)"""
    print("正在扫描科技/政策热点...")
    tech_sectors = []
    
    for sector_key, codes in TECH_POLICY_HOT_STOCKS.items():
        leading_stocks = get_stocks_realtime_sina(codes)
        if not leading_stocks: continue
        
        # 过滤掉价格为0的
        leading_stocks = [s for s in leading_stocks if s['price'] > 0]
        if not leading_stocks: continue
            
        avg_pct = sum(s['change_pct'] for s in leading_stocks) / len(leading_stocks)
        max_pct = max(s['change_pct'] for s in leading_stocks)
        
        # 【修改】不再硬性推荐。必须板块整体上涨(>0)或者有明显龙头(>3)才纳入，否则视为弱势不推荐
        if avg_pct < 0 and max_pct < 3:
            continue
            
        # 计算每只股票的技术指标
        valid_stocks_with_rating = []
        for stock in leading_stocks:
            try:
                c6 = stock['code'][-6:] if len(stock['code']) > 6 else stock['code']
                hist = ak.stock_zh_a_hist(symbol=c6, period="daily", adjust="qfq")
                tech = calculate_technical_indicators(hist)
                if tech:
                    stock['technical'] = tech
                    # 使用算出来的评级
                    stock['recommendation'] = tech['rating_label'] 
                    valid_stocks_with_rating.append(stock)
                else:
                    stock['recommendation'] = "⚪"
                    valid_stocks_with_rating.append(stock)
            except:
                pass
        
        if not valid_stocks_with_rating:
            valid_stocks_with_rating = leading_stocks

        # 按评分降序
        valid_stocks_with_rating.sort(key=lambda x: x.get('technical', {}).get('rating_score', 0), reverse=True)

        # 稍微加分，但不再是盲目 +15
        bonus = 0
        if avg_pct > 0.5: bonus = 5 
        
        heat_score = avg_pct * 0.8 + max_pct * 0.2 + bonus
        
        sector_name = sector_key.split('/')[0]
        tech_sectors.append({
            "name": f"{sector_name}",
            "change_pct": round(avg_pct, 2),
            "heat_score": round(heat_score, 2),
            "leading_stocks": valid_stocks_with_rating,
            "source": "tech_policy"
        })
        print(f"  -> 科技热点入选: {sector_name} (均涨{avg_pct:.2f}%)")
    
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

def get_hot_sectors_and_stocks(top_n=8, stocks_per_sector=5):
    """2. 获取热点板块及龙头 (科技政策 + 同花顺题材 + 新浪行业 三源驱动)"""
    print(f"正在扫描主流热点赛道...")
    
    scanned_sectors = []
    
    # === A. 科技/政策热点扫描 (最高优先级，散户最关注) ===
    tech_sectors = get_tech_policy_sectors()
    scanned_sectors.extend(tech_sectors)
    
    # === B. 同花顺题材扫描 ===
    ths_concepts = get_hot_concepts(top_n=5)
    scanned_sectors.extend(ths_concepts)
    
    # === C. 新浪行业动态扫描 (传统行业兜底) ===
    
    try:
        # 1. 获取新浪行业涨幅榜
        sina_hy_url = "http://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
            'Referer': 'https://finance.sina.com.cn/'
        }
        resp = requests.get(sina_hy_url, headers=headers, timeout=6)
        resp.encoding = 'gbk'
        
        # 解析数据: {key:"value", ...}
        # 使用正则提取所有 key:value 对
        # value格式: 代码(new_xxx),名称,数量,均价,涨跌额,涨跌幅...
        import re
        # 兼容带引号和不带引号的Key: "new_xm" 或 new_xm
        matches = re.findall(r'(?:["\'])?([a-z0-9_]+)(?:["\'])?:"([^"]+)"', resp.text)
        
        sector_list = []
        for key, val_str in matches:
            parts = val_str.split(',')
            if len(parts) > 5:
                name = parts[1]
                avg_price = safe_float(parts[3])
                pct = safe_float(parts[5])
                total_amount = safe_float(parts[7])
                
                sector_list.append({
                    "code": key, # 板块代码，如 new_blhy
                    "name": name,
                    "change_pct": pct,
                    "amount": total_amount
                })
        
        # 按涨跌幅倒序排序，取前 top_n
        sector_list.sort(key=lambda x: x['change_pct'], reverse=True)
        top_candidates = sector_list[:top_n]
        
        if top_candidates:
            print(f"  -> 成功识别今日领涨行业: {[s['name'] for s in top_candidates]}")
        
        # 2. 深入扫描每个领涨板块的成分股
        for sector in top_candidates:
            if sector['change_pct'] < 0: # 如果连最强的板块都绿了，可能不需要深究（或者根据需求调整）
                continue
                
            # 请求板块成分股
            node_api = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
            params = {
                "page": "1", 
                "num": "12", # 【修改】扩大获取数量，确保有足够的可推荐股票
                "sort": "changepercent",
                "asc": "0",
                "node": sector['code']
            }
            
            try:
                r_node = requests.get(node_api, params=params, headers=headers, timeout=5)
                # 新浪API返回的是 JSON 数组
                node_stocks = r_node.json()
                
                leading_stocks = []
                for s in node_stocks:
                    name = s.get('name')
                    code = s.get('code') # 6位代码
                    price = safe_float(s.get('trade'))
                    pct = safe_float(s.get('changepercent'))
                    
                    # 转换结构以匹配原有逻辑
                    stock_info = {
                        "name": name,
                        "code": code,
                        "price": price,
                        "change_pct": pct,
                        "turnover": 0 # API没直接给换手率，暂置0
                    }
                    leading_stocks.append(stock_info)
                
                if not leading_stocks:
                    continue
                    
                # 计算热度分 (兼容旧逻辑)
                max_pct = max(s['change_pct'] for s in leading_stocks) if leading_stocks else 0
                heat_score = sector['change_pct'] * 0.6 + max_pct * 0.4
                
                # 【修改】为所有获取到的龙头股计算指标，不再限制前3
                valid_stocks_with_rating = []
                for stock in leading_stocks:
                    try:
                        hist = ak.stock_zh_a_hist(symbol=stock['code'], period="daily", adjust="qfq")
                        tech = calculate_technical_indicators(hist)
                        if tech:
                            stock['technical'] = tech
                            stock['recommendation'] = tech.get('rating_label', "⚪")
                            valid_stocks_with_rating.append(stock)
                        else:
                             # 如果算不出指标（如新股或停牌），给个默认
                             stock['recommendation'] = "⚪"
                             valid_stocks_with_rating.append(stock)
                    except:
                        pass
                
                # 如果计算完发现有效的太少，就用原始列表（至少显示名字）
                if not valid_stocks_with_rating:
                    valid_stocks_with_rating = leading_stocks

                # 按内部评分二次排序，确保推荐最强的
                valid_stocks_with_rating.sort(key=lambda x: x.get('technical', {}).get('rating_score', 0), reverse=True)

                scanned_sectors.append({
                    "name": sector['name'], # 行业名称
                    "change_pct": round(sector['change_pct'], 2),
                    "heat_score": round(heat_score, 2),
                    "leading_stocks": valid_stocks_with_rating[:8] # 保留前8个
                })
                print(f"  -> 扫描行业: {sector['name']} (板块涨{sector['change_pct']}%, 龙头{max_pct}%)")
                
            except Exception as e:
                print(f"    扫描板块{sector['name']}成分股失败: {e}")
                continue

    except Exception as e:
        print(f"⚠️ 动态全市场扫描失败: {e}")
        print("  ->以此为契机，回退到静态精选板块列表...")
        scanned_sectors = [] # 清空，触发下方fallback逻辑

    # === 回退/补充逻辑: 如果动态扫描结果太少，或者失败 ===
    if len(scanned_sectors) < 3:
        # 原有的静态扫描逻辑 (FALLBACK_HOT_STOCKS)
        # 仅作为补充
        print("启动备用静态板块扫描...")
        for sector_key, codes in FALLBACK_HOT_STOCKS.items():
            # (简化的防重逻辑)
            sector_name_static = sector_key.split('/')[0]
            if any(s['name'] == sector_name_static for s in scanned_sectors):
                continue
                
            leading_stocks = get_stocks_realtime_sina(codes)
            if not leading_stocks: continue
            
            avg_pct = sum(s['change_pct'] for s in leading_stocks) / len(leading_stocks)
            max_pct = max(s['change_pct'] for s in leading_stocks)
            heat_score = avg_pct * 0.6 + max_pct * 0.4
            
            if heat_score > 0.5 or max_pct > 4: # 门槛稍高一点
                # ... (原有的技术指标计算代码) ...
                for stock in leading_stocks[:3]:
                     try:
                        hist = ak.stock_zh_a_hist(symbol=stock['code'], period="daily", adjust="qfq")
                        tech = calculate_technical_indicators(hist)
                        if tech: stock['technical'] = tech
                     except: pass
                
                scanned_sectors.append({
                    "name": sector_name_static,
                    "change_pct": round(avg_pct, 2),
                    "heat_score": heat_score,
                    "leading_stocks": leading_stocks
                })
    
    # === 最终排序与输出 ===
    sector_performance = scanned_sectors
    
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

def load_my_stocks():
    if not os.path.exists(STOCK_FILE):
        return [] 
    stock_list = []
    with open(STOCK_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            code = line.strip()
            if code.isdigit() and len(code) == 6:
                stock_list.append(code)
    return list(set(stock_list)) 

def get_dragon_tiger_list():
    """3. 获取龙虎榜 (Smart Money) - 使用新浪源"""
    print("正在分析龙虎榜机构席位...")
    
    # === 方案1: 使用新浪龙虎榜（更稳定）===
    for attempt in range(MAX_RETRIES):
        try:
            lhb = ak.stock_lhb_detail_daily_sina()
            
            if lhb is None or lhb.empty:
                break  # 尝试备用方案
            
            result = []
            seen_stocks = set()
            
            for _, row in lhb.iterrows():
                # 新浪接口字段名: ['序号', '股票代码', '股票名称', '收盘价', '对应值', '成交量', '成交额', '指标']
                stock_name = row.get('股票名称', row.get('名字', '未知'))
                stock_code = str(row.get('股票代码', row.get('代码', '')))
                reason = str(row.get('指标', ''))
                
                if stock_name in seen_stocks or stock_name == '未知':
                    continue
                seen_stocks.add(stock_name)
                
                # 截断上榜原因
                if len(reason) > 35:
                    reason = reason[:35] + "..."
                
                result.append(f"- {stock_name}({stock_code}): {reason}")
                
                if len(result) >= 5:
                    break
            
            if result:
                return "\n".join(result)
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"    新浪龙虎榜重试 {attempt + 1}/{MAX_RETRIES}...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"  -> 新浪龙虎榜失败: {e}")
    
    # === 方案2: 尝试东财接口 ===
    try:
        end_date = datetime.datetime.now().strftime("%Y%m%d")
        start_date = (datetime.datetime.now() - datetime.timedelta(days=5)).strftime("%Y%m%d")
        
        lhb = ak.stock_lhb_detail_em(start_date=start_date, end_date=end_date)
        
        if lhb is not None and not lhb.empty:
            if '上榜日' in lhb.columns:
                lhb = lhb.sort_values(by='上榜日', ascending=False)
            
            result = []
            seen_stocks = set()
            
            for _, row in lhb.head(10).iterrows():
                stock_name = row.get('名称', row.get('股票名称', '未知'))
                stock_code = row.get('代码', row.get('股票代码', ''))
                
                if stock_name in seen_stocks:
                    continue
                seen_stocks.add(stock_name)
                
                reason = row.get('解读', row.get('上榜原因', ''))
                if len(reason) > 30:
                    reason = reason[:30] + "..."
                
                result.append(f"- {stock_name}({stock_code}): {reason}")
                
                if len(result) >= 5:
                    break
            
            if result:
                return "\n".join(result)
    except:
        pass
    
    return "最近暂无龙虎榜数据"

def check_my_portfolio():
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
    """5. 获取新闻 (以财联社为主源)"""
    print("正在抓取多源新闻...")
    all_news = []
    
    # 1. 财联社 (主源 - 更稳定)
    for attempt in range(MAX_RETRIES):
        try:
            news_df = ak.stock_info_global_cls()
            if news_df is not None and not news_df.empty:
                for _, row in news_df.head(30).iterrows():
                    title = str(row.get('标题', row.get('title', '')))
                    time_str = str(row.get('发布时间', row.get('time', '')))
                    if title:
                        all_news.append({"source": "财联社", "time": time_str, "title": title})
                print(f"  -> 财联社: {len(all_news)}条")
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                print(f"  -> 财联社获取失败: {e}")
    
    # 2. 东财快讯 (备用)
    if len(all_news) < 10:
        try:
            url = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
            params = {"client": "web", "biz": "web_724", "fastColumn": "102", "pageSize": 50}
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
            resp = requests.get(url, params=params, headers=headers, timeout=5)
            data = resp.json()
            if data.get("data") and data["data"].get("fastNewsList"):
                for n in data["data"]["fastNewsList"]:
                    all_news.append({"source": "东财", "time": n.get("showTime", ""), "title": n.get("title", "")})
                print(f"  -> 东财快讯: {len(data['data']['fastNewsList'])}条")
        except Exception as e:
            print(f"  -> 东财快讯失败: {e}")
    
    # 过滤与排序
    seen_titles = set()
    latest_news = []
    high_count = 0
    
    for item in all_news:
        title = item.get("title", "")
        if not title or title[:10] in seen_titles: 
            continue
        if any(kw in title for kw in NEWS_KEYWORDS["filter_out"]): 
            continue
        
        seen_titles.add(title[:10])
        is_high = any(kw in title for kw in NEWS_KEYWORDS["high_priority"])
        relevance = "high" if is_high else "low"
        if is_high:
            high_count += 1
        latest_news.append({**item, "relevance": relevance})
    
    latest_news.sort(key=lambda x: 0 if x["relevance"] == "high" else 1)
    
    return {
        "items": latest_news[:limit], 
        "summary": {
            "total": len(latest_news),
            "high_relevance": high_count
        }
    }

def save_to_history_csv(data):
    """6. 保存历史记录"""
    try:
        # 【修改点】确保目录存在
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        
        row = {
            "日期": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "上证指数": data["market_sentiment"].get("index_value", 0),
            "大盘涨跌%": data["market_sentiment"].get("change_pct", 0),
        }
        df = pd.DataFrame([row])
        if not os.path.exists(HISTORY_FILE):
            df.to_csv(HISTORY_FILE, index=False, encoding='utf_8_sig')
        else:
            df.to_csv(HISTORY_FILE, mode='a', header=False, index=False, encoding='utf_8_sig')
    except Exception as e:
        print(f"❌ 历史保存失败: {e}")

def generate_ai_report_text(data):
    """【新增】生成预格式化的AI报告文本，确保AI不会瞎编数据"""
    lines = []
    lines.append(f"# A股实时行情数据报告")
    lines.append(f"生成时间: {data['timestamp']}")
    lines.append("")
    
    # 大盘情绪
    sentiment = data.get('market_sentiment', {})
    lines.append(f"## 大盘概况")
    lines.append(f"- 上证指数: {sentiment.get('index_value', 0)}")
    lines.append(f"- 涨跌幅: {sentiment.get('change_pct', 0)}%")
    lines.append(f"- 市场温度: {sentiment.get('market_temperature', '未知')}")
    lines.append(f"- 风险等级: {sentiment.get('risk_level', '未知')}")
    lines.append(f"- 操作建议: {sentiment.get('suggested_action', '未知')}")
    lines.append("")
    
    # 热点板块 - 重新排序：优先科技 > 题材(多股) > 题材(单股) > 传统行业
    sectors = data.get('hot_sectors', [])
    
    # 分类
    tech_sectors = [s for s in sectors if '科技' in s.get('name', '')]
    concept_multi = [s for s in sectors if '题材' in s.get('name', '') and len(s.get('leading_stocks', [])) > 1]
    concept_single = [s for s in sectors if '题材' in s.get('name', '') and len(s.get('leading_stocks', [])) == 1]
    traditional = [s for s in sectors if '科技' not in s.get('name', '') and '题材' not in s.get('name', '')]
    
    # 按热度排序各类别
    tech_sectors.sort(key=lambda x: x.get('change_pct', 0), reverse=True)
    concept_multi.sort(key=lambda x: x.get('change_pct', 0), reverse=True)
    concept_single.sort(key=lambda x: x.get('change_pct', 0), reverse=True)
    traditional.sort(key=lambda x: x.get('change_pct', 0), reverse=True)
    
    # 合并：科技(2) + 题材多股(1) + 题材单股(2) + 传统(1)
    sorted_sectors = tech_sectors[:2] + concept_multi[:1] + concept_single[:2] + traditional[:1]
    
    lines.append(f"## 热点板块详情")
    
    for i, sector in enumerate(sorted_sectors[:6], 1):
        sector_name = sector.get('name', '未知')
        sector_pct = sector.get('change_pct', 0)
        lines.append(f"### 板块{i}: {sector_name} (涨幅 {sector_pct}%)")
        lines.append("")
        lines.append("| 代码 | 名称 | 现价 | 涨跌幅 | 技术信号 | 建议 |")
        lines.append("|------|------|------|--------|----------|------|")
        
        stocks = sector.get('leading_stocks', [])
        for stock in stocks[:5]:
            code = stock.get('code', '?')
            name = stock.get('name', '?')
            price = stock.get('price', 0)
            pct = stock.get('change_pct', 0)
            
            # 提取技术信号
            tech = stock.get('technical', {})
            signals = tech.get('signals', [])
            
            # 建议 (使用 星级 + 短评 的组合)
            rec = stock.get('recommendation', '⚪')
            comment = stock.get('comment', tech.get('rating_comment', ''))
            
            # 组合展示
            rec_display = f"{rec} {comment}"
            signal_str = ','.join(signals[:2]) if signals else '无'
            
            lines.append(f"| {code} | {name} | {price} | {pct}% | {signal_str} | {rec_display} |")
        
        lines.append("")
    
    # 龙虎榜
    lines.append("## 龙虎榜摘要")
    lines.append(data.get('dragon_tiger', '暂无数据'))
    lines.append("")
    
    # 新闻
    lines.append("## 重要新闻")
    news = data.get('news_brief', {})
    for item in news.get('items', [])[:5]:
        rel = "🔥" if item.get('relevance') == 'high' else ""
        lines.append(f"- {rel}{item.get('title', '')}")
    
    return "\n".join(lines)

# ==========================================
# 🏁 主程序入口
# ==========================================
def main():
    print("="*50)
    print("🚀 开始执行全维扫描 (稳定版 v4.0 - 科技政策增强)")
    print("  数据源: 新浪财经 + 同花顺 + 财联社")
    print("="*50)
    
    sentiment = get_market_sentiment()
    print(f"大盘: {sentiment.get('index_value')} ({sentiment.get('change_pct')}%) | {sentiment.get('market_temperature')}")
    
    sectors = get_hot_sectors_and_stocks(top_n=8)
    dt_list = get_dragon_tiger_list()
    my_stocks = check_my_portfolio()
    news = get_latest_news()

    data = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "market_sentiment": sentiment,
        "hot_sectors": sectors,
        "dragon_tiger": dt_list,
        "my_portfolio": my_stocks,
        "news_brief": news
    }
    
    # 【新增】生成预格式化的AI报告文本
    ai_report = generate_ai_report_text(data)
    data["ai_report_text"] = ai_report
    
    # 【修改点】确保输出目录存在
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n✅ JSON已保存: {OUTPUT_FILE}")
    
    # 4. 保存 CSV (给复盘)
    save_to_history_csv(data)
    
    print("\n" + "="*50)
    print("🎉 扫描完成！数据摘要:")
    print(f"   📊 市场温度: {sentiment['market_temperature']}")
    print(f"   📈 涨跌比: {sentiment['up_count']}:{sentiment['down_count']}")
    print(f"   🔥 热点板块: {len(sectors)}个")
    print(f"   📰 有效新闻: {news['summary']['total']}条 (高相关{news['summary']['high_relevance']}条)")
    print("="*50)
    
    # 【新增】N8N 标准输出支持
    # 只有在使用 --std-json 参数时，才会通过 stdout 输出纯净的 JSON 数据
    if _N8N_MODE:
        _original_print(json.dumps(data, ensure_ascii=False, default=str))

if __name__ == "__main__":
    main()
