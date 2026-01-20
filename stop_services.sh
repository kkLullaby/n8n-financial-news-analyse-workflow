#!/bin/bash
# ====================================
# 停止所有服务
# ====================================

echo "🛑 停止飞书代理 + 隧道服务..."

# 停止飞书代理
pkill -f "feishu_proxy.py" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✓ 已停止飞书代理"
else
    echo "  ℹ 飞书代理未运行"
fi

# 停止隧道
pkill -f "cloudflared tunnel" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✓ 已停止 Cloudflare 隧道"
else
    echo "  ℹ 隧道未运行"
fi

echo ""
echo "✓ 所有服务已停止"
