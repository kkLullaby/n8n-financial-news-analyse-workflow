#!/bin/bash
# ====================================
# 一键配置开机自启
# ====================================

echo "======================================"
echo "⚙️ 配置飞书机器人开机自启"
echo "======================================"
echo ""

# 备份现有 crontab
crontab -l > /tmp/crontab_backup_$(date +%Y%m%d_%H%M%S).txt 2>/dev/null
echo "✓ 已备份当前 crontab"

# 添加新任务（避免重复）
(crontab -l 2>/dev/null | grep -v "feishu_proxy.py" | grep -v "cloudflared tunnel" | grep -v "start_services.sh"; cat <<EOF
# Feishu Bot Auto-start
@reboot sleep 30 && /home/kk/n8n/start_services.sh >> /tmp/feishu_startup.log 2>&1
*/5 * * * * pgrep -f "feishu_proxy.py" > /dev/null || (cd /home/kk/n8n && nohup python3 feishu_proxy.py > /tmp/feishu_proxy.log 2>&1 &)
*/5 * * * * pgrep -f "cloudflared tunnel" > /dev/null || (nohup cloudflared tunnel --url http://localhost:8080 > /tmp/cloudflared.log 2>&1 &)
EOF
) | crontab -

echo "✓ Crontab 已更新"
echo ""
echo "======================================"
echo "✅ 配置完成！"
echo "======================================"
echo ""
echo "📋 已添加的任务："
echo "  • 开机自动启动服务"
echo "  • 每 5 分钟检查并自动重启"
echo ""
echo "🔍 查看 crontab："
echo "  crontab -l"
echo ""
echo "🗑️ 移除自启："
echo "  crontab -e  (手动删除相关行)"
echo ""
echo "======================================"
