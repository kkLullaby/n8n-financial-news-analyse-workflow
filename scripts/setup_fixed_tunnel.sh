#!/bin/bash
# ====================================
# 配置 Cloudflare 固定隧道
# ====================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_DIR="${ROOT_DIR}/data"

echo "======================================"
echo "🔐 配置 Cloudflare 固定隧道"
echo "======================================"
echo ""

# 1. 登录 Cloudflare（只需要一次）
echo "[Step 1] 登录 Cloudflare 账号..."
echo "将自动打开浏览器，请登录并授权"
echo ""
cloudflared tunnel login

if [ $? -ne 0 ]; then
    echo "❌ 登录失败"
    exit 1
fi

echo ""
echo "✓ 登录成功！"
echo ""

# 2. 创建命名隧道
TUNNEL_NAME="feishu-stock-bot"
echo "[Step 2] 创建命名隧道: $TUNNEL_NAME"
cloudflared tunnel create $TUNNEL_NAME

if [ $? -ne 0 ]; then
    echo "⚠️ 隧道可能已存在，继续..."
fi

# 3. 获取隧道 UUID
TUNNEL_UUID=$(cloudflared tunnel list | grep $TUNNEL_NAME | awk '{print $1}')

if [ -z "$TUNNEL_UUID" ]; then
    echo "❌ 无法获取隧道 UUID"
    exit 1
fi

echo "✓ 隧道 UUID: $TUNNEL_UUID"

# 4. 创建配置文件
CONFIG_FILE="$HOME/.cloudflared/config.yml"
echo ""
echo "[Step 3] 创建配置文件: $CONFIG_FILE"

cat > $CONFIG_FILE << EOF
tunnel: $TUNNEL_UUID
credentials-file: $HOME/.cloudflared/$TUNNEL_UUID.json

ingress:
  - hostname: $TUNNEL_NAME.cfargotunnel.com
    service: http://localhost:8080
  - service: http_status:404
EOF

echo "✓ 配置文件已创建"

# 5. 创建 DNS 路由
echo ""
echo "[Step 4] 配置 DNS 路由..."
cloudflared tunnel route dns $TUNNEL_NAME $TUNNEL_NAME.cfargotunnel.com

# 6. 显示固定 URL
echo ""
echo "======================================"
echo "✅ 配置完成！"
echo "======================================"
echo ""
echo "🌐 你的固定 URL："
echo "   https://$TUNNEL_NAME.cfargotunnel.com"
echo ""
echo "📝 飞书 Webhook URL："
echo "   https://$TUNNEL_NAME.cfargotunnel.com/feishu-webhook"
echo ""
echo "🚀 启动隧道："
echo "   cloudflared tunnel run $TUNNEL_NAME"
echo ""
echo "⚙️ 自动运行："
echo "   已更新启动脚本，下次使用固定 URL"
echo ""
echo "======================================"

# 保存配置信息
mkdir -p "${DATA_DIR}"
cat > "${DATA_DIR}/tunnel_config.txt" << EOF
Tunnel Name: $TUNNEL_NAME
Tunnel UUID: $TUNNEL_UUID
Fixed URL: https://$TUNNEL_NAME.cfargotunnel.com
Webhook URL: https://$TUNNEL_NAME.cfargotunnel.com/feishu-webhook
EOF

echo "配置信息已保存到: ${DATA_DIR}/tunnel_config.txt"
