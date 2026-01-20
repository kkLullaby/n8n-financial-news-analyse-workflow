# 飞书股票机器人 - 服务管理指南

## 🚀 快速启动

```bash
cd /home/kk/n8n

# 启动所有服务
./start_services.sh

# 查看状态
./check_status.sh

# 停止服务
./stop_services.sh
```

---

## ⚙️ 配置开机自启

```bash
# 一键配置（推荐）
./setup_autostart.sh
```

配置后会自动：
- ✅ 开机时自动启动服务
- ✅ 每 5 分钟检查一次，挂了自动重启
- ✅ 记录所有日志

---

## 📊 服务架构

```
飞书 → Cloudflare Tunnel → Flask 代理 (8080) → 处理指令 → 修改 my_stocks.txt
                                                ↓
                                           n8n (定时读取)
```

---

## 📝 可用脚本

| 脚本 | 功能 |
|:---|:---|
| `start_services.sh` | 启动飞书代理 + 隧道 |
| `stop_services.sh` | 停止所有服务 |
| `check_status.sh` | 查看服务状态 + 测试 |
| `setup_autostart.sh` | 配置开机自启 |
| `daemon.sh` | 守护进程（持续监控） |

---

## 🔍 查看日志

```bash
# 飞书代理日志
tail -f /tmp/feishu_proxy.log

# 隧道日志
tail -f /tmp/cloudflared.log

# 查看当前 URL
cat /home/kk/n8n/tunnel_url.txt
```

---

## 💬 飞书支持的指令

在飞书群里 @机器人 发送：

| 指令 | 功能 |
|:---|:---|
| `添加 600519` | 添加股票到监控列表 |
| `删除 600519` | 从列表中移除股票 |
| `查看持仓` | 显示当前监控列表 |
| `清空持仓` | 清空所有监控 |

---

## 🛠️ 故障排查

### 服务没启动
```bash
./check_status.sh  # 查看状态
./start_services.sh  # 重新启动
```

### 隧道 URL 变了
每次重启隧道，URL 会变化（免费版限制）。需要：
1. 运行 `cat /home/kk/n8n/tunnel_url.txt` 查看新 URL
2. 到飞书后台更新 Request URL

### 配置长期 URL（可选）
注册 Cloudflare 账号后创建命名隧道，可获得固定 URL。

---

## 📌 文件说明

| 文件 | 说明 |
|:---|:---|
| `feishu_proxy.py` | 飞书代理服务（处理验证和指令） |
| `my_stocks.txt` | 持仓股票列表 |
| `tunnel_url.txt` | 当前隧道 URL |
| `market_scanner.py` | n8n 定时运行的数据扫描脚本 |

---

## ✅ 最佳实践

1. **设置开机自启**：运行 `./setup_autostart.sh`
2. **定期查看日志**：`tail -f /tmp/feishu_proxy.log`
3. **保存当前 URL**：避免忘记 webhook 地址

---

## 🔗 相关链接

- 飞书 Webhook URL: `https://xxx.trycloudflare.com/feishu-webhook`
- 健康检查: `http://localhost:8080/health`
- n8n 界面: `http://localhost:5678`

---

如有问题，查看日志或重启服务即可解决大部分问题。
