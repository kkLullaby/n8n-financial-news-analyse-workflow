#!/bin/bash
# ====================================
# 守护进程脚本 - 自动重启服务
# ====================================

while true; do
    # 检查飞书代理
    if ! pgrep -f "feishu_proxy.py" > /dev/null; then
        echo "[$(date)] 飞书代理已停止，正在重启..."
        cd /home/kk/n8n
        nohup python3 feishu_proxy.py > /tmp/feishu_proxy.log 2>&1 &
    fi
    
    # 检查隧道
    if ! pgrep -f "cloudflared tunnel" > /dev/null; then
        echo "[$(date)] 隧道已停止，正在重启..."
        nohup cloudflared tunnel --url http://localhost:8080 > /tmp/cloudflared.log 2>&1 &
        sleep 10
        # 更新 URL
        grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared.log | head -1 > /home/kk/n8n/tunnel_url.txt
    fi
    
    # 每 30 秒检查一次
    sleep 30
done
