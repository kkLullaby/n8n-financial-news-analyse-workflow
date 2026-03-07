import requests

def test_sina(code):
    url = f"https://hq.sinajs.cn/list={code}"
    headers = {'Referer': 'https://finance.sina.com.cn'}
    resp = requests.get(url, headers=headers)
    resp.encoding = 'gbk'
    print(f"{code}: {resp.text}")

test_sina("bj920729")
test_sina("bse920729")
test_sina("sh600519")
