#!/bin/bash
# 这个脚本用于触发n8n工作流前先更新数据

# 1. 进入工作目录
cd /home/kk/n8n

# 2. 运行市场扫描脚本
echo "正在更新市场数据..."
python3 market_scanner.py

# 3. 触发n8n工作流（通过API）
echo "正在触发n8n工作流..."
curl -X POST http://localhost:5678/api/v1/workflows/1QfFKeKPeALCB1uuEfz7u/execute \
  -H "Content-Type: application/json" \
  -d '{}'

echo "完成！"
