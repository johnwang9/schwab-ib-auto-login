# GitHub 发布操作清单 / GitHub Publishing Checklist

目标仓库 / Target repo: `https://github.com/johnwang9/schwab-ib-auto-login`

---

## 一、推送 7 个文件（一条命令）

```bash
cd /c/Setup/auto
git remote add origin https://github.com/johnwang9/schwab-ib-auto-login.git
git push -u origin main
```

弹出凭据框时：
- Username: `johnwang9`
- Password: 粘贴你的 **PAT**（不是账号密码，GitHub 不支持密码推送）

**如果卡住连不上**（本机直连 GitHub 被墙，必须走代理）：
```bash
git config --global http.proxy http://127.0.0.1:6789
git config --global https.proxy http://127.0.0.1:6789
```

---

## 二、Description（仓库标题下的简介）

打开 https://github.com/johnwang9/schwab-ib-auto-login → 右侧齿轮 Settings 图标 → Description 填入：

```
Auto-login for Schwab thinkorswim, IBKR TWS and IB Gateway — an IBC / IBCAlpha
alternative that also supports thinkorswim, plus Schwab API refresh-token
auto-renewal. AutoIt + Windows Task Scheduler.
```

Website 可填 `https://github.com/johnwang9/schwab-ib-auto-login`（或留空）

---

## 三、Topics（搜索权重最高的字段，20 个全填满）

同一 Settings 面板，Topics 栏逐个粘贴（每次回车确认）：

```
thinkorswim
schwab
ibkr
interactive-brokers
tws
ib-gateway
ibc
ibc-alpha
autoit
autologin
auto-login
windows-automation
task-scheduler
quantitative-trading
algorithmic-trading
trading-automation
schwab-api
refresh-token
tws-api
broker-automation
```

---

## 四、为什么是这些词（实测数据）

| 搜索词 | GitHub 命中数 | 说明 |
|---|---|---|
| `thinkorswim` | **288** | 有真实流量，你的最大抓手 |
| `interactive brokers tws` | 2 | IBC(1603★) 已归档、ib-controller(684★) |
| `auto login` | 0-1 | **GitHub 命名生态里的死词，别依赖它** |
| `ibc autologin` | 0 | 组合词无人用，但 `IBC` 单词权重高 |
| `schwab api token refresh` | 5 | 全是 Python/JS/PHP，**无 AutoIt 方案** |

**核心策略**：靠平台名（thinkorswim / TWS / IB Gateway / IBC）被搜到，
而不是靠 `auto login` 这种动作词。

**重要优势**：`IbcAlpha/IBC`（**1603 stars**，本领域事实标准）已于 2026 **归档停止维护**，
且完全不覆盖 thinkorswim 与 Schwab token 续期 → 写 `IBC alternative` 是真实且有杀伤力的定位。

---

## 五、不要写 "newest version"

无法核实的宣称会损害可信度。用**可验证的事实**替代：

| 别写 | 改写成 |
|---|---|
| the newest version | `Actively maintained (2026)` |
| the best solution | `An IBC / IBCAlpha alternative` |
| — | `Also supports thinkorswim`（IBC 不支持，独特优势） |
