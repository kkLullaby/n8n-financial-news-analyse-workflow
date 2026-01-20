#!/bin/bash
# ====================================
# 使用固定隧道启动服务
# ====================================

SCRIPT_DIR="/home/kk/n8n"
PROXY_LOG="/tmp/feishu_proxy.log"
TUNNEL_LOG="/tmp/cloudflared_fixed.log"
TUNNEL_NAME="feishu-stock-bot"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "======================================"
echo "🚀 启动飞书代理 + 固定隧道"
echo "======================================"

# 检查是否已配置固定隧道
if [ ! -f "$HOME/.cloudflared/config.yml" ]; then
    echo -e "${RED}✗ 未检测到固定隧道配置${NC}"
    echo ""
    echo "请先运行: ./setup_fixed_tunnel.sh"
    exit 1
fi

# 1. 停止旧进程
echo -e "${YELLOW}[1/4]${NC} 清理旧进程..."
pkill -f "feishu_proxy.py" 2>/dev/null && echo "  ✓ 已停止旧的代理服务"
pkill -f "cloudflared tunnel" 2>/dev/null && echo "  ✓ 已停止旧的隧道"
sleep 2

# 2. 启动飞书代理
echo -e "${YELLOW}[2/4]${NC} 启动飞书代理服务..."
nohup python3 ${SCRIPT_DIR}/feishu_proxy.py > ${PROXY_LOG} 2>&1 &
PROXY_PID=$!
sleep 3

if curl -s http://localhost:8080/health > /dev/null; then
    echo -e "  ${GREEN}✓ 代理服务已启动${NC} (PID: ${PROXY_PID})"
else
    echo -e "  ${RED}✗ 代理服务启动失败${NC}"
    exit 1
fi

# 3. 启动固定隧道
echo -e "${YELLOW}[3/4]${NC} 启动固定隧道 (${TUNNEL_NAME})..."
nohup cloudflared tunnel run $TUNNEL_NAME > ${TUNNEL_LOG} 2>&1 &
TUNNEL_PID=$!
sleep 5

# 4. 验证
echo -e "${YELLOW}[4/4]${NC} 验证服务..."
FIXED_URL="https://${TUNNEL_NAME}.cfargotunnel.com"

echo ""
echo "======================================"
echo -e "${GREEN}✓ 所有服务已启动！${NC}"
echo "======================================"
echo ""
echo "📊 服务状态："
echo "  • 飞书代理: http://localhost:8080 (PID: ${PROXY_PID})"
echo "  • 固定隧道: ${FIXED_URL} (PID: ${TUNNEL_PID})"
echo ""
echo "🌐 飞书 Webhook URL："
echo -e "  ${GREEN}${FIXED_URL}/feishu-webhook${NC}"
echo ""
echo "  ⚠️ 这个 URL 永久有效，不会改变！"
echo ""
echo "======================================"

# 测试
echo ""
echo "🧪 测试 challenge 验证..."
RESPONSE=$(curl -s -X POST "${FIXED_URL}/feishu-webhook" \
  -H "Content-Type: application/json" \
  -d '{"challenge": "fixed_url_test"}' 2>&1)

if echo "$RESPONSE" | grep -q "fixed_url_test"; then
    echo -e "  ${GREEN}✓ 验证成功！${NC}"
else
    echo -e "  ${YELLOW}⚠ 请等待几分钟让 DNS 生效${NC}"
    echo "  响应: $RESPONSE"
fi

echo ""
echo "======================================"

# 保存 URL
echo "$FIXED_URL" > /home/kk/n8n/tunnel_url.txt
