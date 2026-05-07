# AlphaPilot AI v0.32

基于 Streamlit 的加密货币量化交易终端，支持 Binance 永续合约的多空信号扫描、AI 决策辅助、模拟交易执行与复盘分析。

**v0.32 新增：WebSocket 实时行情推送 + Railway 512MB 内存优化**

---

## 功能特性

- **实时行情**：Binance WebSocket 推送，价格延迟 <1 秒
- **多空排行榜**：扫描全市场低价币种，REST 请求已优化 95%+
- **AI 信号评分**：基于 RSI、MACD、布林带、均线、成交量的多因子模型
- **专业 K 线图**：币安深色风格，MA7/25/99、布林带、成交量
- **手动搜币**：支持输入任意币种代码查看 K 线和 AI 信号
- **模拟交易**：动态资金池、熔断机制、止损止盈、智能订单队列
- **AI 复盘报告**：调用智谱 GLM-4-Flash（免费）生成每日结构化复盘
- **参数持久化**：所有设置刷新不丢失，自动交易稳定运行
- **零成本部署**：Railway 免费版 + UptimeRobot 保活
- **内存安全**：512MB 容器下 WebSocket 自动管理，超限降级

---

## 快速开始

### 1. 克隆仓库
```bash
git clone https://github.com/你的用户名/AlphaPilot-Lite-Pro.git
cd AlphaPilot-Lite-Pro
