#!/bin/bash
# 这个脚本用于触发n8n工作流前先更新数据

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_FILE="${ROOT_DIR}/data/market_data.json"

# 1. 进入工作目录
cd "${ROOT_DIR}"

# 2. 运行市场扫描脚本
echo "正在更新市场数据..."
python3 market_scanner.py

# 3. 显示结果
echo ""
echo "✅ 数据已更新！"
echo "📊 查看数据摘要："
python3 -c "import json; data=json.load(open('${DATA_FILE}')); print(f\"时间: {data.get('timestamp')}\"); print(f\"持仓: {len(data.get('my_portfolio', {}).get('stocks', []))}只\"); print(f\"板块: {len(data.get('hot_sectors', []))}个\")"
echo ""
echo "💡 现在可以："
echo "   1. 访问 http://localhost:5678 在n8n界面手动执行工作流"
echo "   2. 等待定时任务自动执行（9:15 或 14:50）"

echo "完成！"
