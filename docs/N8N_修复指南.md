# N8N 工作流修复指南 (2026-01-26)

## 问题诊断
AI 生成的报告没有基于真实数据，原因可能是：
1. Code 节点没有正确解析 JSON 文件
2. HTTP Request 节点没有正确引用 Code 节点的输出
3. DashScope API 的请求格式不正确

---

## 修复步骤

### 步骤 1: 更新 Code 节点代码

将 `/home/kk/n8n/n8n_code_to_copy.txt` 中的**完整代码**复制到 N8N 的 Code 节点中。

### 步骤 2: 配置 Read/Write Files from Disk 节点

确保设置如下：
- **Operation**: `Read File(s) From Disk`
- **File Path**: `/home/kk/n8n/market_data.json` (绝对路径!)
- **Options**:
  - ✅ **JSON Parse**: 勾选 (如果有这个选项)
  - 或者 **Read As String**: 勾选 (代码会自动解析)

### 步骤 3: 配置 HTTP Request 节点 (DashScope)

**URL**: 
```
https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation
```

**Method**: `POST`

**Authentication**: `Header Auth`
- Header Name: `Authorization`
- Header Value: `Bearer sk-你的API密钥`

**Body Content Type**: `JSON`

**Body** (关键！选择 "JSON" 然后填入):
```
{{ $json.body }}
```

或者如果上面不工作，尝试:
```json
{
  "model": "qwen-plus",
  "input": {
    "messages": [
      {
        "role": "user", 
        "content": "{{ $json.prompt }}"
      }
    ]
  }
}
```

### 步骤 4: 检查 HTTP Request 输出到飞书

在发送到飞书之前，您可能需要一个 Code 节点来提取 AI 的回复：

```javascript
// 提取 DashScope 返回的内容
const response = items[0].json;

let aiContent = "";
try {
    // DashScope 返回格式
    if (response.output && response.output.choices) {
        aiContent = response.output.choices[0].message.content;
    }
    // 或者直接的 text 格式
    else if (response.output && response.output.text) {
        aiContent = response.output.text;
    }
    else {
        aiContent = JSON.stringify(response);
    }
} catch (e) {
    aiContent = "解析 AI 响应失败: " + e.message;
}

return {
    json: {
        content: aiContent
    }
};
```

---

## 调试技巧

### 1. 检查 Code 节点输出
运行工作流后，点击 Code 节点，查看输出的 `debug` 字段：

```json
{
  "debug": {
    "parseSuccess": true,
    "timestamp": "2026-01-26 ...",
    "portfolioCount": 1,
    "portfolioStocks": ["特变电工(600089): 1.82%"],
    "hotSectorsCount": 8
  }
}
```

- 如果 `portfolioCount` 是 0，说明文件读取失败
- 如果 `parseSuccess` 是 false，说明 JSON 解析出错

### 2. 检查 HTTP Request 发送的内容
在 HTTP Request 节点的设置中，可以查看实际发送的请求体。确保 `input.messages[1].content` 包含了您的持仓信息。

### 3. 手动测试 API
您可以用 curl 测试 DashScope API：

```bash
curl -X POST 'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation' \
  -H 'Authorization: Bearer sk-你的密钥' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen-plus",
    "input": {
      "messages": [{"role": "user", "content": "你好"}]
    }
  }'
```

---

## 常见问题

### Q: AI 回复说"数据源是 undefined"
**A**: Code 节点没有正确读取到 JSON 文件。请检查：
1. Read File 节点的路径是否正确
2. market_data.json 文件是否存在且格式正确

### Q: HTTP Request 返回 401
**A**: API Key 不正确或过期。请更新 Authorization header。

### Q: 飞书收到的消息是空的
**A**: 检查最后一个发送飞书的 HTTP Request 节点，确保引用了正确的字段。

---

## 文件位置

- Python 脚本: `/home/kk/n8n/market_scanner.py`
- 生成的数据: `/home/kk/n8n/market_data.json`
- 持仓列表: `/home/kk/n8n/my_stocks.txt`
- N8N Code 代码: `/home/kk/n8n/n8n_code_to_copy.txt`
