#!/bin/bash
# ====================================
# 查看服务状态
# ====================================

echo "======================================"
echo "📊 服务状态检查"
echo "======================================"
echo ""

# 检查飞书代理
if pgrep -f "feishu_proxy.py" > /dev/null; then
    PID=$(pgrep -f "feishu_proxy.py")
    echo "✓ 飞书代理: 运行中 (PID: $PID)"
    
    # 测试健康检查
    HEALTH=$(curl -s http://localhost:8080/health 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "  └─ 健康检查: ✓ OK"
        echo "  └─ 响应: $HEALTH"
    else
        echo "  └─ 健康检查: ✗ 失败"
    fi
else
    echo "✗ 飞书代理: 未运行"
fi

echo ""

# 检查隧道
if pgrep -f "cloudflared tunnel" > /dev/null; then
    PID=$(pgrep -f "cloudflared tunnel")
    echo "✓ Cloudflare 隧道: 运行中 (PID: $PID)"
    
    # 读取 URL
    if [ -f "/home/kk/n8n/tunnel_url.txt" ]; then
        TUNNEL_URL=$(cat /home/kk/n8n/tunnel_url.txt)
        echo "  └─ 公网 URL: $TUNNEL_URL"
        echo "  └─ Webhook: ${TUNNEL_URL}/feishu-webhook"
        
        # 测试可达性
        RESPONSE=$(curl -s -X POST "${TUNNEL_URL}/feishu-webhook" \
          -H "Content-Type: application/json" \
          -d '{"challenge": "status_test"}' 2>/dev/null)
        
        if echo "$RESPONSE" | grep -q "status_test"; then
            echo "  └─ Webhook 测试: ✓ 可访问"
        else
            echo "  └─ Webhook 测试: ✗ 不可访问"
        fi
    fi
else
    echo "✗ Cloudflare 隧道: 未运行"
fi

echo ""

# 检查持仓数量
STOCK_FILE="/home/kk/n8n/my_stocks.txt"
if [ -f "$STOCK_FILE" ]; then
    COUNT=$(grep -c "^[0-9]\{6\}$" "$STOCK_FILE" 2>/dev/null || echo 0)
    echo "📋 当前持仓: $COUNT 只"
fi

echo ""
echo "======================================"
echo ""
echo "📝 查看日志："
echo "  tail -f /tmp/feishu_proxy.log"
echo "  tail -f /tmp/cloudflared.log"
echo ""
