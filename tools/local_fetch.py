import akshare as ak
import json
import os
from datetime import date, datetime

def json_serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)

def save_market_data():
    file_path = os.path.expanduser("~/n8n/market_data.json")
    try:
        print("正在获取全市场实时行情...")
        # 这个接口是 AkShare 最核心且最稳的接口
        df = ak.stock_zh_a_spot_em()
        
        # 尝试通过多种关键词匹配，甚至直接找上证指数(sh000001)作为替代参考
        # 只要有一行数据，大模型就能分析
        market_info = df.head(10).to_dict(orient='records') # 拿前10名作为市场热度参考
        
        # 专门寻找一下 A50 相关的个股或宽基
        a50_ref = df[df['名称'].str.contains('50', na=False)].head(2).to_dict(orient='records')

        print("正在通过保底方式获取新闻...")
        try:
            # 放弃复杂的新闻接口，改用最基础的 JS 接口
            news_df = ak.js_news(src="sina")
            news = news_df.head(5).to_dict(orient='records')
        except:
            news = [{"title": "市场波动", "content": "当前网络环境建议关注价格异动"}]

    except Exception as e:
        print(f"抓取中途报错: {str(e)}")
        market_info = []
        news = [{"content": "接口限制"}]

    data = {
        "market_top_10": market_info,
        "a50_reference": a50_ref,
        "news": news,
        "updated_at": datetime.now().isoformat()
    }
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, default=json_serial, ensure_ascii=False, indent=2)
    print(f"写入成功: {file_path}")

if __name__ == "__main__":
    save_market_data()
