# N8N 工作流修复 - 备选方案

## 🔧 方案A：使用 Execute Command 节点（推荐）

这是最可靠的方案，不依赖 Read File 节点的复杂格式。

### 步骤 1: 删除或禁用 Read File 节点

### 步骤 2: 添加 Execute Command 节点

在 Schedule Trigger 之后，添加一个 **Execute Command** 节点：

**配置如下：**
- **Command**: `cat /home/kk/n8n/market_data.json`
- **或者更安全的方式**:
  ```bash
  python3 /home/kk/n8n/market_scanner.py && cat /home/kk/n8n/market_data.json
  ```
  这样可以确保先运行脚本，再读取最新数据

### 步骤 3: 添加 Code 节点

在 Execute Command 之后，添加 Code 节点，使用以下代码：

```javascript
// 从 Execute Command 的输出中解析 JSON
const output = items[0].json.stdout || items[0].json.output || "";

let data = {};
try {
    data = JSON.parse(output);
    console.log("✅ 成功解析数据");
    console.log("📊 时间戳:", data.timestamp);
    console.log("💼 持仓数量:", data.my_portfolio?.stocks?.length || 0);
} catch (error) {
    console.log("❌ 解析失败:", error.message);
    return { json: { error: "无法解析 JSON", output: output.substring(0, 500) } };
}

// 构建 Prompt
const sentiment = data.market_sentiment || {};
const mood = `市场温度: ${sentiment.market_temperature || "未知"} | 风险偏好: ${sentiment.risk_level || "平稳"}`;

let portfolioText = "";
if (data.my_portfolio?.stocks?.length > 0) {
    data.my_portfolio.stocks.forEach(stock => {
        const tech = stock.technical || {};
        portfolioText += `
- ${stock.name} (${stock.code}): ${stock.change_pct}%
  建议: ${stock.advice} | RSI: ${tech.rsi6}
  风险: ${tech.risks?.join(',') || '无'}
`;
    });
}

let sectorText = "";
if (data.hot_sectors?.length > 0) {
    data.hot_sectors.slice(0, 5).forEach(s => {
        sectorText += `\n> **${s.name}** (+${s.change_pct}%)\n`;
        s.leading_stocks?.slice(0, 2).forEach(stock => {
            sectorText += `  - ${stock.name}: ${stock.change_pct}%\n`;
        });
    });
}

const prompt = `
你是A股量化分析师。根据以下数据生成《收盘复盘报告》：

【市场情绪】${mood}
【持仓诊断】${portfolioText}
【热点板块】${sectorText}

请输出 Markdown 格式报告，包含：
1. 核心持仓策略
2. 市场热点透视
3. 明日交易计划
`;

return {
    json: {
        body: {
            model: "qwen-plus",
            input: {
                messages: [
                    { role: "system", content: "你是专业A股分析师，基于数据分析。" },
                    { role: "user", content: prompt }
                ]
            },
            parameters: { result_format: "message" }
        },
        prompt: prompt,
        debug: {
            portfolioCount: data.my_portfolio?.stocks?.length || 0,
            hotSectors: data.hot_sectors?.slice(0,3).map(s => s.name) || []
        }
    }
};
```

---

## 🔧 方案B：修改 Read File 节点配置

如果您想继续使用 Read File 节点，请尝试：

### 步骤 1: 在 Read File 节点中添加 Options

点击 **Add option**，添加：
- **Property Name**: 留空或填 `data`
- **As JSON**: 如果有这个选项，勾选它
- **As UTF-8**: 勾选

### 步骤 2: 使用新的 Code

用 `/home/kk/n8n/n8n_code_v5_final.txt` 中的代码替换 Code 节点。

这个版本会输出详细的调试信息，帮您找到问题。

---

## 🎯 推荐方案对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| **Execute Command** | ✅ 最可靠<br>✅ 可以先运行脚本<br>✅ 格式简单 | 需要 SSH/Shell 权限 |
| **Read File + 新代码** | ✅ 不需要执行权限 | 需要调试 Binary 格式 |

---

## 📋 快速测试 Execute Command 方案

1. 在 N8N 中添加 **Execute Command** 节点
2. Command 填: `cat /home/kk/n8n/market_data.json`
3. 单独执行这个节点
4. 查看输出的 `stdout` 字段是否包含完整 JSON

如果看到完整 JSON，说明这个方案可行！
