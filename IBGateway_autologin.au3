; ============================================================
; IBKR Gateway Auto-Login Script
; ============================================================

#include <Misc.au3>

; ===================== Config =====================
Global $ACCOUNT   = "myaccount"         ; Section name in accounts.ini — change only this to switch accounts
Global $GW_VER    = "1045"             ; ibgateway subfolder version number
Global $MODE      = "Live Trading"     ; "Live Trading" = real / "Paper Trading" = paper
Global $PY_SCRIPT = "C:\path\to\your_script.py" ; Script to run after login (change to your own)
Global $PY_RUN    = True               ; Set False to skip running the script
; True = ApiOnly=true already set in jts.ini, Gateway starts in IB API mode, skip API Type click in login window
; False = Script clicks "IB API" in login window (requires Java control accessibility or coordinate fallback)
Global $API_VIA_INI = True

; Window titles
Global $sLogin = "IBKR Gateway"                          ; Login window
Global $s2FA   = "Second Factor Authentication"          ; Second factor window (IB Key)
Global $sMain  = "[REGEXPTITLE:(?i)Interactive Brokers]" ; Main window after successful login
; =================================================

; ---------- Kill other instances of this script (avoid keyboard fighting) ----------
; Each double-click should start fresh: not "reject new instance" but "kill old, then start"
Func _KillSameScript()
    Local $sMarker = "IBGateway_" & $ACCOUNT & "_" & @ScriptName & "_"
    AutoItWinSetTitle($sMarker & @AutoItPID)
    Sleep(300)
    Local $aList = WinList("[REGEXPTITLE:" & $sMarker & "\d+]")
    Local $nKilled = 0
    For $i = 1 To $aList[0][0]
        Local $pid = WinGetProcess($aList[$i][1])
        If $pid > 0 And $pid <> @AutoItPID Then
            ProcessClose($pid)
            $nKilled += 1
        EndIf
    Next
    If $nKilled > 0 Then Sleep(1500) ; Wait for old instance to exit, release any Gateway login window focus
EndFunc   ;==>_KillSameScript

; Kill other instances on launch (user expects fresh start each time)
_KillSameScript()

; ---------- Read credentials from accounts.ini ----------
Global $sIni = @ScriptDir & "\accounts.ini"
Global $user = IniRead($sIni, $ACCOUNT, "user", "")
Global $pw   = IniRead($sIni, $ACCOUNT, "pw", "")

If $user = "" Or $pw = "" Then
    MsgBox(16, "IBKR Auto-Login", "Failed to read credentials!" & @CRLF & @CRLF & _
            "File: " & $sIni & @CRLF & _
            "Confirm section [" & $ACCOUNT & "] exists in accounts.ini and user / pw are not empty.")
    Exit
EndIf

If Not FileExists("C:\Jts\ibgateway\" & $GW_VER & "\ibgateway.exe") Then
    MsgBox(16, "IBKR Auto-Login", "Gateway not found, check version config $GW_VER." & @CRLF & _
            "C:\Jts\ibgateway\" & $GW_VER & "\ibgateway.exe")
    Exit
EndIf

; ---------- Close any running Gateway ----------
If WinExists($sLogin) Then
    WinClose($sLogin)
    WinWaitClose($sLogin, "", 15)
EndIf

; ---------- Launch Gateway ----------
Global $sExe = "C:\Jts\ibgateway\" & $GW_VER & "\ibgateway.exe"
Run($sExe & " -J-DjtsConfigDir=C:\Jts\ibgateway\" & $GW_VER)

; Wait for login window to appear (max 5 min, first launch/version upgrade is slow)
If WinWait($sLogin, "", 300) = 0 Then
    MsgBox(48, "IBKR Auto-Login", "IBKR Gateway login window not detected within 5 minutes, script exiting.")
    Exit
EndIf

; ---------- Fill and submit login, auto-retry on failure ----------
Local $bOK = False
For $n = 1 To 3
    _FillAndLogin()

    ; Poll for result: main window (success) / 2FA window (need phone confirmation) / timeout then retry
    ; Using polling instead of WinWait so we proceed immediately on success
    Local $t = TimerInit()
    Local $bTip = False
    While TimerDiff($t) < 180000 ; Max 3 min (includes time for phone 2FA confirmation)
        If WinExists($sMain) Then
            $bOK = True
            ExitLoop 2 ; Break out of While and For
        EndIf
        If WinExists($s2FA) And Not $bTip Then
            TrayTip("IBKR Auto-Login", "Please confirm second factor on phone IB Key / IBKR Mobile (within ~70 sec)...", 10, 1)
            $bTip = True
        EndIf
        Sleep(2000)
    WEnd

    TrayTip("IBKR Auto-Login", "Attempt " & $n & " failed, retrying in 3 sec...", 5, 2)
    Sleep(3000)
Next

; ---------- Login result handling ----------
If $bOK Then
    WinActivate($sMain)
    WinWaitActive($sMain, "", 30)
    Sleep(3000) ; Wait for main window to be fully ready
    TrayTip("IBKR Auto-Login", "Login successful, account: " & $user, 5, 1)
    If $PY_RUN Then
        If FileExists($PY_SCRIPT) Then
            Run('pythonw "' & $PY_SCRIPT & '"') ; Run Python script
        Else
            MsgBox(48, "IBKR Auto-Login", "Login succeeded, but Python script not found:" & @CRLF & $PY_SCRIPT)
        EndIf
    EndIf
Else
    MsgBox(48, "IBKR Auto-Login", "Login not detected after multiple attempts, please check manually." & @CRLF & @CRLF & _
            "If IB Key two-step verification is enabled, confirm you approved it on your phone in time.")
EndIf

; =================================================
; Function: Switch API Type to "IB API"
; Note: IB Gateway defaults to IBKR Desktop after launch — must switch to IB API before login
;       Different Gateway versions have identical control Class / text, use ControlCommand to find button by text
; =================================================
Func _SwitchAPIToIBAPI()
    ; ApiOnly=true in jts.ini presets IB API mode, login window no longer needs API Type selection
    If $API_VIA_INI Then Return True

    ; If IB API is already checked, skip (re-clicking would uncheck it)
    Local $bChecked = ControlCommand($sLogin, "", "[TEXT:IB API]", "IsChecked", "")
    If @error = 0 And $bChecked = 1 Then Return True
    ControlCommand($sLogin, "", "[TEXT:IB API]", "Check", "")
    Sleep(500)
    ; Fallback to client-area coordinate click if control text search fails (old Gateway versions)
    ; Coordinates measured with mouse probe script: relative ratio of client area
    ;   Range [0,1]: within IB Gateway login window client area
    ;   Out of range: active window is not IB Gateway (e.g. taskbar), skip coordinate fallback
    Local $aC = WinGetClientSize($sLogin)
    If $aC[0] > 0 And $aC[1] > 0 Then
        ; User-measured IB API absolute screen coordinates: (326, 439)
        ;   These depend on the IB Gateway login window position at that time, invalid after window moves
        ;   Robust approach: center or fix window position, then re-measure relative ratio
        Local $relX = 0, $relY = 0
        If $relX > 0 And $relY > 0 And $relX <= 1 And $relY <= 1 Then
            Local $xAPI = Int($aC[0] * $relX)
            Local $yAPI = Int($aC[1] * $relY)
            MouseClick("left", $xAPI, $yAPI, 1, 0)
            Sleep(500)
        EndIf
    EndIf
EndFunc

; =================================================
; Function: Fill username/password and auto-submit login
; =================================================
Func _FillAndLogin()
    WinActivate($sLogin)
    WinWaitActive($sLogin, "", 15)
    Sleep(2000) ; Wait for UI to fully render

    ; ---- Switch API Type to IB API (must be before username/password) ----
    _SwitchAPIToIBAPI()
    Sleep(500)

    ; Switch to English keyboard layout, prevent Chinese IME from interfering with password input
    Local $hWnd = WinGetHandle($sLogin)
    Local $ret = DllCall("user32.dll", "long", "LoadKeyboardLayout", "str", "04090409", "int", 1 + 0)
    DllCall("user32.dll", "ptr", "SendMessage", "hwnd", $hWnd, "int", 0x50, "int", 1, "int", $ret[0])

    ; Click trading mode tab (Live/Paper), also brings focus into the form area
    ControlClick($sLogin, "", $MODE)
    Sleep(800)

    ; ---- Username ----
    Send("{END}+{HOME}{DEL}") ; Clear existing content (avoid Ctrl+A to prevent Windows locator ripple)
    Sleep(200)
    Send($user)
    Sleep(300)

    ; ---- Password ----
    Send("{TAB}") ; Move to password field
    Sleep(300)
    Send("{END}+{HOME}{DEL}")
    Sleep(200)
    Send($pw)
    Sleep(300)

    ; ---- Auto-submit login (Enter triggers it, no manual press needed) ----
    Send("{ENTER}")
EndFunc   ;==>_FillAndLogin
