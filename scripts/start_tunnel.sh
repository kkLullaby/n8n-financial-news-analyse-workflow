#!/bin/bash
# 启动 Cloudflare 隧道脚本
# 使用方法: ./start_tunnel.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_DIR="${ROOT_DIR}/data"

LOG_FILE="/tmp/cloudflared.log"

# 杀死旧的隧道进程
pkill -f "cloudflared tunnel" 2>/dev/null

# 启动新隧道
echo "正在启动 Cloudflare 隧道..."
nohup cloudflared tunnel --url http://localhost:5678 > $LOG_FILE 2>&1 &

# 等待隧道建立
sleep 10

# 提取 URL
TUNNEL_URL=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' $LOG_FILE | head -1)

if [ -n "$TUNNEL_URL" ]; then
  echo "✅ 隧道已启动！"
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "📌 公网 URL: $TUNNEL_URL"
  echo ""
  echo "📝 飞书 Webhook URL:"
  echo "   ${TUNNEL_URL}/webhook/feishu-command"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "⚠️ 注意: 此 URL 在隧道重启后会变化"
  
  # 保存 URL 到文件
  mkdir -p "${DATA_DIR}"
  echo "$TUNNEL_URL" > "${DATA_DIR}/tunnel_url.txt"
else
  echo "❌ 隧道启动失败，请检查日志: $LOG_FILE"
  tail -20 $LOG_FILE
fi
