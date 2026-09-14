; TWS Auto-Login Script (2026-09-06 updated, compatible with TWS 10.50)
; New login window title is "Login" (EN) or "登录" (CN) — this script handles both
; After login submit, a Second Factor Authentication window appears (IB Key mobile confirmation)
; Confirm the push on your phone IB Key / IBKR Mobile within ~70 sec or TWS auto-restarts login (script retries)

; ===================== Config =====================
Global $ACCOUNT   = "myaccount"         ; Section name in accounts.ini — change only this to switch accounts
Global $TWS_EXE   = "C:\Jts\tws.exe"    ; TWS main executable
Global $TWS_CFG   = "C:\Jts"            ; jtsConfigDir
; =================================================

; 2FA window mouse hover point (as ratio of window client area, measured with mouse probe script)
Global $QR_X = 0.72 ; Higher = more to the right
Global $QR_Y = 0.80 ; Higher = lower

#include <Misc.au3>
Opt("MouseCoordMode", 2) ; Mouse coordinates relative to window client area

; ---------- Kill other instances of this script ----------
; Each double-click should start fresh, avoid multiple instances fighting over mouse / duplicate TWS login
; Principle: AutoIt process has a hidden "AutoIt main window",
;            use AutoItWinSetTitle to give it a unique title (script name + account + PID),
;            then WinList all matching windows, ProcessClose any whose PID isn't ours.
Func _KillSameScript()
    Local $sMarker = "TWS_" & $ACCOUNT & "_" & @ScriptName & "_"
    AutoItWinSetTitle($sMarker & @AutoItPID)
    Sleep(300) ; Let title write take effect, also give old instance time to do the same

    Local $aList = WinList("[REGEXPTITLE:" & $sMarker & "\d+]")
    Local $nKilled = 0
    For $i = 1 To $aList[0][0]
        Local $pid = WinGetProcess($aList[$i][1])
        If $pid > 0 And $pid <> @AutoItPID Then
            ProcessClose($pid)
            $nKilled += 1
        EndIf
    Next

    If $nKilled > 0 Then
        ; Wait for killed processes to exit, release any TWS login window focus / IME state they hold
        Local $t = TimerInit()
        While TimerDiff($t) < 5000
            Local $stillAlive = False
            For $i = 1 To $aList[0][0]
                Local $pid2 = WinGetProcess($aList[$i][1])
                If $pid2 > 0 And $pid2 <> @AutoItPID And ProcessExists($pid2) Then
                    $stillAlive = True
                    ExitLoop
                EndIf
            Next
            If Not $stillAlive Then ExitLoop
            Sleep(200)
        WEnd
        ConsoleWrite("[TWS] Killed " & $nKilled & " existing instance(s) of " & @ScriptName & @CRLF)
    EndIf
EndFunc   ;==>_KillSameScript

; ---------- Read credentials from accounts.ini ----------
Global $sIni = @ScriptDir & "\accounts.ini"
Global $user = IniRead($sIni, $ACCOUNT, "user", "")
Global $pw   = IniRead($sIni, $ACCOUNT, "pw", "")

If $user = "" Or $pw = "" Then
    MsgBox(16, "TWS Auto-Login", "Failed to read credentials!" & @CRLF & @CRLF & _
            "File: " & $sIni & @CRLF & _
            "Confirm section [" & $ACCOUNT & "] exists in accounts.ini and user / pw are not empty.")
    Exit
EndIf

If Not FileExists($TWS_EXE) Then
    MsgBox(16, "TWS Auto-Login", "TWS not found, check $TWS_EXE config." & @CRLF & $TWS_EXE)
    Exit
EndIf

; Kill other instances of this script first (avoid mouse fighting)
_KillSameScript()

; Login window title — compatible with both EN and CN
$sLogin = "[REGEXPTITLE:(?i)^(登录|Login)$]"
; Second factor authentication window
$s2FA = "Second Factor Authentication"
; Main window after successful login (title contains account number + Interactive Brokers)
$sMain = "[REGEXPTITLE:(?i)Interactive Brokers]"

; Close login window if it already exists
If WinExists($sLogin) Then
    WinClose($sLogin)
    WinWaitClose($sLogin, "", 15)
EndIf

; Launch TWS
; [2026-09-07 Fix] Add -J-DskipUpdateCheck=true to skip startup update check (equivalent to
; Gateway fixed-version behavior). Update check uses direct connection to download server
; which doesn't work on this machine — was the root cause of "Update Failed".
Run('"' & $TWS_EXE & '" -J-DskipUpdateCheck=true -J-DjtsConfigDir=' & $TWS_CFG, $TWS_CFG)

; ---------- Wait for login flow to appear (max 5 min), handle "Update Failed" popup ----------
; Update failed popup is install4j self-drawn UI (no control handle), title "Update Failed",
; "Try Again" button at bottom-right — activate popup, click by client-area ratio, Enter as fallback
; (with skipUpdateCheck this shouldn't appear, kept as safety net)
Global $sUpdFail = "[REGEXPTITLE:(?i)Update Failed|更新失败]"
Local $tWait = TimerInit()
Local $nRetry = 0
While TimerDiff($tWait) < 300000
    ; TWS may auto-submit if credentials are saved, login window flashes by to 2FA — all three windows count as "arrived"
    If WinExists($sLogin) Or WinExists($s2FA) Or WinExists($sMain) Then ExitLoop

    If WinExists($sUpdFail) Then
        $nRetry += 1
        If $nRetry > 10 Then
            MsgBox(48, "TWS Auto-Login", "Update failed after 10 auto-retries." & @CRLF & _
                    "Please enable Clash TUN mode, run TWS manually once to update, then run this script.")
            Exit
        EndIf
        TrayTip("TWS Auto-Login", "Update failed popup detected, auto-clicking Try Again (attempt " & $nRetry & ")...", 5, 1)
        WinActivate($sUpdFail)
        WinWaitActive($sUpdFail, "", 5)
        Local $aC = WinGetClientSize($sUpdFail)
        If IsArray($aC) Then
            MouseClick("left", Int($aC[0] * 0.89), Int($aC[1] * 0.90), 1, 0) ; Try Again is at bottom-right
            Sleep(1500)
            If WinExists($sUpdFail) And WinActive($sUpdFail) Then Send("{ENTER}") ; Fallback: default button
        EndIf
        Sleep(20000) ; Allow time for update retry (popup may disappear and rebuild)
    Else
        Sleep(2000)
    EndIf
WEnd

If Not WinExists($sLogin) And Not WinExists($s2FA) And Not WinExists($sMain) Then
    MsgBox(48, "TWS Auto-Login", "TWS login window not detected within 5 minutes, script exiting.")
    Exit
EndIf

Local $bOK = False
For $n = 1 To 5 ; Max 5 retries (TWS restarts login window after 2FA timeout)
    ; If credentials are remembered, TWS auto-submits and login window is gone — don't manually fill
    If WinExists($sLogin) Then _FillAndLogin()
    Local $bHover = False ; Mouse positioning done once only
    ; Wait for result: main window / 2FA window / login window reappears, poll for 150 sec
    Local $t = TimerInit()
    While TimerDiff($t) < 150000
        If WinExists($sMain) Then
            $bOK = True
            ExitLoop 2
        EndIf
        If WinExists($s2FA) Then
            If Not $bHover Then
                ; Move mouse near "Login with QR code" area (right ~28%, bottom ~20%), move only, no click
                WinActivate($s2FA)
                WinWaitActive($s2FA, "", 5)
                Local $a2 = WinGetClientSize($s2FA)
                MouseMove(Int($a2[0] * $QR_X), Int($a2[1] * $QR_Y), 0) ; Instant move, no animation
                $bHover = True
            EndIf
        EndIf
        If WinExists($sLogin) Then ExitLoop ; 2FA timeout, TWS restarted login window, retry
        Sleep(2000)
    WEnd
    If $bOK Then ExitLoop
    ; Wait for login window to reappear (after 2FA timeout TWS returns to login page); if user confirms 2FA now, main window counts as success
    Local $tRe = TimerInit()
    While TimerDiff($tRe) < 120000
        If WinExists($sMain) Then $bOK = True
        If $bOK Or WinExists($sLogin) Then ExitLoop
        Sleep(1000)
    WEnd
    If $bOK Then ExitLoop
    If Not WinExists($sLogin) Then ExitLoop
    Sleep(2000)
Next

If $bOK Then
    ; Wait for main window to be fully ready
    WinWaitActive($sMain, "", 60)
    Sleep(3000)
;    Run('pythonw "C:\path\to\your_script.py"') ; Run Python script
Else
    TrayTip("TWS Auto-Login", "Login not detected after multiple attempts, please check manually.", 10, 2)
EndIf

; ---------- Fill username/password and click login ----------
Func _FillAndLogin()
    WinActivate($sLogin)
    WinWaitActive($sLogin, "", 15)
    Sleep(2000) ; Wait for UI to fully render

    ; Switch to English keyboard layout (prevent Chinese IME from interfering with password input)
    Local $hWnd = WinGetHandle($sLogin)
    Local $ret = DllCall("user32.dll", "long", "LoadKeyboardLayout", "str", "04090409", "int", 1 + 0)
    DllCall("user32.dll", "ptr", "SendMessage", "hwnd", $hWnd, "int", 0x50, "int", 1, "int", $ret[0])

    ; New login UI is Java-drawn with no standalone control handles — position by client-area ratio (adapts to different resolution/DPI scaling)
    Local $aC = WinGetClientSize($sLogin)
    Local $xField = Int($aC[0] * 0.734) ; Input field horizontal center
    Local $yUser  = Int($aC[1] * 0.447) ; Username input
    Local $yPw    = Int($aC[1] * 0.515) ; Password input
    Local $yBtn   = Int($aC[1] * 0.651) ; Login button

    MouseClick("left", $xField, $yUser, 1, 0) ; Speed 0: instant, no glide animation
    Sleep(400)
    Send("{END}+{HOME}{DEL}") ; Clear existing content (avoid Ctrl+A to prevent Windows locator ripple effect)
    Send($user)
    Sleep(300)

    MouseClick("left", $xField, $yPw, 1, 0)
    Sleep(400)
    Send("{END}+{HOME}{DEL}")
    Send($pw)
    Sleep(300)

    ; Auto-click the "Login" button
    MouseClick("left", $xField, $yBtn, 1, 0)
EndFunc   ;==>_FillAndLogin
