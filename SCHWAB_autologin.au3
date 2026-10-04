; ============================================================
; thinkorswim Auto-Login Script
; ============================================================

#include <Misc.au3>
#include <GUIConstantsEx.au3>
#include <WindowsConstants.au3>

; ===================== Config =====================
Global $ACCOUNT   = "myaccount"         ; Section name in accounts.ini — change only this to switch accounts
Global $TOS_EXE   = "C:\Program Files\thinkorswim\thinkorswim.exe"
Global $sLogin    = "Logon to thinkorswim" ; Login window title
Global $sMainKey  = "thinkorswim"          ; Main window keyword (partial match, must exclude updater)

Global $T_BOOT    = 300 ; Max seconds to wait for login window to appear (thinkorswim may run updater first)
Global $T_LOGIN   = 120 ; Max seconds to wait for login window to close (confirm success)
Global $T_UPDATE  = 600 ; Max seconds to wait for update to complete (10 min)
Global $MAX_TRY   = 2   ; Max login attempts (total, not retries). If all fail, stop trying
                        ; — repeated failures usually mean the server is under maintenance.
; =================================================

; ---------- Kill other instances of this script ----------
; Each double-click should start fresh: not "reject new instance" but "kill old, then start"
Func _KillSameScript()
    Local $sMarker = "thinkorswim_" & $ACCOUNT & "_" & @ScriptName & "_"
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
    If $nKilled > 0 Then Sleep(1500) ; Wait for old instance to exit, release any window focus it holds
EndFunc   ;==>_KillSameScript

_KillSameScript()

; ---------- Read credentials from accounts.ini ----------
Global $sIni = @ScriptDir & "\accounts.ini"
Global $user = IniRead($sIni, $ACCOUNT, "user", "")
Global $pw   = IniRead($sIni, $ACCOUNT, "pw", "")

If $user = "" Or $pw = "" Then
    MsgBox(16, "thinkorswim Auto-Login", "Failed to read credentials!" & @CRLF & @CRLF & _
            "File: " & $sIni & @CRLF & _
            "Confirm section [" & $ACCOUNT & "] exists in accounts.ini and user / pw are not empty.")
    Exit
EndIf

If Not FileExists($TOS_EXE) Then
    MsgBox(16, "thinkorswim Auto-Login", "thinkorswim not found, check $TOS_EXE config." & @CRLF & $TOS_EXE)
    Exit
EndIf

; ---------- Check if a title belongs to an updater/installer window ----------
Func _IsUpdateWindow($sTitle)
    If $sTitle = "" Then Return False
    ; Matches: Update / Install / Setup (both EN and CN)
    If StringRegExp($sTitle, "(?i)(更新|Update|安装|Install|Setup)") Then Return True
    Return False
EndFunc   ;==>_IsUpdateWindow

; ---------- Get process name for a PID (returns "" on failure) ----------
Func _WinProcName($pid)
    If $pid <= 0 Then Return ""
    Local $objWMI = ObjGet("winmgmts:\\.\root\cimv2")
    Local $col = $objWMI.ExecQuery("SELECT Name FROM Win32_Process WHERE ProcessId=" & $pid)
    For $o In $col
        Return $o.Name
    Next
    Return ""
EndFunc   ;==>_WinProcName

; ---------- Check if main window is truly running (excludes updater) ----------
; Old code WinExists("thinkorswim") matches "thinkorswim Updater" too, causing false positive
Func _IsMainRunning()
    Local $aList = WinList("[REGEXPTITLE:(?i)" & $sMainKey & "]")
    For $i = 1 To $aList[0][0]
        Local $t = $aList[$i][0]
        If $t = "" Then ContinueLoop
        If BitAND(WinGetState($aList[$i][1]), 2) = 0 Then ContinueLoop ; Skip hidden windows (script's own hidden AutoIt window title contains "thinkorswim")
        If _IsUpdateWindow($t) Then ContinueLoop ; Skip updater windows
        ; Window must belong to thinkorswim.exe process (exclude file folders / browser tabs with same name)
        If _WinProcName(WinGetProcess($aList[$i][1])) <> "thinkorswim.exe" Then ContinueLoop
        Return True
    Next
    Return False
EndFunc   ;==>_IsMainRunning

; ---------- Get updater window handle (0 if none) ----------
Func _GetUpdateWindow()
    Local $aList = WinList("[REGEXPTITLE:(?i)" & $sMainKey & "]")
    For $i = 1 To $aList[0][0]
        If BitAND(WinGetState($aList[$i][1]), 2) = 0 Then ContinueLoop ; Skip hidden windows
        If _IsUpdateWindow($aList[$i][0]) Then Return $aList[$i][1]
    Next
    Return 0
EndFunc   ;==>_GetUpdateWindow

; ---------- Calculate progress window position (never overlaps thinkorswim windows) ----------
; Priority: below updater window > below login window; if no room below, place above;
; fallback: bottom-center of screen (above taskbar), guaranteeing no overlap
Func _ProgPos($W, $H)
    Local $aRet[2] = [Int((@DesktopWidth - $W) / 2), 0]

    ; Working area bottom (taskbar top if taskbar is at bottom)
    Local $nBottom = @DesktopHeight
    Local $aTB = WinGetPos("[CLASS:Shell_TrayWnd]")
    If IsArray($aTB) And $aTB[1] > 0 Then $nBottom = $aTB[1]

    ; Default: bottom-center of screen
    $aRet[1] = $nBottom - $H - 4

    ; If target window exists (updater/login): place below it, or above if no room
    Local $hTarget = _GetUpdateWindow()
    If $hTarget = 0 And WinExists($sLogin) Then $hTarget = WinGetHandle($sLogin)
    If $hTarget <> 0 Then
        Local $aT = WinGetPos($hTarget)
        If IsArray($aT) Then
            Local $xD   = $aT[0] + Int(($aT[2] - $W) / 2) ; Horizontally centered with target
            Local $yDn  = $aT[1] + $aT[3] + 6             ; Below target
            Local $yUp  = $aT[1] - $H - 6                 ; Above target
            If $yDn + $H <= $nBottom Then
                $aRet[0] = $xD
                $aRet[1] = $yDn
            ElseIf $yUp >= 0 Then
                $aRet[0] = $xD
                $aRet[1] = $yUp
            EndIf
        EndIf
    EndIf

    ; Clamp X to screen
    If $aRet[0] < 0 Then $aRet[0] = 0
    If $aRet[0] + $W > @DesktopWidth Then $aRet[0] = @DesktopWidth - $W
    Return $aRet
EndFunc   ;==>_ProgPos

; ---------- Wait for update to finish if one is running ----------
; Returns True = OK to continue (no update or update done); False = timeout
Func _WaitForUpdate()
    Local $hUpd = _GetUpdateWindow()
    If $hUpd = 0 Then Return True ; No update in progress, continue

    TrayTip("thinkorswim Auto-Login", "thinkorswim is updating, waiting for completion..." & @CRLF & _
            "Max wait " & Int($T_UPDATE / 60) & " minutes", 10, 1)

    Local $t = TimerInit()
    While TimerDiff($t) < $T_UPDATE * 1000
        ; Updater window disappeared -> update done
        If Not WinExists($hUpd) Then
            TrayTip("thinkorswim Auto-Login", "Update complete, continuing to login...", 5, 1)
            Sleep(5000) ; Give the main program a moment to start
            Return True
        EndIf
        ; If login window appears during update, continue immediately
        If WinExists($sLogin) Then Return True
        Sleep(3000)
    WEnd

    MsgBox(48, "thinkorswim Auto-Login", "Update wait timed out (" & Int($T_UPDATE / 60) & " min), please check update status manually.")
    Return False
EndFunc   ;==>_WaitForUpdate

; ---------- Detect whether the login page (embedded Chromium) has rendered ----------
; Principle: on a blank/unrendered page the three sampled points (above/at/below the
; input field) have identical color; once the field/text is rendered they differ -> ready.
; Waits at most $iTimeoutMs; on timeout returns False anyway (safe fallback, no deadlock).
Func _PageReady($x, $y, $iTimeoutMs)
    Local $t = TimerInit()
    While TimerDiff($t) < $iTimeoutMs
        If Not WinExists($sLogin) Then Return True ; Window gone = flow already finished
        Local $c1 = PixelGetColor($x, $y)
        Local $c2 = PixelGetColor($x, $y - 80)
        Local $c3 = PixelGetColor($x, $y + 80)
        If $c1 <> $c2 Or $c1 <> $c3 Or $c2 <> $c3 Then Return True
        Sleep(200)
    WEnd
    Return False
EndFunc   ;==>_PageReady

; ---------- Login window already exists -> activate and use directly ----------
If WinExists($sLogin) Then
    WinActivate($sLogin)
    TrayTip("thinkorswim Auto-Login", "Detected an open login window, filling credentials directly...", 5, 1)

; ---------- Main window already running (excluding updater) -> activate and notify ----------
ElseIf _IsMainRunning() Then
    Local $aList = WinList("[REGEXPTITLE:(?i)" & $sMainKey & "]")
    For $i = 1 To $aList[0][0]
        If $aList[$i][0] = "" Then ContinueLoop
        If BitAND(WinGetState($aList[$i][1]), 2) = 0 Then ContinueLoop ; Skip hidden windows
        If _IsUpdateWindow($aList[$i][0]) Then ContinueLoop
        If _WinProcName(WinGetProcess($aList[$i][1])) <> "thinkorswim.exe" Then ContinueLoop ; Only activate real thinkorswim window
        WinActivate($aList[$i][1])
        ExitLoop
    Next
    TrayTip("thinkorswim Auto-Login", "thinkorswim is already running, no need to login again.", 5, 1)
    Exit

; ---------- Otherwise: launch thinkorswim ----------
Else
    ; If updater is already running, wait for it to finish first
    If Not _WaitForUpdate() Then Exit

    ; ---- Show a non-focus-stealing progress window so user knows script is running ----
    ; Position decided by _ProgPos(): bottom of screen, then follows updater/login window above/below
    Local $aP0 = _ProgPos(380, 90)
    Local $hProg = GUICreate("thinkorswim Auto-Login", 380, 90, $aP0[0], $aP0[1], -1, _
                            BitOR($WS_EX_NOACTIVATE, $WS_EX_TOPMOST))
    Local $idLbl = GUICtrlCreateLabel("Launching thinkorswim..." & @CRLF & "Elapsed: 0 sec", 12, 14, 356, 60)
    GUISetState(@SW_SHOWNOACTIVATE, $hProg)

    ; Launch
    ; [Critical] Don't use AutoIt's Run to directly CreateProcess — thinkorswim
    ; would be identified as a script child process, security software may block
    ; update downloads, causing the updater window to hang and login UI to never appear.
    ; Using explorer.exe launches via Windows Shell (same context as manual double-click),
    ; updates complete in 20~35 seconds and login UI appears.
    Local $pidTOS = Run('explorer.exe "' & $TOS_EXE & '"')
    If $pidTOS = 0 Then
        GUIDelete($hProg)
        MsgBox(16, "thinkorswim Auto-Login", "Failed to launch thinkorswim! (explorer returned 0, @error=" & @error & ")" & @CRLF & $TOS_EXE)
        Exit
    EndIf
    TrayTip("thinkorswim Auto-Login", "thinkorswim launched" & @CRLF & _
            "Waiting for login window, first launch is slow...", 10, 1)

    ; Poll for login window (thinkorswim usually runs updater first)
    Local $t = TimerInit()
    Local $bTipUpdate = False
    Local $bFound = False

    While TimerDiff($t) < $T_BOOT * 1000
        If WinExists($sLogin) Then
            $bFound = True
            ExitLoop
        EndIf

        ; Update progress window text (show user the script is alive)
        Local $nEl = Int(TimerDiff($t) / 1000)
        Local $sExtra = ""
        If _GetUpdateWindow() Then
            $sExtra = "(Updater detected, waiting...)"
            If Not $bTipUpdate Then
                TrayTip("thinkorswim Auto-Login", "thinkorswim updater is running" & @CRLF & _
                        "Login UI will appear after update completes, please wait...", 10, 1)
                $bTipUpdate = True
            EndIf
        Else
            $sExtra = "(First launch is slow, please wait)"
        EndIf
        GUICtrlSetData($idLbl, "Launching thinkorswim..." & @CRLF & "Elapsed: " & $nEl & " sec" & @CRLF & $sExtra)

        ; Follow target window position (only move if changed, avoid flicker)
        Local $aP = _ProgPos(380, 90)
        Local $aNow = WinGetPos($hProg)
        If Not IsArray($aNow) Or $aNow[0] <> $aP[0] Or $aNow[1] <> $aP[1] Then
            WinMove($hProg, "", $aP[0], $aP[1])
        EndIf

        Sleep(2000)
    WEnd

    ; Login window appeared -> close progress window + force topmost flash (ensure visibility)
    GUIDelete($hProg)

    If Not $bFound Then
        MsgBox(48, "thinkorswim Auto-Login", "Login window not detected within " & $T_BOOT & " seconds." & @CRLF & @CRLF & _
                "Common causes: thinkorswim is updating in background (takes time);" & @CRLF & _
                "or main program didn't launch after update." & @CRLF & @CRLF & _
                "Suggestion: open thinkorswim manually to finish update/start, then run this script after login UI appears.")
        Exit
    EndIf

    ; Force login window to top and flash
    WinSetOnTop($sLogin, "", 1)
    WinActivate($sLogin)
    WinFlash($sLogin, "", 4, 250)
    WinSetOnTop($sLogin, "", 0)
EndIf

; ---------- Activate and wait for login window to be ready ----------
WinActivate($sLogin)
WinWaitActive($sLogin, "", 10)

; Switch to English keyboard layout (prevent Chinese IME interference)
Local $hWnd = WinGetHandle($sLogin)
Local $ret = DllCall("user32.dll", "long", "LoadKeyboardLayout", "str", "04090409", "int", 1 + 0)
DllCall("user32.dll", "ptr", "SendMessage", "hwnd", $hWnd, "int", 0x50, "int", 1, "int", $ret[0])

; ---------- Wait for embedded Chromium page to load (smart detection, no fixed 5s wait) ----------
; Continue as soon as the page is rendered, typically 1~2 s; max 4 s fallback
Local $posR = WinGetPos($sLogin)
If IsArray($posR) Then
    Local $rdyX = $posR[0] + Int($posR[2] * 0.50)
    Local $rdyY = $posR[1] + Int($posR[3] * 0.28)
    MouseMove(Int(@DesktopWidth / 2), Int(@DesktopHeight / 2), 0) ; Move mouse away so the pointer doesn't cover the sample points
    _PageReady($rdyX, $rdyY, 4000)
Else
    Sleep(2000)
EndIf

; ---------- Two-step login, at most $MAX_TRY attempts ----------
; If every attempt fails, stop trying: repeated failures usually mean the server is
; under maintenance (or the credentials are wrong), so hammering it again is pointless.
Local $bOK = False

For $iTry = 1 To $MAX_TRY
    ; Login window already gone -> treat as success (auto-login / window closed)
    If Not WinExists($sLogin) Then
        $bOK = True
        ExitLoop
    EndIf

    WinActivate($sLogin)
    WinWaitActive($sLogin, "", 10)

    ; ---------- Step 1: Click Login ID field, paste username ----------
    ; [2026-09-06] Login window changed to "Welcome" vertical layout (377x682), Login ID field at ~28% height
    ; (old 45% coordinate landed on empty space, paste was ineffective)
    ; [2026-09-07] Added IsArray guard: WinGetPos may return 0 (window gone), subscript access crashes
    Local $pos = WinGetPos($sLogin)
    If Not IsArray($pos) Then
        If $iTry < $MAX_TRY Then ContinueLoop
        ExitLoop
    EndIf
    Local $inputX = $pos[0] + Int($pos[2] * 0.50)
    Local $inputY = $pos[1] + Int($pos[3] * 0.28)

    MouseClick("left", $inputX, $inputY, 1, 0)
    Sleep(1000)
    ClipPut($user)
    Send("^a^v") ; Select all + paste (overwrite any residual content)
    Sleep(500)
    Send("{ENTER}")

    ; Wait for second page (password input) to load
    Sleep(4000)

    ; ---------- Step 2: Click password field, paste password ----------
    ; [2026-09-06] Password field also at ~28% height (confirmed via screenshot)
    If Not WinExists($sLogin) Then
        $bOK = True ; Window closed = login succeeded
        ExitLoop
    EndIf
    Local $pos2 = WinGetPos($sLogin)
    If Not IsArray($pos2) Then
        If $iTry < $MAX_TRY Then ContinueLoop
        ExitLoop
    EndIf
    Local $pwX = $pos2[0] + Int($pos2[2] * 0.50)
    Local $pwY = $pos2[1] + Int($pos2[3] * 0.28)

    MouseClick("left", $pwX, $pwY, 1, 0)
    Sleep(1000)
    ClipPut($pw)
    Send("^a^v")
    Sleep(500)
    Send("{ENTER}")

    ; Clear clipboard (no password residue)
    ClipPut("")

    ; ---------- Wait for login window to close (confirm login success) ----------
    If WinWaitClose($sLogin, "", $T_LOGIN) Then
        $bOK = True
        ExitLoop
    EndIf

    ; ---------- This attempt failed ----------
    ; Return to the Login ID page and try once more (only if attempts remain)
    If $iTry < $MAX_TRY Then
        TrayTip("thinkorswim Auto-Login", "Login attempt " & $iTry & " failed, retrying (" & ($iTry + 1) & "/" & $MAX_TRY & ")...", 10, 1)
        WinActivate($sLogin)
        Sleep(1500)
        Send("{ESC}") ; Go back to the Login ID page
        Sleep(3000)
    EndIf
Next

; ---------- Result ----------
If $bOK Then
    TrayTip("thinkorswim Auto-Login", "Login successful, account: " & $user, 5, 1)
Else
    ; Give up: do not keep retrying, the server may be under maintenance
    MsgBox(48, "thinkorswim Auto-Login", _
            "Login failed after " & $MAX_TRY & " attempts, stopped retrying." & @CRLF & @CRLF & _
            "The thinkorswim server may be under maintenance, or the credentials are incorrect." & @CRLF & _
            "Please check the site status and run again later.")
EndIf
