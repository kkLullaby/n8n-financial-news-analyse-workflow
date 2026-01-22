# 修复工作流数据不更新的问题

## 问题原因
n8n工作流在定时触发时，直接读取 `market_data.json`，但没有先运行 `market_scanner.py` 来更新数据，导致使用的是旧数据。

## 解决方案：在工作流中添加数据更新步骤

### 步骤1：打开n8n界面
访问：http://localhost:5678

### 步骤2：编辑工作流
1. 找到并打开 "My workflow"
2. 点击左侧的"+"添加新节点

### 步骤3：添加Execute Command节点
1. 搜索并选择 "Execute Command" 节点
2. 配置如下：
   - **Command**: `python3 /home/kk/n8n/market_scanner.py`
   - **Working Directory**: `/home/kk/n8n`
3. 将这个节点拖到工作流的最开始（在"Schedule Trigger"之后，"Read/Write Files"之前）
4. 连接节点：
   ```
   Schedule Trigger → Execute Command → Read/Write Files → ...
   ```

### 步骤4：保存并测试
1. 点击右上角"Save"保存工作流
2. 点击"Execute Workflow"测试

## 方案2（临时）：使用外部定时任务

如果Execute Command节点不可用，可以改用crontab：

```bash
# 编辑crontab
crontab -e

# 添加以下行（工作日早上9:10和下午14:45运行）
10 9 * * 1-5 cd /home/kk/n8n && python3 market_scanner.py
45 14 * * 1-5 cd /home/kk/n8n && python3 market_scanner.py
```

这样在n8n工作流触发前5分钟，数据就已经更新了。
