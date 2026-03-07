// ============================================================
// 🎯 A股内参 - 智能拆包 & 双重保险版 (V9.0)
// ============================================================

// 1. 🔍 核心修复：智能定位数据层级
let root = $input.item.json;

// 如果数据被包在 'data' 字段里（根据你的截图修复）
if (root.data && (root.data.hot_sectors || root.data.market_sentiment)) {
    root = root.data;
}

// 2. 获取数据源
let reportText = root.ai_report_text;
const sectors = root.hot_sectors || [];
const sentiment = root.market_sentiment || {};
const portfolio = root.my_portfolio || { stocks: [], summary: {} }; // 🟢 新增持仓数据源

// 3. 🔥 救急逻辑：如果 Python 没生成文本，但有原始数据，现场拼一个！
if (!reportText && sectors.length > 0) {
    const time = root.timestamp || '刚刚';
    const temp = sentiment.market_temperature || '未知';
    const upRatio = sentiment.up_ratio || '-';
    
    let manualReport = `# A股实时内参 (JS应急版)\n`;
    manualReport += `🕒 ${time} | 🌡️ ${temp} | 📈 上涨率: ${upRatio}\n\n`;

    // A. 👮 持仓哨兵 (新增板块)
    if (portfolio.stocks && portfolio.stocks.length > 0) {
        manualReport += `## 👮 持仓哨兵\n`;
        manualReport += `策略建议: ${portfolio.summary.strategy_suggestion || '观察'}\n`;
        manualReport += `| 名称 | 涨幅 | 建议 |\n|---|---|---|\n`;
        portfolio.stocks.forEach(s => {
            manualReport += `| ${s.name} | ${s.change_pct}% | ${s.advice || '持有'} |\n`;
        });
        manualReport += `\n`;
    }
    
    // B. 🔥 核心板块 (增强角色与评级)
    manualReport += `## 🔥 核心题材掘金\n`;
    manualReport += `| 角色 | 代码 | 名称 | 涨幅 | 评级 | 核心点评 |\n|---|---|---|---|---|---|\n`;
    
    sectors.slice(0, 8).forEach((s) => { // 增加扫描板块数量
        const stocks = s.leading_stocks || [];
        // 手动分配角色：第一个是龙一，第二个是龙二...
        stocks.slice(0, 6).forEach((st, idx) => {
            let role = '⚡跟风';
            if (idx === 0) role = '👑龙一';
            if (idx === 1) role = '⚔️龙二';
            if (idx === 2) role = '🛡️中军';

            // 智能读取 Python 算好的评级，如果没有则 JS 估算
            let rec = st.recommendation || st.rating_label || '⚪';
            let comment = st.comment || st.rating_comment || '-';
            
            if (rec === '⚪' && st.change_pct > 9.5) rec = '🔥封板';
            
            manualReport += `| ${role} | ${st.code} | ${st.name} | ${st.change_pct}% | ${rec} | ${comment} |\n`;
        });
    });
    reportText = manualReport;
}

// 4. 最后的防线
if (!reportText) {
    reportText = `⚠️ 严重错误：N8N 未读取到有效数据！\n当前读取到的 JSON Keys: ${Object.keys(root).join(", ")}`;
}

// 5. 定义 AI 人设
const systemPrompt = `你是一名 A 股顶级游资操盘手。
你的任务是将一份【Python量化报告】改写为简短犀利的《主力内参》。

【严格执行原则】
1. **数据保真**：严禁修改任何数字、评级（如“妖股”）或角色（如“👑龙一”）。
2. **持仓监控**：如果报告包含【👮持仓哨兵】板块，请将其放在开头或显眼位置，明确给出操作建议。
3. **题材对比**：在【题材掘金】板块，必须保留表格形式，**强制包含“角色”、“评级”和“核心点评”三列**，以便用户直观对比龙头与跟风股。
4. **风格**：干练、专业、冷酷，拒绝废话。`;

const userContent = `这是最新的盘面扫描数据，请立即生成内参：\n\n${reportText}`;

// 6. 输出给 HTTP 节点
return {
    json: {
        messages: [
            { "role": "system", "content": systemPrompt },
            { "role": "user", "content": userContent }
        ]
    }
};