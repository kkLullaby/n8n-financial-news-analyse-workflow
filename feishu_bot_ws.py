#!/usr/bin/env python3
"""
飞书机器人 - 长连接模式
使用飞书SDK的WebSocket长连接接收消息，无需配置回调URL
"""

import lark_oapi as lark
from lark_oapi.adapter.flask import *
from lark_oapi.api.im.v1 import *
import json
import os
import re
import requests

# 飞书配置
APP_ID = "cli_a9e0e7f0e8f81cc2"
APP_SECRET = "E4d1iB147qmPyAusrFALkegRtiBb571D"
WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/e7cfa254-769f-4995-bda9-2bae05dc710a"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STOCK_FILE = os.path.join(DATA_DIR, "my_stocks.txt")

def log(msg):
    print(msg, flush=True)

def read_stocks():
    try:
        if not os.path.exists(STOCK_FILE):
            return []
        with open(STOCK_FILE, 'r') as f:
            return [line.strip() for line in f if line.strip().isdigit() and len(line.strip()) == 6]
    except:
        return []

def write_stocks(stocks):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(STOCK_FILE, 'w') as f:
            if stocks:
                f.write('\n'.join(stocks) + '\n')
            else:
                f.write('')
        log(f"[写入] {len(stocks)} 只股票")
        return True
    except Exception as e:
        log(f"[写入失败] {e}")
        return False

def send_reply(text):
    """通过群机器人Webhook发送消息"""
    try:
        resp = requests.post(
            WEBHOOK_URL,
            json={"msg_type": "text", "content": {"text": text}},
            timeout=10
        )
        log(f"[回复] {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        log(f"[回复失败] {e}")
        return False

def process_command(raw_text):
    """处理指令"""
    text = re.sub(r'@\S+\s*', '', raw_text).strip()
    log(f"[指令] '{raw_text}' -> '{text}'")
    
    stocks = read_stocks()
    
    # 清空
    if re.search(r'清空|clear|重置', text, re.I):
        write_stocks([])
        return f"⚠️ 已清空所有持仓\n\n当前监控: 0 只"
    
    # 添加
    add_match = re.search(r'(?:添加|add|买入|加入)\s*(\d{6})', text, re.I)
    if add_match:
        code = add_match.group(1)
        if code not in stocks:
            stocks.append(code)
            write_stocks(stocks)
            return f"✅ 已添加 {code}\n\n📋 当前监控 ({len(stocks)} 只):\n" + "\n".join([f"• {s}" for s in stocks])
        return f"⚠️ {code} 已在列表中"
    
    # 删除
    del_match = re.search(r'(?:删除|del|remove|移除)\s*(\d{6})', text, re.I)
    if del_match:
        code = del_match.group(1)
        if code in stocks:
            stocks.remove(code)
            write_stocks(stocks)
            return f"🗑️ 已移除 {code}\n\n📋 剩余 ({len(stocks)} 只):\n" + ("\n".join([f"• {s}" for s in stocks]) if stocks else "（空）")
        return f"⚠️ {code} 不在列表中"
    
    # 查看
    if re.search(r'查看|持仓|列表|查询', text, re.I):
        if stocks:
            return f"📋 当前监控 ({len(stocks)} 只)\n\n" + "\n".join([f"• {s}" for s in stocks])
        return "📋 当前没有监控股票\n\n发送 \"添加 600519\" 开始"
    
    # 帮助
    return f"📖 持仓管理助手\n\n• 添加 600519\n• 删除 600519\n• 查看持仓\n• 清空持仓\n\n当前监控: {len(stocks)} 只"

def handle_message(data: P2ImMessageReceiveV1) -> None:
    """处理收到的消息"""
    try:
        message = data.event.message
        content = json.loads(message.content)
        text = content.get("text", "")
        
        log(f"\n{'='*50}")
        log(f"[收到消息] {text}")
        
        if text:
            reply = process_command(text)
            log(f"[回复内容] {reply[:50]}...")
            send_reply(reply)
        
        log(f"{'='*50}\n")
    except Exception as e:
        log(f"[处理错误] {e}")

def main():
    # 创建飞书客户端
    cli = lark.ws.Client(
        APP_ID,
        APP_SECRET,
        event_handler=lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(handle_message)
            .build(),
        log_level=lark.LogLevel.INFO
    )
    
    log("="*50)
    log("🚀 飞书机器人启动 - 长连接模式")
    log("="*50)
    log(f"当前持仓: {read_stocks()}")
    log("="*50)
    log("等待消息...")
    
    # 启动长连接
    cli.start()

if __name__ == "__main__":
    main()
