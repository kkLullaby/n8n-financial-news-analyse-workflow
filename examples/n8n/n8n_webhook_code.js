// n8n Webhook 节点 - Code in JavaScript
// 处理飞书 @机器人 消息，管理持仓股票

const fs = require('fs');
const STOCK_FILE = '/home/node/data/my_stocks.txt';

// 读取持仓
function readStocks() {
  try {
    if (!fs.existsSync(STOCK_FILE)) return [];
    const content = fs.readFileSync(STOCK_FILE, 'utf8');
    return content.split('\n').filter(code => /^\d{6}$/.test(code.trim()));
  } catch (e) {
    return [];
  }
}

// 写入持仓
function writeStocks(stocks) {
  try {
    fs.writeFileSync(STOCK_FILE, stocks.join('\n') + '\n', 'utf8');
    return true;
  } catch (e) {
    return false;
  }
}

// 处理指令
function processCommand(text) {
  const cleanText = text.replace(/@\S+\s*/g, '').trim();
  let stocks = readStocks();
  
  // 清空持仓
  if (/清空|clear|重置/i.test(cleanText)) {
    writeStocks([]);
    return { type: 'command', message: `⚠️ 已清空所有持仓\n\n当前监控: 0 只` };
  }
  
  // 添加股票
  const addMatch = cleanText.match(/(?:添加|add|买入|加入|新增)\s*(\d{6})/i);
  if (addMatch) {
    const code = addMatch[1];
    if (!stocks.includes(code)) {
      stocks.push(code);
      writeStocks(stocks);
      return { 
        type: 'command', 
        message: `✅ 已添加股票 ${code}\n\n📋 当前监控 (${stocks.length} 只):\n` + stocks.map(s => `• ${s}`).join('\n')
      };
    }
    return { type: 'command', message: `⚠️ 股票 ${code} 已在监控列表中` };
  }
  
  // 删除股票
  const delMatch = cleanText.match(/(?:删除|del|remove|卖出|移除)\s*(\d{6})/i);
  if (delMatch) {
    const code = delMatch[1];
    if (stocks.includes(code)) {
      stocks = stocks.filter(s => s !== code);
      writeStocks(stocks);
      const list = stocks.length > 0 ? stocks.map(s => `• ${s}`).join('\n') : '（空）';
      return { 
        type: 'command', 
        message: `🗑️ 已移除股票 ${code}\n\n📋 剩余监控 (${stocks.length} 只):\n${list}`
      };
    }
    return { type: 'command', message: `⚠️ 股票 ${code} 不在监控列表中` };
  }
  
  // 查看持仓
  if (/查看|list|持仓|列表|查询/i.test(cleanText)) {
    if (stocks.length > 0) {
      return { 
        type: 'command', 
        message: `📋 当前持仓监控 (${stocks.length} 只)\n\n` + stocks.map(s => `• ${s}`).join('\n')
      };
    }
    return { type: 'command', message: '📋 当前没有监控任何股票\n\n发送 "添加 600519" 开始监控' };
  }
  
  // 帮助
  if (/帮助|help|\?|？/i.test(cleanText)) {
    return { 
      type: 'command', 
      message: `📖 持仓管理助手\n\n🔹 指令格式：\n• 添加 600519\n• 删除 600519\n• 查看持仓\n• 清空持仓\n\n📊 当前监控: ${stocks.length} 只`
    };
  }
  
  // 未识别指令
  return { 
    type: 'command', 
    message: `❓ 收到消息: "${cleanText}"\n\n请使用：\n• 添加 600519\n• 删除 600519\n• 查看持仓\n• 清空持仓\n\n当前监控: ${stocks.length} 只`
  };
}

// 主逻辑
const body = $input.item.json.body;

// 提取消息文本
let text = '';
try {
  const event = body.event || {};
  const message = event.message || {};
  const contentStr = message.content || '{}';
  const content = JSON.parse(contentStr);
  text = content.text || '';
} catch (e) {
  text = '';
}

if (!text) {
  return { json: { skip: true } };
}

// 处理指令
const result = processCommand(text);

return { json: result };
