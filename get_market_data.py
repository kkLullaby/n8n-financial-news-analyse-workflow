import akshare as ak
import json
from datetime import date, datetime

# 解决日期无法序列化的问题
def json_serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)

def get_data():
    try:
        # 1. 抓取行情数据 (东方财富)
        # 我们用这个最稳的接口，它涵盖了 A50 相关的指数
        df_spot = ak.stock_zh_a_spot_em()
        
        # 筛选包含 "A50" 的行，转为字典
        a50_data = df_spot[df_spot['名称'].str.contains('A50', na=False)].head(1).to_dict(orient='records')

        # 2. 抓取实时快讯 (使用更通用的接口)
        # 如果 stock_telegraph_cls 不行，我们换成这个全球快讯接口
        try:
            news_df = ak.stock_info_global_cls() 
        except:
            # 万一上面的也不行，抓取新浪财经的实时新闻
            news_df = ak.js_news(src="sina")

        news_list = news_df.head(5).to_dict(orient='records')

        result = {
            "market_summary": a50_data,
            "latest_news": news_list,
            "status": "success"
        }
        return json.dumps(result, default=json_serial, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "status": "failed"}, ensure_ascii=False)

if __name__ == "__main__":
    print(get_data())
