#!/bin/bash
# ====================================
# 飞书代理 + 隧道 启动脚本
# ====================================

SCRIPT_DIR="/home/kk/n8n"
PROXY_LOG="/tmp/feishu_proxy.log"
TUNNEL_LOG="/tmp/cloudflared.log"
URL_FILE="/home/kk/n8n/tunnel_url.txt"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================"
echo "🚀 启动飞书代理 + Cloudflare 隧道"
echo "======================================"

# 1. 停止旧进程
echo -e "${YELLOW}[1/4]${NC} 清理旧进程..."
pkill -f "feishu_proxy.py" 2>/dev/null && echo "  ✓ 已停止旧的代理服务"
pkill -f "cloudflared tunnel" 2>/dev/null && echo "  ✓ 已停止旧的隧道"
sleep 2

# 2. 启动飞书代理服务
echo -e "${YELLOW}[2/4]${NC} 启动飞书代理服务 (端口 8080)..."
nohup python3 ${SCRIPT_DIR}/feishu_proxy.py > ${PROXY_LOG} 2>&1 &
PROXY_PID=$!
sleep 3

# 检查代理服务是否启动成功
if curl -s http://localhost:8080/health > /dev/null; then
    echo -e "  ${GREEN}✓ 代理服务已启动${NC} (PID: ${PROXY_PID})"
else
    echo -e "  ${RED}✗ 代理服务启动失败${NC}"
    echo "  查看日志: tail -f ${PROXY_LOG}"
    exit 1
fi

# 3. 启动 Cloudflare 隧道
echo -e "${YELLOW}[3/4]${NC} 启动 Cloudflare 隧道..."
nohup cloudflared tunnel --url http://localhost:8080 > ${TUNNEL_LOG} 2>&1 &
TUNNEL_PID=$!
sleep 12

# 4. 提取隧道 URL
echo -e "${YELLOW}[4/4]${NC} 提取公网 URL..."
TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' ${TUNNEL_LOG} | head -1)

if [ -z "$TUNNEL_URL" ]; then
    echo -e "  ${RED}✗ 隧道启动失败${NC}"
    echo "  查看日志: tail -f ${TUNNEL_LOG}"
    exit 1
fi

echo "$TUNNEL_URL" > ${URL_FILE}

# 5. 测试验证
echo ""
echo "======================================"
echo -e "${GREEN}✓ 所有服务已启动！${NC}"
echo "======================================"
echo ""
echo "📊 服务状态："
echo "  • 飞书代理: http://localhost:8080 (PID: ${PROXY_PID})"
echo "  • 隧道服务: ${TUNNEL_URL} (PID: ${TUNNEL_PID})"
echo ""
echo "🌐 飞书 Webhook URL："
echo -e "  ${GREEN}${TUNNEL_URL}/feishu-webhook${NC}"
echo ""
echo "📝 查看日志："
echo "  • 代理日志: tail -f ${PROXY_LOG}"
echo "  • 隧道日志: tail -f ${TUNNEL_LOG}"
echo ""
echo "🛑 停止服务："
echo "  ./stop_services.sh"
echo ""
echo "======================================"

# 测试 challenge
echo "🧪 测试 challenge 验证..."
RESPONSE=$(curl -s -X POST "${TUNNEL_URL}/feishu-webhook" \
  -H "Content-Type: application/json" \
  -d '{"challenge": "startup_test"}')

if echo "$RESPONSE" | grep -q "startup_test"; then
    echo -e "  ${GREEN}✓ Webhook 验证成功！${NC}"
else
    echo -e "  ${YELLOW}⚠ 响应: ${RESPONSE}${NC}"
fi

echo ""
echo "======================================"
