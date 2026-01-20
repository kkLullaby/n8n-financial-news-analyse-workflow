#!/usr/bin/env python3
"""
飞书 Webhook 代理服务 v3.0 - 最终修复版
"""

from flask import Flask, request, jsonify
import requests
import json
import os
import re
import sys

app = Flask(__name__)

# 配置
STOCK_FILE = "/home/kk/n8n/my_stocks.txt"
FEISHU_WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/e7cfa254-769f-4995-bda9-2bae05dc710a"

def log(msg):
    """打印日志并立即刷新"""
    print(msg, flush=True)

def read_stocks():
    """读取股票列表"""
    try:
        if not os.path.exists(STOCK_FILE):
            return []
        with open(STOCK_FILE, 'r') as f:
            return [line.strip() for line in f if line.strip().isdigit() and len(line.strip()) == 6]
    except Exception as e:
        log(f"[错误] 读取文件失败: {e}")
        return []

def write_stocks(stocks):
    """写入股票列表"""
    try:
        with open(STOCK_FILE, 'w') as f:
            if stocks:
                f.write('\n'.join(stocks) + '\n')
            else:
                f.write('')
        log(f"[成功] 写入 {len(stocks)} 只股票到文件")
        return True
    except Exception as e:
        log(f"[错误] 写入文件失败: {e}")
        return False

def send_reply(text):
    """通过 Webhook 发送消息到飞书群"""
    try:
        log(f"[发送回复] {text[:50]}...")
        resp = requests.post(
            FEISHU_WEBHOOK_URL,
            json={"msg_type": "text", "content": {"text": text}},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        log(f"[回复结果] HTTP {resp.status_code}: {resp.text[:100]}")
        return resp.status_code == 200
    except Exception as e:
        log(f"[回复失败] {e}")
        return False

def process_command(raw_text):
    """处理股票指令"""
    # 移除 @提及 (各种格式)
    text = re.sub(r'@\S+\s*', '', raw_text).strip()
    log(f"[处理指令] 原始='{raw_text}' -> 清理后='{text}'")
    
    stocks = read_stocks()
    log(f"[当前持仓] {stocks}")
    
    # 清空持仓
    if re.search(r'清空|clear|重置', text, re.I):
        write_stocks([])
        return f"⚠️ 已清空所有持仓\n\n当前监控: 0 只"
    
    # 添加股票
    add_match = re.search(r'(?:添加|add|买入|加入|新增)\s*(\d{6})', text, re.I)
    if add_match:
        code = add_match.group(1)
        if code not in stocks:
            stocks.append(code)
            write_stocks(stocks)
            return f"✅ 已添加股票 {code}\n\n📋 当前监控 ({len(stocks)} 只):\n" + "\n".join([f"• {s}" for s in stocks])
        else:
            return f"⚠️ 股票 {code} 已在监控列表中"
    
    # 删除股票
    del_match = re.search(r'(?:删除|del|remove|卖出|移除)\s*(\d{6})', text, re.I)
    if del_match:
        code = del_match.group(1)
        if code in stocks:
            stocks.remove(code)
            write_stocks(stocks)
            stock_list = "\n".join([f"• {s}" for s in stocks]) if stocks else "（空）"
            return f"🗑️ 已移除股票 {code}\n\n📋 剩余监控 ({len(stocks)} 只):\n{stock_list}"
        else:
            return f"⚠️ 股票 {code} 不在监控列表中"
    
    # 查看持仓
    if re.search(r'查看|list|持仓|列表|查询', text, re.I):
        if stocks:
            return f"📋 当前持仓监控 ({len(stocks)} 只)\n\n" + "\n".join([f"• {s}" for s in stocks])
        else:
            return "📋 当前没有监控任何股票\n\n发送 \"添加 600519\" 开始监控"
    
    # 帮助
    if re.search(r'帮助|help|\?|？', text, re.I):
        return f"""📖 持仓管理助手

🔹 指令格式：
• 添加 600519
• 删除 600519
• 查看持仓
• 清空持仓

📊 当前监控: {len(stocks)} 只"""
    
    # 未识别 - 也返回帮助信息
    return f"""❓ 收到消息: "{text}"

请使用以下格式：
• 添加 600519
• 删除 600519
• 查看持仓
• 清空持仓

当前监控: {len(stocks)} 只"""

@app.route('/feishu-webhook', methods=['POST', 'GET'])
def feishu_webhook():
    """飞书 Webhook 入口"""
    log("\n" + "="*60)
    log(f"[请求] {request.method} /feishu-webhook")
    
    if request.method == 'GET':
        return jsonify({'status': 'ok', 'message': 'Feishu webhook is running'})
    
    try:
        raw_data = request.get_data(as_text=True)
        log(f"[原始数据] {raw_data[:500]}")
        
        data = request.json or {}
        
        # 1. Challenge 验证
        if 'challenge' in data:
            challenge = data['challenge']
            log(f"[Challenge验证] {challenge}")
            return jsonify({'challenge': challenge})
        
        # 2. 加密消息检测
        if 'encrypt' in data:
            log("[警告] 收到加密消息，请在飞书后台关闭加密")
            send_reply("⚠️ 请在飞书后台关闭消息加密功能")
            return jsonify({'code': 0})
        
        # 3. 提取消息文本 - 尝试多种格式
        text = ""
        
        # 格式1: event.message.content
        event = data.get('event', {})
        message = event.get('message', {})
        content_str = message.get('content', '')
        if content_str:
            try:
                content = json.loads(content_str)
                text = content.get('text', '')
            except:
                text = content_str
        
        # 格式2: 直接在顶层
        if not text:
            text = data.get('text', '')
        
        # 格式3: event.text
        if not text:
            text = event.get('text', '')
        
        log(f"[提取文本] '{text}'")
        
        if not text:
            log("[跳过] 没有文本内容")
            return jsonify({'code': 0})
        
        # 4. 处理指令
        reply_text = process_command(text)
        log(f"[回复内容] {reply_text[:100]}...")
        
        # 5. 发送回复
        send_reply(reply_text)
        
        log("="*60 + "\n")
        return jsonify({'code': 0})
        
    except Exception as e:
        log(f"[异常] {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'code': 0, 'error': str(e)})

@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    stocks = read_stocks()
    return jsonify({'status': 'ok', 'stocks_count': len(stocks), 'stocks': stocks})

@app.route('/test', methods=['GET', 'POST'])
def test():
    """测试端点"""
    if request.method == 'POST':
        data = request.json or {}
        text = data.get('text', '')
        if text:
            reply = process_command(text)
            return jsonify({'reply': reply})
    return jsonify({'message': 'Send POST with {"text": "添加 600519"}'})

@app.route('/send-test', methods=['GET'])
def send_test():
    """发送测试消息到群"""
    result = send_reply("🧪 测试消息：机器人回复功能正常！")
    return jsonify({'success': result})

if __name__ == '__main__':
    log("="*60)
    log("🚀 飞书 Webhook 代理服务 v3.0")
    log("="*60)
    log(f"股票文件: {STOCK_FILE}")
    log(f"Webhook: {FEISHU_WEBHOOK_URL[:50]}...")
    log(f"当前持仓: {read_stocks()}")
    log("="*60)
    log("支持指令: 添加/删除/查看持仓/清空持仓/帮助")
    log("="*60)
    
    # 确保输出即时显示
    sys.stdout.flush()
    
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
