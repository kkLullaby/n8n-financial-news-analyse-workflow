# 开机重启后怎么用（长连接模式）

> 机器人走 **lark-oapi 长连接**，正常收发消息不依赖公网/隧道。只要本机能连外网即可。仅当需要对外暴露 webhook（如 n8n 公网回调）才启动 Cloudflare 隧道。

## 💻 开机后最小步骤
1. 终端进入项目目录（当前仓库根目录）
2. 启动飞书机器人（长连接）
   ```bash
   nohup python3 bot_start.py > /tmp/bot.log 2>&1 &
   tail -f /tmp/bot.log   # 看到 connected / ping success 表示就绪，可 Ctrl+C 退出 tail
   ```
3. 确认 n8n 正常（容器已设置开机自启，如需手动检查）
   ```bash
   docker ps | grep n8n_financial_bot || docker restart n8n_financial_bot
   ```
4. 需要立即出报告：
   ```bash
   ./scripts/trigger_workflow.sh   # 先更新数据，再调用 n8n 工作流推送
   ```

## 🔌 何时需要 Cloudflare 隧道
- 仅当需要让外部（飞书事件回调或公网 webhook）访问本机接口时才用隧道。
- 长连接模式下，飞书机器人收/发消息 **不需要** 隧道。

### 启动隧道（可选）
```bash
./scripts/start_fixed_tunnel.sh
cat data/tunnel_url.txt   # 获取当前隧道 URL
```
把新 URL 填到飞书后台的事件回调或任何公网 webhook 配置中。

## 🤖 飞书机器人指令
在群里 @机器人 发送：

| 指令示例 | 功能 |
|:---|:---|
| `添加 600519` | 添加股票到监控列表 |
| `删除 600519` | 从列表中移除 |
| `查看持仓` | 查看当前监控 |
| `清空持仓` | 清空所有监控 |

指令生效后，机器人后台会自动跑 `market_scanner.py` 更新 `market_data.json`，n8n 定时或手动触发时会用到最新数据。

## 🧰 常用脚本
| 脚本 | 用途 |
|:---|:---|
| `bot_start.py` | 飞书长连接机器人（核心） |
| `scripts/trigger_workflow.sh` | 先更新行情数据，再调用 n8n 工作流立即出报告 |
| `scripts/start_fixed_tunnel.sh` | 启动 Cloudflare 隧道（仅需公网回调时用） |
| `market_scanner.py` | 行情/持仓扫描，生成 `data/market_data.json` |

## 📜 日志与排查
```bash
# 机器人日志（长连接）
tail -f /tmp/bot.log

# n8n 容器日志
docker logs -f n8n_financial_bot

# 隧道日志（如果启动过）
tail -f /tmp/cloudflared.log
```

常见问题：
- 机器人不回复：重启 `bot_start.py`，确保网络通；检查 `bot.log` 是否连接成功。
- 持仓没更新：看 `bot.log` 是否触发了 `market_scanner.py`；必要时手动运行 `python3 market_scanner.py`，或用 `./trigger_workflow.sh`。
- n8n 不出报告：确认容器在跑；如需立即出报告，执行 `./trigger_workflow.sh`。
- 需要公网回调：启动隧道，更新飞书后台回调 URL。

## 📌 访问入口
- n8n 界面（本机）：http://localhost:5678
- 隧道 URL：`cat data/tunnel_url.txt`（仅在启动隧道后才会有）

## ⏰ 自动化任务时间表
系统已配置自动定时任务（crontab）：

| 时间 | 任务 | 说明 |
|:---|:---|:---|
| 09:10 | 更新市场数据 | 运行 `market_scanner.py` |
| 09:15 | n8n推送早盘报告 | 读取最新数据推送到飞书 |
| 14:45 | 更新市场数据 | 运行 `market_scanner.py` |
| 14:50 | n8n推送收盘报告 | 读取最新数据推送到飞书 |

数据更新提前5分钟，确保n8n工作流读取到最新数据。

## ✅ 开机速查清单
- [ ] `nohup python3 bot_start.py > /tmp/bot.log 2>&1 &`（必做）
- [ ] `tail -f /tmp/bot.log` 确认 connected（可选）
- [ ] `docker ps | grep n8n_financial_bot`（检查 n8n，异常时 `docker restart`）
- [ ] 需要立刻推送：`./scripts/trigger_workflow.sh`
- [ ] 需要公网回调才启动：`./scripts/start_fixed_tunnel.sh && cat data/tunnel_url.txt`

## 🔧 定时任务管理
```bash
# 查看当前定时任务
crontab -l

# 编辑定时任务
crontab -e

# 查看定时任务日志
tail -f /tmp/cron.log
```
