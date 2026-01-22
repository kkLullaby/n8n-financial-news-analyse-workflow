import sys
import os  # <--- 关键！补回了这个库
import json
import time
import datetime
import pandas as pd
import akshare as ak
import requests
import requests.utils

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

# 3. 备选热门股票池（当API不可用时使用，关键词匹配）
FALLBACK_HOT_STOCKS = {
    "机器人/人形机器人/具身智能": ["300024", "002527", "300775", "002747", "300124"],
    "AI芯片/AI/算力/芯片": ["002230", "603986", "603501", "688256", "002049"],
    "新能源/锂电/电池/储能": ["300750", "002594", "601012", "600438", "002466"],
    "航天军工/军工/国防/航空": ["600118", "000547", "600893", "002025", "600855"],
    "医药/生物/创新药/医疗": ["300760", "603259", "688180", "300529", "002821"],
    "白酒/消费/食品饮料": ["600519", "000858", "000568", "603369", "002304"],
    "光伏/太阳能/风电": ["601012", "688599", "002459", "300274", "300763"],
    "汽车/新能源车/特斯拉": ["002594", "601238", "000625", "600104", "002920"],
    "半导体/存储/封测": ["002371", "688396", "688008", "603290", "002049"],
    "互联网/电商/数字经济": ["300059", "002624", "002241", "603881", "300033"],
}

# ==========================================
# 🔧 工具函数
# ==========================================

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
        # 构建新浪代码格式: sh600519, sz000001
        sina_codes = []
        for code in codes:
            code = str(code).zfill(6)
            if code.startswith('6') or code.startswith('5'):
                sina_codes.append(f"sh{code}")
            else:
                sina_codes.append(f"sz{code}")
        
        url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
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
                # 提取代码和数据
                code_part = line.split('_')[-1].split('=')[0]
                data = line.split('"')[1].split(',')
                
                if len(data) >= 4:
                    name = data[0]
                    prev_close = safe_float(data[2])
                    current = safe_float(data[3])
                    pct = round((current - prev_close) / prev_close * 100, 2) if prev_close > 0 else 0
                    
                    # 提取原始6位代码
                    original_code = code_part[2:] if len(code_part) > 2 else code_part
                    
                    result.append({
                        "name": name,
                        "code": original_code,
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

def get_hot_sectors_and_stocks(top_n=8, stocks_per_sector=5):
    """2. 获取热点板块及龙头 (多源策略: 同花顺概念+新浪热门+备用池)"""
    print(f"正在扫描全市场热点板块 (每板块{stocks_per_sector}只)...")
    
    hot_sectors = []
    
    # === 方案1: 使用同花顺板块概览 + 计算实时涨跌 ===
    for attempt in range(MAX_RETRIES):
        try:
            # 获取板块列表
            boards = ak.stock_board_concept_name_ths()
            
            # 计算每个板块的涨跌幅 (通过info接口)
            board_data = []
            for idx, row in boards.head(top_n * 2).iterrows():  # 取多一些备用
                board_name = row.get('name', '')
                if not board_name or any(kw in board_name for kw in ['昨日', '连板', '首板']):
                    continue
                    
                try:
                    # 获取板块实时数据
                    info = ak.stock_board_concept_info_ths(symbol=board_name)
                    # info格式: [['今开', value], ['昨收', value], ...]
                    prev_close = 0
                    current = 0
                    for _, item in info.iterrows():
                        item_name = str(item.get('项目', ''))
                        item_value = safe_float(item.get('值', 0))
                        if '昨收' in item_name:
                            prev_close = item_value
                        elif item_name in ['最新', '现价', '收盘价']:
                            current = item_value
                    
                    if prev_close > 0 and current > 0:
                        pct = round((current - prev_close) / prev_close * 100, 2)
                    else:
                        pct = 0
                    
                    board_data.append({
                        'name': board_name,
                        'change_pct': pct
                    })
                except:
                    # info获取失败，使用0涨跌
                    board_data.append({'name': board_name, 'change_pct': 0})
                
                if len(board_data) >= top_n:
                    break
            
            # 按涨跌幅排序
            board_data.sort(key=lambda x: x['change_pct'], reverse=True)
            
            for bd in board_data[:top_n]:
                board_name = bd['name']
                board_pct = bd['change_pct']
                
                # 使用预定义龙头或新浪获取代表股
                leading_stocks = []
                
                # 尝试从备用池匹配相关板块
                matched_codes = []
                for sector_key, codes in FALLBACK_HOT_STOCKS.items():
                    if any(kw in board_name for kw in sector_key.split('/')):
                        matched_codes = codes[:stocks_per_sector]
                        break
                
                # 使用新浪获取股票实时数据
                if matched_codes:
                    leading_stocks = get_stocks_realtime_sina(matched_codes)
                
                hot_sectors.append({
                    "name": board_name,
                    "change_pct": board_pct,
                    "leading_stocks": leading_stocks
                })
                
                if leading_stocks:
                    print(f"  -> 捕获: {board_name} ({board_pct:+.2f}%) [{len(leading_stocks)}只成分股]")
                else:
                    print(f"  -> 捕获: {board_name} ({board_pct:+.2f}%)")
            
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"    同花顺板块获取失败，重试 {attempt + 1}/{MAX_RETRIES}...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"  -> 同花顺板块获取失败: {e}")
    
    # === 方案2: 使用备用股票池（如果同花顺完全失败）===
    if not hot_sectors:
        print("  -> 尝试备用方案（预定义热门股票池 + 新浪实时）...")
        for sector_key, codes in FALLBACK_HOT_STOCKS.items():
            # 使用新浪批量获取实时数据（更快）
            leading_stocks = get_stocks_realtime_sina(codes[:3])
            
            if leading_stocks:
                # 使用板块关键词的第一个作为名称
                sector_name = sector_key.split('/')[0]
                avg_pct = round(sum(s['change_pct'] for s in leading_stocks) / len(leading_stocks), 2)
                hot_sectors.append({
                    "name": sector_name,
                    "change_pct": avg_pct,
                    "leading_stocks": leading_stocks
                })
                print(f"  -> 捕获: {sector_name} ({avg_pct:+.2f}%) [{len(leading_stocks)}只]")

    if not hot_sectors:
        hot_sectors = [{
            "name": "⚠️ 数据暂不可用",
            "change_pct": 0,
            "leading_stocks": [],
            "data_status": "unavailable"
        }]
    
    return hot_sectors

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
    """4. 持仓哨兵 (增强容错)"""
    my_stocks = load_my_stocks() 
    print(f"正在巡查持仓 ({len(my_stocks)} 只)...")
    
    if not my_stocks:
        return {"stocks": [], "summary": {"message": "暂无持仓监控"}}

    all_stocks = None
    for attempt in range(2):
        try:
            all_stocks = ak.stock_zh_a_spot_em()
            break
        except:
            if attempt < 1: time.sleep(1)
    
    portfolio_list = []
    up_count, down_count, flat_count = 0, 0, 0
    danger_alerts = []
    change_sum = 0.0
    
    for code in my_stocks:
        try:
            name, price, pct, turnover = "未知", 0, 0, 0
            
            if all_stocks is not None:
                stock = all_stocks[all_stocks['代码'] == code]
                if not stock.empty:
                    stock = stock.iloc[0]
                    name = stock['名称']
                    price = safe_float(stock.get('最新价', stock.get('最新', 0)))
                    pct = safe_float(stock['涨跌幅'])
                    turnover = safe_float(stock['换手率'])
            
            # 如果全市场数据里没找到，或者获取失败，尝试单只查询
            if name == "未知":
                print(f"  -> {code} 切换到单只查询模式")
                stock_info = ak.stock_individual_info_em(symbol=code)
                name = str(stock_info[stock_info['item'] == '股票简称']['value'].values[0])
                price = safe_float(stock_info[stock_info['item'] == '最新']['value'].values[0])
                
                # 尝试获取历史数据计算涨跌（可能失败）
                try:
                    hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
                    if len(hist) >= 2:
                        # 优先使用涨跌幅列，否则手动计算
                        if '涨跌幅' in hist.columns:
                            pct = safe_float(hist.iloc[-1]['涨跌幅'])
                        else:
                            latest_close = safe_float(hist.iloc[-1]['收盘'])
                            prev_close = safe_float(hist.iloc[-2]['收盘'])
                            if prev_close > 0:
                                pct = round((latest_close - prev_close) / prev_close * 100, 2)
                        
                        if '换手率' in hist.columns:
                            turnover = safe_float(hist.iloc[-1]['换手率'])
                except Exception as hist_e:
                    print(f"    -> 历史数据暂不可用，仅显示价格")
                    # pct和turnover保持默认值0
                
                print(f"  -> {code} {name}: {price}元 {pct:+.2f}%")

            change_sum += pct
            if pct > 0.1: up_count += 1
            elif pct < -0.1: down_count += 1
            else: flat_count += 1

            # 状态判定
            status, status_text, alert_level = "hold", "🟢 持有", 0
            if pct < -4.0:
                status, status_text, alert_level = "danger", "🔴 暴跌止损", 3
                danger_alerts.append(f"{name}暴跌{pct}%")
            elif pct < -1.5 and turnover > 5:
                status, status_text, alert_level = "warning", "⚠️ 放量下杀", 2
                danger_alerts.append(f"{name}放量下跌")
            elif pct > 5.0:
                status, status_text, alert_level = "strong", "🚀 强势加速", 1
            elif pct > 2.0:
                status, status_text, alert_level = "good", "📈 上涨中", 0

            portfolio_list.append({
                "code": code, "name": name, "price": price,
                "change_pct": pct, "turnover": turnover,
                "status": status, "status_text": status_text,
                "alert_level": alert_level
            })
        
        except Exception:
            portfolio_list.append({"code": code, "name": "获取失败", "status": "error"})

    summary = {
        "total": len(my_stocks),
        "up_count": up_count, "down_count": down_count,
        "danger_alerts": danger_alerts,
        "has_danger": len(danger_alerts) > 0
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

# ==========================================
# 🏁 主程序入口
# ==========================================
def main():
    print("="*50)
    print("🚀 开始执行全维扫描 (稳定版 v3.3 - 多源防伪)")
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

if __name__ == "__main__":
    main()
