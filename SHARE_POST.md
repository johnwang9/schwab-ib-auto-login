# 群发分享文案 / Group Share Copy

仓库地址 / Repo: https://github.com/johnwang9/schwab-ib-auto-login

---

## 版本 A · 推荐（完整版，适合量化群 / 技术群）

每天开盘前，你还在手忙脚乱地输密码、盯着转圈圈的更新进度条吗？

我把自用的**券商客户端自动登录方案**开源了 —— 一次配置，双击（或开机自动）完成"启动 → 等界面就绪 → 填 ID → 填密码 → 提交"全流程：

**覆盖三家券商客户端：**
- **Schwab thinkorswim**：自动登录 + **开机预热**（还在装更新时它已经跑完，坐下一看登录页就摆那儿了）
- **IBKR TWS**：加官方开关 `-J-DskipUpdateCheck=true` **跳过更新检查直登**，自动等手机 IB Key 2FA
- **IBKR Gateway**：Live / Paper 双模式可选，登录后**自动跑你的 Python 数据脚本**

**额外附赠：Schwab API token 7 天自动续期**
Schwab 的 refresh token 只有 7 天寿命，过期就要人工重走浏览器授权。配套的 `schwab_token_keeper.py` + 计划任务做到了：token 快到期时在**美股闭市时段无头浏览器自动重授权**，写库前自动备份、自检失败自动回滚。彻底告别"token 过期、重新授权"的重复劳动。

**几个我踩过的坑，都写在文档里了**（改代码前建议先看）：
- thinkorswim 登录框是**内嵌 Chromium**，`ControlSend` 无效，只能坐标点击 + 剪贴板粘贴
- 中文输入法会吞掉 `Send()` 的英文字符串，**必须走剪贴板**才可靠
- 更新程序窗口标题含 "thinkorswim"，会被误判成"已登录"，需要用进程名+标题三层过滤
- 直接 `Run()` 启动会被安全软件卡住更新下载，改用 `explorer.exe` 走 Shell 就正常了

**全部是源码，账号密码只存在你本机 `accounts.ini`，不经任何第三方服务器。**（明文存储，请自行评估风险）

GitHub（欢迎 Star ⭐）：
https://github.com/johnwang9/schwab-ib-auto-login

---

## 版本 B · 精简版（适合快节奏群 / 朋友圈）

开源了一个**券商客户端自动登录**方案，支持三家：

· **Schwab thinkorswim** — 自动登录 + 开机预热（更新提前跑完）
· **IBKR TWS** — 跳过更新检查直登，自动等手机 2FA
· **IBKR Gateway** — Live/Paper 双模式，登录后自动跑 Python 脚本

另附 **Schwab API token 7 天自动续期**（闭市时段无头浏览器自动重授权，写库前自动备份）

源码全公开，凭据只存本机，含完整踩坑记录 👇
https://github.com/johnwang9/schwab-ib-auto-login

---

## 版本 C · 英文版（适合国际群 / Discord / Reddit）

**Auto-login for Schwab thinkorswim, IBKR TWS & IB Gateway — open source**

Still typing passwords and watching an update bar spin every morning before the open?

I open-sourced my personal broker auto-login setup. Configure once, then double-click (or auto-run on boot) to complete the whole flow: launch → wait for UI → fill login ID → fill password → submit.

**Three broker clients covered:**
- **Schwab thinkorswim** — auto-login + **boot pre-warm** (updates finish before you sit down)
- **IBKR TWS** — skips the update check via `-J-DskipUpdateCheck=true`, waits for mobile IB Key 2FA
- **IBKR Gateway** — Live/Paper mode, auto-runs your Python script after login

**Bonus: Schwab API token auto-renewal**
Schwab refresh tokens expire in 7 days. The included `schwab_token_keeper.py` + Task Scheduler re-authorizes headlessly during US market-closed hours, with automatic backup before writing and rollback on self-check failure.

**Pitfalls documented in detail** (worth reading before modifying):
- thinkorswim's login window is an **embedded Chromium page** — `ControlSend` doesn't work; coordinate clicks + clipboard paste required
- IME swallows ASCII `Send()` strings — clipboard paste bypasses it reliably
- The updater window title contains "thinkorswim" and gets misdetected as "already logged in" — needs 3-layer filtering
- Launching via `Run()` gets the updater blocked by security software; `explorer.exe` works

All source code. Credentials stay in a local `accounts.ini`, never sent to any third-party server.

GitHub (stars welcome ⭐):
https://github.com/johnwang9/schwab-ib-auto-login

---

## 发送注意事项

**建议附带一张截图** —— 登录成功后的界面，或 README 首页。纯文字链接的点击率明显低于带图的。

**发布顺序建议：**
1. 先在自己熟悉的群发，收集反馈、修问题
2. 再发大群（第一次被质疑时你已经准备好了）
3. 国外渠道用版本 C

**准备好回答这两个问题**（一定会被问）：
- **"安全吗？"** → 凭据只存本机 `accounts.ini`，代码全开源可自己审查，不经任何服务器
- **"会被券商封号吗？"** → 这是本机模拟人工输入，不调 API 下单；但自动化登录确实可能触及券商条款，**请自行确认合规**（README 免责声明已写明）

**不建议在群里做什么：**
- ❌ 不要发 QQ 二维码图片（群里都是自己人，直接发链接就行）
- ❌ 不要承诺"绝对安全""绝不会封号" —— 无法保证的事不要说
- ❌ 不要在完全没有技术背景的群里发（会被问"怎么装 Python"问到崩溃）
