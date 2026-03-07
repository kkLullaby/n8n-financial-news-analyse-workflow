import requests
import json
import re

print("正在测试新浪板块接口...")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://finance.sina.com.cn/'
}

# 测试1: 新浪行业板块 (JSONP or JS format)
# 这个URL通常返回 var S_Finance_bankuai_sinahy = {...}
url_industry = "http://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php"
try:
    print(f"1. 请求: {url_industry}")
    resp = requests.get(url_industry, headers=headers, timeout=5)
    resp.encoding = 'gbk'
    content = resp.text
    # 提取 JSON 对象: 查找 { ... }
    match = re.search(r'({.*})', content)
    if match:
        data_str = match.group(1)
        # 这种格式通常 key 没有引号，比如 {classid:"cls_...", ...}，标准 json.loads 解析不了
        # 需要做一些处理或者直接用 eval (如果在受控环境下)
        print(f"   -> 响应长度: {len(content)}")
        print(f"   -> 数据片段: {data_str[:100]}...")
        
        # 简单解析一下看看结构
        # 假设它是 {key: "value", ...} 格式
        if "sw_yinliao" in data_str or "new_blhy" in data_str:
             print("✅ 似乎获取到了行业数据")
    else:
        print("❌ 未找到预期的数据格式")
        print(content[:200])
except Exception as e:
    print(f"❌ 行业请求失败: {e}")

print("-" * 30)

# 测试2: 新浪概念板块
url_concept = "http://money.finance.sina.com.cn/q/view/newSinaHy.php" 
# 似乎是同一个 URl，可能参数不同？
# 尝试另一个 API 风格的
url_api = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
params = {
    "page": "1",
    "num": "8",
    "sort": "changepercent",
    "asc": "0",
    "node": "sinahy" # trying 'sinahy' for industry
}

try:
    print(f"2. 请求 API: {url_api}")
    resp = requests.get(url_api, params=params, headers=headers, timeout=5)
    content = resp.text
    print(f"   -> 状态码: {resp.status_code}")
    print(f"   -> 内容: {content[:200]}")
    if resp.status_code == 200 and len(content) > 10:
         print("✅ 获取到了 JSON 数组")
except Exception as e:
    print(f"❌ API 请求失败: {e}")
