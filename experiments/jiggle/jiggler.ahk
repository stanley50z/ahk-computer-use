; Jiggle test disturbance: moves the cursor to a random point on the primary monitor about once a millisecond,
; through the same injected-input path a competing script or a busy hand would use. Runs for ACU_JIGGLE_SECONDS
; or until asked to close, and writes the number of moves it made to ACU_JIGGLE_MOVES_FILE on exit.
#NoTrayIcon
#SingleInstance Off
DllCall("SetThreadDpiAwarenessContext", "ptr", -4, "ptr")
CoordMode "Mouse", "Screen"
SendMode "Event"
SetMouseDelay -1
SetDefaultMouseSpeed 0
movesFile := EnvGet("ACU_JIGGLE_MOVES_FILE")
state := {moves: 0}
OnExit (*) => (FileOpen(movesFile, "w").Write(state.moves), 0)
MonitorGet 1, &left, &top, &right, &bottom
deadline := A_TickCount + Integer(EnvGet("ACU_JIGGLE_SECONDS") || 120) * 1000

; Sleep 1 rounds up to the 15.6 ms system tick, and Windows 11 ignores timer-resolution requests from a
; windowless background process, so pace the loop with a high-resolution waitable timer instead.
timer := DllCall("CreateWaitableTimerExW", "ptr", 0, "ptr", 0, "uint", 2, "uint", 0x1F0003, "ptr")
if !timer
    throw Error("high-resolution waitable timer unavailable")
oneMillisecond := Buffer(8)
NumPut("int64", -10000, oneMillisecond)  ; relative, in 100 ns units

Loop {
    MouseMove Random(left, right - 1), Random(top, bottom - 1)
    state.moves++
    DllCall("SetWaitableTimer", "ptr", timer, "ptr", oneMillisecond, "int", 0, "ptr", 0, "ptr", 0, "int", 0)
    DllCall("WaitForSingleObject", "ptr", timer, "uint", 100)
    Sleep -1  ; pump messages without sleeping, so a close request still reaches the exit handler
    if (A_TickCount > deadline)
        break
}
