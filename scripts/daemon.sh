#!/bin/bash
# ====================================
# 守护进程脚本 - 自动重启服务
# ====================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_DIR="${ROOT_DIR}/data"

while true; do
    # 检查飞书代理
    if ! pgrep -f "feishu_proxy.py" > /dev/null; then
        echo "[$(date)] 飞书代理已停止，正在重启..."
        cd "${ROOT_DIR}"
        nohup python3 feishu_proxy.py > /tmp/feishu_proxy.log 2>&1 &
    fi
    
    # 检查隧道
    if ! pgrep -f "cloudflared tunnel" > /dev/null; then
        echo "[$(date)] 隧道已停止，正在重启..."
        nohup cloudflared tunnel --url http://localhost:8080 > /tmp/cloudflared.log 2>&1 &
        sleep 10
        # 更新 URL
        mkdir -p "${DATA_DIR}"
        grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared.log | head -1 > "${DATA_DIR}/tunnel_url.txt"
    fi
    
    # 每 30 秒检查一次
    sleep 30
done
