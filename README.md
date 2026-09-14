# 嘉信理财 thinkorswim、盈透证券 TWS 与 IBKR Gateway 券商客户端自动登录程序源码（AutoIt + 计划任务）
# Schwab thinkorswim, IBKR TWS & IBKR Gateway Broker Client Auto-Login Source Code (AutoIt + Task Scheduler)

---

## ⚠️ 免责声明 / Disclaimer

> **中文**：本项目为个人自用自动化脚本的源码分享，凭据在本机**明文**存储、使用风险自负；请在确认合规的前提下自行评估使用，作者不对任何账户或资金损失负责。
>
> **English**: Source-code sharing of a personal-use automation script. Credentials are stored in **plaintext** locally — use at your own risk and verify compliance yourself; the author is not liable for any account or financial loss.

---

> **中文 / English**: 技术交流群【Stock quant analysis 股票量化分析】— 点击链接加入 / Join our discussion group: https://qm.qq.com/q/8xXDlS8clG （群内交流本方案、量化交易与开户相关话题 / discuss this solution, quantitative trading and account opening. English speakers are welcome.）
>
> 也可以在 [GitHub Issues](https://github.com/johnwang9/schwab-ib-auto-login/issues) 提问 / Questions and bug reports are also welcome via [GitHub Issues](https://github.com/johnwang9/schwab-ib-auto-login/issues).

> **中文**：目标：**每天开盘前，你还在手忙脚乱地输密码、盯着转圈圈的更新进度条，眼睁睁错过第一波行情吗？**
>
> 为方便交易登录，避免频繁登录需要输入用户名和密码，以及漫长的等待更新下载，我们对主流券商**嘉信理财 Schwab thinkorswim**、**盈透证券 IBKR TWS / IB**、**盈透证券 IBKR API Gateway** 开发了自动填充账户密码、一键自动登录功能。尤其是 **Schwab thinkorswim** 每次登录都要长时间下载等待，我们专门开发了**开机即自动执行下载任务**的能力——你还没坐到电脑前，更新早就跑完了，登录界面直接摆在那儿等你。
>
> **全部是源码，账号密码只保存在你本机文件，不经任何第三方服务器。**（凭据为明文存储，请按上方免责声明自行评估风险 / Credentials are stored in plaintext — assess the risk per the disclaimer above.）
>
> 一次配置，长期省心：双击一下（或开机自动）即可完成各券商客户端的"启动 → 等界面就绪 → 填登录 ID → 填密码 → 提交"全流程，不再每次手动等待和输入。覆盖三家：**Schwab thinkorswim**（自动登录 + 开机预热）、**IBKR TWS**（跳过更新检查直登 + 手机 2FA 等待）、**IBKR Gateway**（Live/Paper 双模式 + 登录后自动跑数据脚本）。配套：Schwab API token 7 天自动续期（`schwab_token_keeper.py` + 计划任务）——连 API 授权都帮你续好了，7 天一到自动换新，彻底告别"token 过期、重新走一遍浏览器授权"的重复劳动。
>
> **省下的不是几秒钟，是每天开盘前最宝贵的那几分钟专注力。**
>
> **English**: **Still typing passwords and staring at a spinning update bar every morning before the open — while the first move of the day slips away?**
>
> To make broker login painless — no more repeated username/password entry and no more long waits for update downloads — we built auto-fill, one-click auto-login for the major brokers: **Schwab thinkorswim**, **IBKR TWS / IB**, and **IBKR API Gateway**. thinkorswim in particular downloads updates on every launch, so we added **download-on-boot**: the update task runs automatically at startup, so by the time you sit down the login screen is already waiting for you.
>
> **Everything is source code. Credentials stay in a local file on your own machine. Safe, reliable, use it with confidence.**
>
> Configure once, forget the routine: double-click (or auto-start on boot) to complete the full flow — "launch → wait for UI ready → fill login ID → fill password → submit" — for each broker client. Covers three platforms: **Schwab thinkorswim** (auto-login + boot pre-warm), **IBKR TWS** (skip update check + mobile 2FA wait), **IBKR Gateway** (Live/Paper dual mode + auto-run data script after login). Companion: Schwab API token 7-day auto-renewal (`schwab_token_keeper.py` + Task Scheduler) — the API authorization renews itself too, so the "token expired, redo the browser flow" chore is gone for good.
>
> **What you save isn't a few seconds — it's your sharpest few minutes before the open.**
>
> **English**: Goal: double-click (or auto-start on boot) to complete the full flow — "launch → wait for UI ready → fill login ID → fill password → submit" — for each broker client, no more manual waiting and typing. Covers three platforms: **Schwab thinkorswim** (auto-login + boot pre-warm), **IBKR TWS** (skip update check + mobile 2FA wait), **IBKR Gateway** (Live/Paper dual mode + auto-run data script after login). Companion: Schwab API token 7-day auto-renewal (`schwab_token_keeper.py` + Task Scheduler).

---

## 一、这套东西包含什么
## 1. What's Included

| 文件 / File | 作用 / Purpose |
| --- | --- |
| `SCHWAB_autologin.au3` | thinkorswim 自动登录（账号密码从 accounts.ini 读取，脚本本身不含明文密码）/ thinkorswim auto-login (reads credentials from accounts.ini, no hardcoded passwords in script) |
| `TWS_autologin.au3` | IBKR TWS 自动登录（加 `-J-DskipUpdateCheck=true` 跳过更新直登，等手机 IB Key 2FA 确认）/ IBKR TWS auto-login (adds `-J-DskipUpdateCheck=true` to skip update, waits for mobile IB Key 2FA) |
| `IBGateway_autologin.au3` | IBKR Gateway 自动登录（Live/Paper 可选，2FA 等待，登录后自动运行 Python 数据脚本）/ IBKR Gateway auto-login (Live/Paper selectable, 2FA wait, auto-run Python script after login) |
| `accounts.ini.example` | 凭据配置模板。**复制改名为 accounts.ini 并填入你自己的账号密码**（三个登录脚本共用同一份）/ Credential template. **Copy and rename to accounts.ini, fill in your own login ID and password** (shared by all three login scripts) |
| `schwab_token_keeper.py` | Schwab API refresh token 7 天自动续期（健康检查 + 闭市时段无头重授权）/ Schwab API refresh token 7-day auto-renewal (health check + headless re-auth during market-closed hours) |
| `README.md` | 本文档 / This document |

**⚠️ 中文**：安全提醒：`accounts.ini` 含明文密码，只留在本机，绝不上传 / 分享 / 截图。上传分享本目录时只带 `accounts.ini.example` 模板。
**⚠️ English**: Security warning: `accounts.ini` contains plaintext passwords. Keep it on your local machine only — never upload, share, or screenshot it. When sharing this directory, only include the `accounts.ini.example` template.

---

## 二、安装 AutoIt
## 2. Install AutoIt

**中文**：AutoIt 是免费的 Windows 自动化脚本工具（模拟鼠标点击、键盘输入、等待窗口），官网 https://www.autoitscript.com/

**English**: AutoIt is a free Windows automation scripting tool (simulates mouse clicks, keyboard input, window waiting). Official site: https://www.autoitscript.com/

1. 下载 **AutoIt v3 Full Installation**（autoit-v3-setup.exe）/ Download **AutoIt v3 Full Installation** (autoit-v3-setup.exe)
2. 双击安装，全部默认即可（默认会关联 `.au3` 文件，双击即运行）/ Double-click to install, all defaults are fine (by default `.au3` files are associated — double-click to run)
3. 验证安装：确认 `C:\Program Files (x86)\AutoIt3\AutoIt3.exe` 存在 / Verify installation: confirm `C:\Program Files (x86)\AutoIt3\AutoIt3.exe` exists

**中文**：不想装 AutoIt 的话，也可以用自带的 Aut2Exe 把 `.au3` 编译成独立 exe（安装后开始菜单里有），但直接用 AutoIt3.exe 跑脚本最简单。

**English**: If you don't want to install AutoIt, you can use the bundled Aut2Exe to compile `.au3` into a standalone exe (available in the Start menu after installation), but running scripts directly with AutoIt3.exe is simplest.

---

## 三、配置与使用
## 3. Configuration & Usage

### 1. 配置账号（三个登录脚本共用）
### 1. Configure Credentials (shared by all three login scripts)

**中文**：把 `accounts.ini.example` 复制一份，重命名为 `accounts.ini`，和 `.au3` 脚本放同一目录，填入你的登录 ID 和密码：

**English**: Copy `accounts.ini.example`, rename it to `accounts.ini`, place it in the same directory as the `.au3` scripts, and fill in your login ID and password:

```ini
[myaccount]
user=你的登录ID / your_login_id
pw=你的密码 / your_password
```

**中文**：多账号就多复制几个 section 改名（如 `[ib_account]`、`[schwab_account]`），每个脚本开头 `$ACCOUNT` 指向对应 section 即可。

**English**: For multiple accounts, copy the section and rename it (e.g., `[ib_account]`, `[schwab_account]`), then point `$ACCOUNT` at the top of each script to the corresponding section.

### 2. 修改脚本配置区（按需）
### 2. Edit Script Config Section (as needed)

**中文**：每个脚本开头都有一段配置区，按你的实际安装路径 / 需求修改：

**English**: Each script has a config section at the top — modify it to match your installation paths and needs:

```autoit
; SCHWAB_autologin.au3
Global $ACCOUNT   = "myaccount"         ; accounts.ini 里的 section 名 / section name in accounts.ini
Global $TOS_EXE   = "C:\Program Files\thinkorswim\thinkorswim.exe"  ; thinkorswim 安装路径 / install path

; TWS_autologin.au3
Global $ACCOUNT   = "myaccount"         ; 同上 / same as above
Global $TWS_EXE   = "C:\Jts\tws.exe"    ; TWS 安装路径 / TWS install path
Global $TWS_CFG   = "C:\Jts"            ; jtsConfigDir 参数 / jtsConfigDir parameter

; IBGateway_autologin.au3
Global $ACCOUNT   = "myaccount"         ; 同上 / same as above
Global $GW_VER    = "1045"              ; ibgateway 子目录版本号(装新版本后改这里) / ibgateway subfolder version (change after upgrading)
Global $MODE      = "Live Trading"       ; "Live Trading" 真实盘 / "Paper Trading" 模拟盘 / "Live Trading" = real / "Paper Trading" = paper
Global $PY_SCRIPT = "C:\path\to\your_script.py"  ; 登录后要运行的脚本(改成你自己的) / script to run after login (change to your own)
Global $PY_RUN    = True                 ; 不想跑脚本就改 False / set False to skip running the script
```

### 3. 双击运行
### 3. Double-Click to Run

**中文**：三个脚本都是双击即跑，逻辑同构（防重复实例 → 读凭据 → 判断当前状态 → 启动/复用 → 填写 → 提交）。以 `SCHWAB_autologin.au3` 为例：

**English**: All three scripts run on double-click with the same logic (kill old instance → read credentials → check current state → launch/reuse → fill → submit). Using `SCHWAB_autologin.au3` as an example:

1. **杀掉本脚本旧实例**（重复双击不冲突，永远是最新一次生效）/ **Kill any old instance of this script** (repeated double-clicks are safe, latest run always wins)
2. 从 `accounts.ini` 读账号密码 / Read credentials from `accounts.ini`
3. 判断当前状态 / Check current state:
   - 登录窗口已开 → 直接去填写 / Login window already open → fill directly
   - thinkorswim 已在运行（已登录）→ 提示后退出，不重复登录 / thinkorswim already running (logged in) → notify and exit, no duplicate login
   - 都不是 → 通过 `explorer.exe` 启动 thinkorswim（见下方"为什么用 explorer 启动"）/ Neither → launch thinkorswim via `explorer.exe` (see "Why use explorer.exe to launch" below)
4. 等待"thinkorswim 更新程序"跑完（首次启动要先下载更新，最长等 10 分钟），期间右下角有气泡提示 + 小进度窗口 / Wait for "thinkorswim updater" to finish (first launch downloads updates, up to 10 min max), with tray tip + small progress window during the wait
5. 登录窗口出现后，自动**两步登录** / After login window appears, auto **two-step login**:
   - 第一步：点击 Login ID 输入框 → 剪贴板粘贴用户名 → 回车 / Step 1: click Login ID field → clipboard-paste username → Enter
   - 第二步：等密码页 → 点击密码框 → 剪贴板粘贴密码 → 回车 / Step 2: wait for password page → click password field → clipboard-paste password → Enter
6. 清空剪贴板（不残留密码），等登录窗口关闭确认成功 / Clear clipboard (no password residue), wait for login window to close to confirm success

---

## 四、thinkorswim 部分：为什么这么写（原理与踩坑，改代码前必读）
## 4. thinkorswim Section: Why It's Written This Way (Principles & Pitfalls — Read Before Modifying)

### 1. thinkorswim 登录框不是普通 Windows 控件
### 1. thinkorswim Login Fields Are Not Standard Windows Controls

**中文**：登录窗口是**内嵌 Chromium 网页**（SunAwtFrame 里嵌浏览器），AutoIt 的 `ControlSend`/`ControlSetText` 对它无效，只能：
- 用 `MouseClick` 按坐标点击输入框（坐标按窗口位置比例计算，不随窗口位置变化）
- 用 `WinGetPos` 动态取窗口位置，输入框 ≈ 窗口宽度 50%、高度 28% 处

**English**: The login window is an **embedded Chromium web page** (browser inside a SunAwtFrame). AutoIt's `ControlSend`/`ControlSetText` don't work on it — you can only:
- Use `MouseClick` to click input fields by coordinates (calculated as ratio of window position, independent of window location)
- Use `WinGetPos` to dynamically get window position; input field ≈ 50% window width, 28% window height

### 2. 不能直接 Send，要用剪贴板粘贴
### 2. Can't Use Send — Must Use Clipboard Paste

**中文**：中文输入法会把 `Send("your_userid")` 这类英文字符串吞掉或转成拼音候选。**剪贴板粘贴（`ClipPut` + `Ctrl+V`）完全绕过输入法**，任何输入法状态下都可靠。

**English**: Chinese IME will swallow or convert `Send("your_userid")`-style ASCII strings into pinyin candidates. **Clipboard paste (`ClipPut` + `Ctrl+V`) completely bypasses the IME** — reliable regardless of IME state.

### 3. 登录是"两步式"，不是一页填完
### 3. Login Is "Two-Step", Not One-Page

**中文**：第一页只有 Login ID（点 Continue），第二页才出密码框。脚本分两步：填 ID → 回车 → 等 4 秒 → 填密码 → 回车。

**English**: Page 1 only has Login ID (click Continue); page 2 reveals the password field. Script does two steps: fill ID → Enter → wait 4s → fill password → Enter.

### 4. 更新程序窗口会被误判成"已登录"
### 4. Updater Window Falsely Detected as "Already Logged In"

**中文**："thinkorswim 更新程序"窗口标题含 "thinkorswim" 字样，`WinExists("thinkorswim")` 子串匹配会命中它，导致脚本误判"已登录"直接退出。脚本里 `_IsMainRunning()` 用三层过滤排除：跳过隐藏窗口 / 跳过标题含"更新/Update/安装"的窗口 / 窗口进程必须是 thinkorswim.exe。

**English**: The "thinkorswim updater" window title contains "thinkorswim", so `WinExists("thinkorswim")` substring match hits it, causing the script to falsely detect "already logged in" and exit. The `_IsMainRunning()` function uses three-layer filtering to exclude it: skip hidden windows / skip windows with "更新/Update/安装" in title / window process must be thinkorswim.exe.

### 5. 用 explorer.exe 启动，而不是 AutoIt 的 Run
### 5. Launch via explorer.exe, Not AutoIt's Run

**中文**：直接 `Run()` 启动时，thinkorswim 会被识别为脚本子进程，更新下载会被安全软件卡住，导致更新窗口一直挂着、登录界面出不来。改用 `explorer.exe "thinkorswim.exe"` 走 Windows Shell（和手动双击同一上下文），更新 20~35 秒即可完成。

**English**: When launched via `Run()`, thinkorswim is treated as a child process of the script — security software may block update downloads, causing the updater window to hang and the login UI to never appear. Using `explorer.exe "thinkorswim.exe"` goes through the Windows Shell (same context as manual double-click), and updates finish in 20–35 seconds.

### 6. 每次启动都先下载更新，很慢 → 用开机计划任务预热
### 6. Every Launch Downloads Updates First → Pre-warm with Boot Task

**中文**：thinkorswim 每次启动先跑更新下载（3~5 分钟）。解法：**开机后自动跑一次本脚本**，等你要用时早已更新完、登录好（见下一节）。

**English**: thinkorswim runs an update download on every launch (3–5 min). Solution: **auto-run this script once on boot** — by the time you need it, updates are done and login is complete (see next section).

---

## 五、IBKR TWS / Gateway 部分：为什么这么写
## 5. IBKR TWS / Gateway Section: Why It's Written This Way

### 1. TWS 启动卡在"更新检查"，加官方开关跳过
### 1. TWS Stuck on "Update Check" — Add Official Flag to Skip

**中文**：`tws.exe` 每次启动先连 IB 下载服务器做更新检查，检查不动就卡住（表现为"长时间转圈不出现登录窗"）。解法是启动参数加 `-J-DskipUpdateCheck=true`（反编译 twslaunch jar 确认的 `LauncherProperties.skipUpdateCheck` 布尔属性）。真正需要升级 TWS 时，手动跑一次不带该参数的启动即可。

**English**: `tws.exe` connects to IB's download server for an update check on every launch — if it can't connect, it hangs (spinning without showing the login window). Solution: add `-J-DskipUpdateCheck=true` launch parameter (confirmed by decompiling twslaunch jar — `LauncherProperties.skipUpdateCheck` boolean property). When you actually need to upgrade TWS, manually run once without this parameter.

```
C:\Jts\tws.exe -J-DjtsConfigDir="C:\Jts" -J-DskipUpdateCheck=true
```

### 2. 走代理上网时，IB 域名必须直连
### 2. When Using a Proxy, IB Domains Must Go DIRECT

**中文**：若你开着 Clash 等系统代理，TWS 流量被代理劫持会出现"网络错误无法登录"。要在代理规则里给 IB 域名加 DIRECT（以 Clash 的 Merge.yaml 为例，插到规则最前面）：

**English**: If you have a system proxy like Clash running, TWS traffic gets hijacked by the proxy, causing "network error, cannot login". Add DIRECT rules for IB domains in your proxy config (example for Clash's Merge.yaml — insert at the top of rules):

```yaml
- DOMAIN-SUFFIX,ibllc.com,DIRECT            # TWS 登录服务器 / TWS login server ndc1.ibllc.com:4000/4001
- DOMAIN-SUFFIX,ibkr.com,DIRECT
- DOMAIN-SUFFIX,interactivebrokers.com,DIRECT   # TWS 更新下载 / TWS update download
```

### 3. Java AWT 登录窗同样没有标准控件
### 3. Java AWT Login Window Also Has No Standard Controls

**中文**：TWS / Gateway 的登录窗是 Java Swing/AWT（标题 `Login - Interactive Brokers` 等），和 thinkorswim 一样无法 `ControlSend`，只能坐标点击 + 剪贴板粘贴。窗口是固定尺寸，坐标按窗口位置 + 偏移量计算，不随窗口移动而漂移。

**English**: TWS / Gateway login window is Java Swing/AWT (title `Login - Interactive Brokers` etc.), same as thinkorswim — `ControlSend` doesn't work, only coordinate click + clipboard paste. The window is fixed-size; coordinates are calculated as window position + offset, not drifting with window movement.

### 4. 手机 IB Key 2FA 是绕不过的最后一环
### 4. Mobile IB Key 2FA Is the Unavoidable Last Step

**中文**：提交凭据后 IB 会向手机推送 IB Key 确认（或要求输入推送号码）。脚本在这一步**停住等你掏手机点确认**，窗口标题从 Login 变成 "Second Factor Authentication..."。这是 IB 的安全设计，无法（也不应该）自动化——所以"全自动"的准确含义是"自动填到只差最后一下手机确认"。

**English**: After submitting credentials, IB pushes an IB Key confirmation to your phone (or asks for a push number). The script **stops here and waits for you to tap confirm on your phone** — the window title changes from Login to "Second Factor Authentication...". This is IB's security design — cannot (and should not) be automated. So "fully automatic" really means "auto-fills everything up to the final phone confirmation".

### 5. Gateway 的两个专属配置
### 5. Gateway-Specific Configuration

- **中文**：**ApiOnly 模式**：`C:\Jts\jts.ini` 里 `ApiOnly=true` 让 Gateway 登录后不显示图表界面，只留 API 端口（配合程序化交易，内存占用小）
- **English**: **ApiOnly mode**: Set `ApiOnly=true` in `C:\Jts\jts.ini` to make Gateway hide the chart UI after login, keeping only the API port (for programmatic trading, lower memory)
- **中文**：**Live/Paper 切换**：登录窗有模式下拉（Live Trading / Paper Trading），脚本配置区 `$MODE` 变量选择
- **English**: **Live/Paper toggle**: Login window has a mode dropdown (Live Trading / Paper Trading); select via `$MODE` variable in script config
- **中文**：登录成功后可自动运行你的 Python 数据脚本（`$PY_SCRIPT` + `$PY_RUN`），实现"登录完直接开始跑数据"
- **English**: After successful login, auto-run your Python data script (`$PY_SCRIPT` + `$PY_RUN`) — "login done, data starts running immediately"

---

## 六、注册"开机自动登录"计划任务
## 6. Register "Boot Auto-Login" Scheduled Task

**中文**：三个登录脚本都可以照此注册（把 `-Argument` 里的脚本名换掉即可）。以 thinkorswim 为例，以管理员 PowerShell 运行：

**English**: All three login scripts can be registered the same way (just swap the script name in `-Argument`). Using thinkorswim as example — run in admin PowerShell:

```powershell
$action = New-ScheduledTaskAction -Execute 'C:\Program Files (x86)\AutoIt3\AutoIt3.exe' -Argument '"C:\your\folder\SCHWAB_autologin.au3"'
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:COMPUTERNAME\$env:USERNAME"
$trigger.Delay = 'PT3M'   # 登录后 3 分钟再跑，等系统/网络就绪 / Run 3 min after logon, wait for system/network ready
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'SchwabTosLogin' -TaskPath '\' -Principal (New-ScheduledTaskPrincipal -UserId "$env:COMPUTERNAME\$env:USERNAME" -LogonType Interactive) -Action $action -Trigger $trigger -Settings $settings -Force -Description 'thinkorswim boot auto-login'
```

**踩坑记录（重要，照抄才不会失败）/ Pitfall Log (important — follow exactly or it will fail):**

1. **中文**：根路径（TaskPath '\'）任务必须管理员权限注册。普通 PowerShell 会报 `Access denied (0x80070005)`。
   **English**: Root-path (TaskPath '\') tasks require admin privileges to register. Regular PowerShell will get `Access denied (0x80070005)`.

2. **中文**：必须显式指定 Principal 为你自己的登录账户。如果用"以管理员身份运行"的 PowerShell 注册，任务会挂在管理员账户名下；而 AutoIt 脚本需要在**你登录的桌面会话**里点鼠标、发键盘，账户不匹配会因 Windows 会话隔离看不到窗口、全部失效。
   **English**: You must explicitly set Principal to your own login account. If you register from an "Run as administrator" PowerShell, the task is attached to the admin account — but AutoIt scripts need to click mouse and send keys in **your interactive desktop session**. Account mismatch causes Windows session isolation to hide all windows, making everything fail.

3. **中文**：提权注册后，普通会话可能查不到任务（`Get-ScheduledTask` 看不到）。验证任务真身用这两招：
   - 提权脚本内部自查并写日志文件（提权进程的输出读不回来，只能落盘）
   - 直接看 `C:\Windows\System32\Tasks\` 目录下是否有同名 XML 文件（需管理员权限）

   **English**: After registering with elevated privileges, the regular session may not see the task (`Get-ScheduledTask` shows nothing). Verify the task actually exists with these two methods:
   - Self-check inside the elevated script and write to a log file (elevated process output can't be read back, must persist to disk)
   - Check `C:\Windows\System32\Tasks\` for a matching XML file (requires admin privileges)

4. **中文**：当日触发点错过属正常：如果注册时间晚于当天的定时触发点（比如 12:00 的任务 12:05 才注册好），当天不会补跑，次日起正常。
   **English**: Missing the day's trigger is normal: if registration happens after the day's scheduled trigger (e.g., a 12:00 task registered at 12:05), it won't run that day — it works normally from the next day.

---

## 七、Schwab API token 自动续期（schwab_token_keeper.py）
## 7. Schwab API Token Auto-Renewal (schwab_token_keeper.py)

**中文**：Schwab API 的 refresh token 只有 7 天寿命，过期就要人工浏览器重新授权。`schwab_token_keeper.py`（已随附本目录，配合 Windows 计划任务）可实现全自动续期：

**English**: Schwab API refresh tokens expire in 7 days — manual browser re-authorization is required after expiry. `schwab_token_keeper.py` (included in this directory, paired with Windows Task Scheduler) enables fully automatic renewal:

- **中文**：每天 12:00 / 21:00 / 登录后 10 分钟 三重触发，检查 token 年龄：不满 5 天只做健康检查（顺带刷新 access token 写回）
- **English**: Triple triggers — daily 12:00 / 21:00 / 10 min after logon — check token age: if under 5 days, only health check (refreshes access token and writes it back)
- **中文**：满 5 天且在美股闭市时段（北京 04:00–21:20）→ 无头浏览器自动重授权（需先把账号/密码/TOTP 存入 Windows 凭据管理器，`--store-creds`）
- **English**: If 5+ days old and during US market-closed hours (Beijing 04:00–21:20) → headless browser auto re-authorization (first store account/password/TOTP in Windows Credential Manager via `--store-creds`)
- **中文**：写 tokens.db 前自动备份，自检失败自动回滚，零侵入不改动主程序
- **English**: Auto-backup before writing tokens.db; auto-rollback on self-check failure; zero intrusion — doesn't modify the main program
- **中文**：依赖：`requests`、`playwright`（无头浏览器）、`keyring`（Windows 凭据管理器）、`pyotp`（TOTP）；token 文件位置和 API 用途由脚本顶部 `BASE_DIR` 相对定位，放到你的工程根目录运行
- **English**: Dependencies: `requests`, `playwright` (headless browser), `keyring` (Windows Credential Manager), `pyotp` (TOTP); token file location and API usage are relative to `BASE_DIR` at the top of the script — place it in your project root directory to run

**中文**：计划任务注册（管理员 PowerShell，三重触发：每天 12:00、每天 21:00 晚间兜底、登录后 10 分钟）：

**English**: Task Scheduler registration (admin PowerShell, triple triggers: daily 12:00, daily 21:00 evening fallback, 10 min after logon):

```powershell
$action = New-ScheduledTaskAction -Execute 'C:\Users\<you>\AppData\Local\Programs\Python\Python311\pythonw.exe' -Argument '"C:\your\project\schwab_token_keeper.py" --once' -WorkingDirectory 'C:\your\project'
$t1 = New-ScheduledTaskTrigger -Daily -At '12:00'
$t2 = New-ScheduledTaskTrigger -Daily -At '21:00'   # 错过 12:00 的当晚兜底 / Evening fallback if 12:00 was missed
$t3 = New-ScheduledTaskTrigger -AtLogOn -User "$env:COMPUTERNAME\$env:USERNAME"
$t3.Delay = 'PT10M'   # 避开 TOS 自动登录的鼠标键盘占用 / Avoid TOS auto-login mouse/keyboard activity
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'SchwabTokenKeeper' -TaskPath '\' -Principal (New-ScheduledTaskPrincipal -UserId "$env:COMPUTERNAME\$env:USERNAME" -LogonType Interactive) -Action $action -Trigger @($t1, $t2, $t3) -Settings $settings -Force -Description 'Schwab 7-day refresh token auto-renewal'
```

**说明 / Notes:**
- **中文**：pythonw.exe 用**有 requests 依赖的 Python**（keeper 的 `__pycache__` 是 cpython-311 → 选 3.11；勿用没有依赖的解释器）
- **English**: Use a pythonw.exe that **has the `requests` dependency** (keeper's `__pycache__` is cpython-311 → use Python 3.11; do not use an interpreter that lacks the dependencies)
- **中文**：keeper 自带单实例锁（1 小时超时），多触发器重叠不会并发跑坏 tokens.db
- **English**: Keeper has a built-in single-instance lock (1-hour timeout) — overlapping triggers won't run concurrently and corrupt tokens.db
- **中文**：首次使用先跑一次 `python schwab_token_keeper.py --login` 有头校准，并用 `--store-creds` 存凭据
- **English**: For first-time use, run `python schwab_token_keeper.py --login` once for headed calibration, and use `--store-creds` to store credentials
- **中文**：运行日志：`<你的工程目录>\.schwabdev\keeper.log`
- **English**: Run log: `<your project dir>\.schwabdev\keeper.log`

---

## 八、目录上传前检查清单
## 8. Pre-Upload Checklist

- [ ] `.gitignore` **已就位**（自动排除 `accounts.ini`、`*.db`、`*.log`、`.schwabdev/`、`__pycache__/`、`.env` 等）/ **`.gitignore` in place** (auto-excludes `accounts.ini`, `*.db`, `*.log`, `.schwabdev/`, `__pycache__/`, `.env`, etc.)
- [ ] `accounts.ini` **已删除**（只保留 `accounts.ini.example` 模板）/ **deleted** (only `accounts.ini.example` template remains)
- [ ] `.au3` 脚本里无明文账号密码（本方案从 ini 读，天然干净；若你用的是旧版明文脚本，先改成 ini 方式）/ No hardcoded passwords in `.au3` scripts (this solution reads from ini — naturally clean; if using old hardcoded scripts, convert to ini method first)
- [ ] 全目录 grep 个人账号名 / 密码串无命中（脚本配置区已统一为 `myaccount` 占位）/ Grep the entire directory for personal account names / password strings — zero hits (script config uses `myaccount` placeholder)
- [ ] 文档中的个人路径（`C:\Users\...`、计算机名等）已替换成通用占位或注明"按需修改" / Personal paths in docs (`C:\Users\...`, computer names, etc.) replaced with generic placeholders or "modify as needed"
- [ ] `.bak` 历史版本（可能含明文密码）不放进本目录 / `.bak` historical versions (may contain plaintext passwords) not included in this directory
