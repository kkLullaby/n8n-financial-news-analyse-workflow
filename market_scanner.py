import akshare as ak
import pandas as pd
import json
import datetime
import os

# ==========================================
# ⚙️ 用户配置区域
# ==========================================

# 1. 你的持仓清单 (在此处手动修改，暂时代替飞书动态传入)
# 格式：["代码1", "代码2"]，代码必须是 6位数字

# 2. 文件保存路径
OUTPUT_FILE = "/home/kk/n8n/market_data.json"
HISTORY_FILE = "/home/kk/n8n/history_data.csv"
STOCK_FILE = "/home/kk/n8n/my_stocks.txt"
# ==========================================
# 🚀 核心功能函数
# ==========================================

def get_market_sentiment():
    """1. 获取大盘情绪 + 量化指标"""
    try:
        zh_index = ak.stock_zh_index_spot_em(symbol="上证系列指数")
        sh_index = zh_index[zh_index['名称'] == '上证指数'].iloc[0]
        
        index_value = float(sh_index['最新价'])
        change_pct = float(sh_index['涨跌幅'])
        volume = float(sh_index['成交额'])
        
        # 获取涨跌家数用于计算市场宽度
        try:
            all_stocks = ak.stock_zh_a_spot_em()
            up_count = len(all_stocks[all_stocks['涨跌幅'] > 0])
            down_count = len(all_stocks[all_stocks['涨跌幅'] < 0])
            limit_up = len(all_stocks[all_stocks['涨跌幅'] >= 9.9])
            limit_down = len(all_stocks[all_stocks['涨跌幅'] <= -9.9])
            total_count = len(all_stocks)
            up_ratio = round(up_count / total_count * 100, 1) if total_count > 0 else 50
        except:
            up_count, down_count, limit_up, limit_down = 0, 0, 0, 0
            up_ratio = 50
        
        # === 量化指标计算 ===
        # 1. 市场温度 (综合涨跌幅和上涨比例)
        temp_score = change_pct * 10 + (up_ratio - 50) * 0.5
        if temp_score > 15:
            market_temperature = "🔥 极度亢奋"
        elif temp_score > 8:
            market_temperature = "🌡️ 偏热"
        elif temp_score > 0:
            market_temperature = "😊 温和"
        elif temp_score > -8:
            market_temperature = "😐 冷静"
        elif temp_score > -15:
            market_temperature = "🥶 偏冷"
        else:
            market_temperature = "❄️ 极度恐慌"
        
        # 2. 风险等级
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
        
        # 3. 操作建议
        if risk_score >= 3:
            suggested_action = "🛑 减仓观望"
        elif risk_score >= 2:
            suggested_action = "⚠️ 谨慎操作"
        elif change_pct > 1.5 and up_ratio > 60:
            suggested_action = "🚀 积极参与"
        elif change_pct > 0.5:
            suggested_action = "👍 正常交易"
        else:
            suggested_action = "👀 观望为主"
        
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
    except Exception as e:
        print(f"市场情绪获取失败: {e}")
        return {
            "index_value": 0, "change_pct": 0, "volume": 0,
            "up_count": 0, "down_count": 0, "limit_up": 0, "limit_down": 0,
            "up_ratio": 50, "market_temperature": "❓ 未知",
            "risk_level": "⚪ 未知", "risk_score": 2, "suggested_action": "👀 观望为主"
        }

def get_hot_sectors_and_stocks(top_n=8, stocks_per_sector=5):
    """2. 获取热点板块及龙头 (每板块返回stocks_per_sector只股票)"""
    print(f"正在扫描全市场热点板块 (每板块{stocks_per_sector}只)...")
    try:
        boards = ak.stock_board_concept_name_em()
        top_boards = boards.sort_values(by='涨跌幅', ascending=False).head(top_n)
        
        hot_sectors = []
        for _, row in top_boards.iterrows():
            board_name = row['板块名称']
            
            # 找领涨的前N名个股
            cons = ak.stock_board_concept_cons_em(symbol=board_name)
            leading_cons = cons.sort_values(by='涨跌幅', ascending=False).head(stocks_per_sector)
            
            leading_stocks = []
            for _, stock in leading_cons.iterrows():
                leading_stocks.append({
                    "name": stock['名称'],
                    "code": str(stock['代码']),
                    "price": float(stock['最新价']),
                    "change_pct": float(stock['涨跌幅']),
                    "turnover": float(stock['换手率']),
                    "volume_ratio": float(stock['量比']) if '量比' in stock else 0
                })
            
            hot_sectors.append({
                "name": board_name,
                "change_pct": float(row['涨跌幅']),
                "leading_stocks": leading_stocks
            })
            print(f"  -> 捕获: {board_name} (+{row['涨跌幅']}%)")
            
        return hot_sectors
    except Exception as e:
        print(f"板块获取失败: {e}")
        return []

def load_my_stocks():
    if not os.path.exists(STOCK_FILE):
        return [] # 如果文件不存在，返回空

    stock_list = []
    with open(STOCK_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            code = line.strip()
            # 简单的过滤：只保留6位数字
            if code.isdigit() and len(code) == 6:
                stock_list.append(code)
    return list(set(stock_list)) # 去重

def get_dragon_tiger_list():
    """3. 获取龙虎榜 (Smart Money)"""
    print("正在分析龙虎榜机构席位...")
    try:
        today = datetime.datetime.now().strftime("%Y%m%d")
        lhb = ak.stock_lhb_detail_daily(date=today)
        
        if lhb is None or lhb.empty:
            return "今日暂无龙虎榜数据或休市"

        # 计算净买入
        lhb['净买入额'] = lhb['买入额'] - lhb['卖出额']
        top_inst = lhb.sort_values(by='净买入额', ascending=False).head(5)
        
        result = []
        for _, row in top_inst.iterrows():
            stock_name = row['股票名称']
            net_buy = row['净买入额'] / 10000 
            result.append(f"- {stock_name}: 主力净买入 {int(net_buy)} 万")
            
        return "\n".join(result)
    except Exception as e:
        # print(f"龙虎榜获取失败: {e}") 
        return "盘中暂无龙虎榜数据"

def check_my_portfolio():
    """
    4. 【核心新增】持仓哨兵 (动态读取版)
    扫描 my_stocks.txt 中的列表
    返回结构化数据：{ "stocks": [...], "summary": {...} }
    """
    my_stocks = load_my_stocks() 
    
    print(f"正在巡查持仓 ({len(my_stocks)} 只)...")
    
    if not my_stocks:
        return {
            "stocks": [],
            "summary": {
                "total": 0,
                "message": "暂无持仓监控 (请检查 my_stocks.txt)"
            }
        }

    try:
        all_stocks = ak.stock_zh_a_spot_em()
        
        portfolio_list = []
        up_count = 0
        down_count = 0
        flat_count = 0
        danger_alerts = []
        change_sum = 0.0
        
        for code in my_stocks:
            stock = all_stocks[all_stocks['代码'] == code]

            if stock.empty:
                portfolio_list.append({
                    "code": code,
                    "name": "未知",
                    "price": 0,
                    "change_pct": 0,
                    "turnover": 0,
                    "status": "error",
                    "status_text": "❓ 未找到数据",
                    "alert_level": 0
                })
                continue

            stock = stock.iloc[0]
            name = stock['名称']
            price = float(stock['最新价'])
            pct = float(stock['涨跌幅'])
            turnover = float(stock['换手率'])
            
            change_sum += pct
            
            # 统计涨跌
            if pct > 0.1:
                up_count += 1
            elif pct < -0.1:
                down_count += 1
            else:
                flat_count += 1

            # --- 风控逻辑 & 状态判定 ---
            status = "hold"
            status_text = "🟢 持有"
            alert_level = 0  # 0=正常, 1=关注, 2=警告, 3=危险

            if pct < -4.0:
                status = "danger"
                status_text = "🔴 暴跌止损警报"
                alert_level = 3
                danger_alerts.append(f"{name}暴跌{pct}%")
            elif pct < -1.5 and turnover > 5:
                status = "warning"
                status_text = "⚠️ 放量下杀"
                alert_level = 2
                danger_alerts.append(f"{name}放量下跌")
            elif pct > 5.0:
                status = "strong"
                status_text = "🚀 强势加速"
                alert_level = 1
            elif pct > 2.0:
                status = "good"
                status_text = "📈 上涨中"
                alert_level = 0

            # 计算角色标签
            role = "跟风"
            if turnover > 10 and pct > 3:
                role = "龙头"
            elif turnover > 5 and pct > 0:
                role = "跟风"
            else:
                role = "观察"
            
            # 资金状态
            if turnover > 8:
                fund_status = "放量突破" if pct > 2 else "放量加速"
            elif turnover > 4:
                fund_status = "量能活跃"
            else:
                fund_status = "缩量整理"

            portfolio_list.append({
                "code": code,
                "name": name,
                "price": price,
                "change_pct": pct,
                "turnover": turnover,
                "status": status,
                "status_text": status_text,
                "alert_level": alert_level,
                "role": role,
                "fund_status": fund_status
            })

        # 找出最强和最弱
        valid_stocks = [s for s in portfolio_list if s["status"] != "error"]
        if valid_stocks:
            strongest = max(valid_stocks, key=lambda x: x["change_pct"])
            weakest = min(valid_stocks, key=lambda x: x["change_pct"])
            avg_change = round(change_sum / len(valid_stocks), 2)
        else:
            strongest = weakest = {"name": "无", "change_pct": 0}
            avg_change = 0

        # 汇总数据
        summary = {
            "total": len(my_stocks),
            "up_count": up_count,
            "down_count": down_count,
            "flat_count": flat_count,
            "avg_change": avg_change,
            "strongest": f"{strongest['name']} ({strongest['change_pct']}%)",
            "weakest": f"{weakest['name']} ({weakest['change_pct']}%)",
            "danger_alerts": danger_alerts,
            "has_danger": len(danger_alerts) > 0
        }

        return {
            "stocks": portfolio_list,
            "summary": summary
        }

    except Exception as e:
        print(f"持仓扫描出错: {e}")
        return {
            "stocks": [],
            "summary": {
                "total": 0,
                "message": f"持仓数据暂时无法获取: {str(e)}"
            }
        }
# 新闻关键词配置
NEWS_KEYWORDS = {
    "high_priority": ["央行", "降息", "降准", "利好", "重磅", "突发", "紧急", "暴涨", "暴跌", "涨停", "跌停",
                      "芯片", "半导体", "AI", "人工智能", "机器人", "新能源", "光伏", "锂电", "华为", "特斯拉"],
    "medium_priority": ["业绩", "营收", "利润", "增长", "下滑", "政策", "规划", "投资", "并购", "回购",
                        "医药", "消费", "金融", "地产", "基建"],
    "filter_out": ["招聘", "广告", "活动", "会议", "论坛", "培训"]
}

def get_latest_news(limit=15):
    """5. 获取新闻 (带质量过滤和相关性标签)"""
    print("正在抓取电报 (质量过滤模式)...")
    try:
        news_df = ak.stock_info_global_cls()
        latest_news = []
        processed_count = 0
        
        for _, row in news_df.iterrows():
            if processed_count >= limit:
                break
                
            pub_time = str(row['发布时间']) if '发布时间' in row else ""
            title = str(row['标题']) if '标题' in row else ""
            
            # === 质量过滤 ===
            # 1. 过滤空标题
            if not title or title.strip() == "" or len(title) < 5:
                continue
            
            # 2. 过滤垃圾内容
            if any(kw in title for kw in NEWS_KEYWORDS["filter_out"]):
                continue
            
            # === 相关性评分 ===
            relevance = "low"
            relevance_icon = "📰"
            
            # 高优先级关键词
            if any(kw in title for kw in NEWS_KEYWORDS["high_priority"]):
                relevance = "high"
                relevance_icon = "🔥"
            # 中优先级关键词
            elif any(kw in title for kw in NEWS_KEYWORDS["medium_priority"]):
                relevance = "medium"
                relevance_icon = "📌"
            
            latest_news.append({
                "time": pub_time,
                "title": title,
                "relevance": relevance,
                "relevance_icon": relevance_icon
            })
            processed_count += 1
        
        # 按相关性排序：高优先 > 中优先 > 低优先
        relevance_order = {"high": 0, "medium": 1, "low": 2}
        latest_news.sort(key=lambda x: relevance_order.get(x["relevance"], 2))
        
        # 统计
        high_count = len([n for n in latest_news if n["relevance"] == "high"])
        medium_count = len([n for n in latest_news if n["relevance"] == "medium"])
        print(f"  -> 新闻过滤完成: {len(latest_news)}条 (🔥高相关{high_count} | 📌中相关{medium_count})")
        
        return {
            "items": latest_news,
            "summary": {
                "total": len(latest_news),
                "high_relevance": high_count,
                "medium_relevance": medium_count,
                "low_relevance": len(latest_news) - high_count - medium_count
            }
        }
    except Exception as e:
        print(f"新闻获取失败: {e}")
        return {
            "items": [],
            "summary": {"total": 0, "high_relevance": 0, "medium_relevance": 0, "low_relevance": 0}
        }

def save_to_history_csv(data):
    """6. 保存历史记录到 CSV"""
    try:
        row = {
            "日期": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "上证指数": data["market_sentiment"]["index_value"],
            "大盘涨跌%": data["market_sentiment"]["change_pct"],
        }
        sectors = data["hot_sectors"]
        for i in range(min(3, len(sectors))):
            s = sectors[i]
            lead_name = s["leading_stocks"][0]["name"] if s["leading_stocks"] else "无"
            row[f"Top{i+1}_板块"] = s["name"]
            row[f"Top{i+1}_龙头"] = lead_name

        df = pd.DataFrame([row])
        if not os.path.exists(HISTORY_FILE):
            df.to_csv(HISTORY_FILE, index=False, encoding='utf_8_sig')
        else:
            df.to_csv(HISTORY_FILE, mode='a', header=False, index=False, encoding='utf_8_sig')
        print(f"✅ 历史记录已追加")
    except Exception as e:
        print(f"❌ 历史保存失败: {e}")

# ==========================================
# 🏁 主程序入口
# ==========================================
def main():
    print("="*50)
    print("🚀 开始执行全维扫描 (增强版 v2.0)")
    print("="*50)
    
    # 1. 获取所有模块数据
    print("\n[1/5] 获取市场情绪 + 量化指标...")
    sentiment = get_market_sentiment()
    print(f"  -> 大盘: {sentiment['index_value']} ({sentiment['change_pct']}%)")
    print(f"  -> 温度: {sentiment['market_temperature']} | 风险: {sentiment['risk_level']}")
    print(f"  -> 建议: {sentiment['suggested_action']}")
    
    print("\n[2/5] 扫描热点板块 (每板块5只股票)...")
    sectors = get_hot_sectors_and_stocks(top_n=8, stocks_per_sector=5)
    
    print("\n[3/5] 分析龙虎榜...")
    dt_list = get_dragon_tiger_list()
    
    print("\n[4/5] 巡查持仓...")
    my_stocks = check_my_portfolio()
    if isinstance(my_stocks, dict) and my_stocks.get('summary', {}).get('has_danger'):
        print("  ⚠️ 发现高风险持仓！")
    
    print("\n[5/5] 抓取新闻 (质量过滤)...")
    news = get_latest_news(limit=15)

    # 2. 组装数据
    data = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_version": "2.0",
        "market_sentiment": sentiment,
        "hot_sectors": sectors,
        "dragon_tiger": dt_list,
        "my_portfolio": my_stocks,
        "news_brief": news
    }
    
    # 3. 保存 JSON (给 n8n)
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
