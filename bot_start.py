import lark_oapi as lark
from lark_oapi.adapter.flask import *
from lark_oapi.api.im.v1 import *

# 1. 填入你的 App ID 和 App Secret
# (在飞书后台 -> "凭证与基础信息" 里找)
APP_ID = "cli_a9e0e7f0e8f81cc2" 
APP_SECRET = "E4d1iB147qmPyAusrFALkegRtiBb571D"

# 群机器人 Webhook
WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/e7cfa254-769f-4995-bda9-2bae05dc710a"
STOCK_FILE = "/home/kk/n8n/my_stocks.txt"

import requests
import json
import re
import os

def read_stocks():
    try:
        if not os.path.exists(STOCK_FILE):
            return []
        with open(STOCK_FILE, 'r') as f:
            return [line.strip() for line in f if line.strip().isdigit() and len(line.strip()) == 6]
    except:
        return []

def write_stocks(stocks):
    with open(STOCK_FILE, 'w') as f:
        f.write('\n'.join(stocks) + '\n') if stocks else f.write('')

def send_reply(text):
    requests.post(WEBHOOK_URL, json={"msg_type": "text", "content": {"text": text}}, timeout=10)

def process_command(raw_text):
    text = re.sub(r'@\S+\s*', '', raw_text).strip()
    stocks = read_stocks()
    
    if re.search(r'清空|clear', text, re.I):
        write_stocks([])
        return f"⚠️ 已清空所有持仓\n当前监控: 0 只"
    
    add_match = re.search(r'(?:添加|add)\s*(\d{6})', text, re.I)
    if add_match:
        code = add_match.group(1)
        if code not in stocks:
            stocks.append(code)
            write_stocks(stocks)
            return f"✅ 已添加 {code}\n📋 当前监控 ({len(stocks)} 只):\n" + "\n".join([f"• {s}" for s in stocks])
        return f"⚠️ {code} 已在列表中"
    
    del_match = re.search(r'(?:删除|del)\s*(\d{6})', text, re.I)
    if del_match:
        code = del_match.group(1)
        if code in stocks:
            stocks.remove(code)
            write_stocks(stocks)
            return f"🗑️ 已移除 {code}\n📋 剩余 ({len(stocks)} 只):\n" + ("\n".join([f"• {s}" for s in stocks]) if stocks else "（空）")
        return f"⚠️ {code} 不在列表中"
    
    if re.search(r'查看|持仓|列表', text, re.I):
        if stocks:
            return f"📋 当前监控 ({len(stocks)} 只)\n\n" + "\n".join([f"• {s}" for s in stocks])
        return "📋 当前没有监控股票"
    
    return f"📖 持仓助手\n• 添加 600519\n• 删除 600519\n• 查看持仓\n• 清空持仓\n\n当前监控: {len(stocks)} 只"

# 2. 定义收到消息后的处理逻辑
def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    print(f'\n{"="*50}')
    print(f'[收到消息事件]')
    
    try:
        content_str = data.event.message.content
        print(f'[原始内容]: {content_str}')
        
        content = json.loads(content_str)
        text = content.get("text", "")
        print(f'[提取文本]: {text}')
        
        if text:
            reply = process_command(text)
            print(f'[回复内容]: {reply[:50]}...')
            send_reply(reply)
            print(f'[已发送回复]')
    except Exception as e:
        print(f'[处理错误]: {e}')
    
    print(f'{"="*50}\n')

# 3. 注册事件处理器
event_handler = lark.EventDispatcherHandler.builder("", "") \
    .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1) \
    .build()

# 4. 启动长连接客户端 (WebSocket Client)
def main():
    print("正在尝试建立长连接...")
    client = lark.ws.Client(APP_ID, APP_SECRET, 
                            event_handler=event_handler, 
                            log_level=lark.LogLevel.DEBUG)
    
    # 启动连接（这行代码会阻塞主线程，一直运行）
    client.start()

if __name__ == "__main__":
    main()