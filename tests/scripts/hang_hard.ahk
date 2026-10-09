; Blocks inside a Win32 Sleep, so the thread cannot process a close request and the launcher must kill it.
; AutoHotkey's own Sleep and even a tight Loop still check the message queue; this does not.
; Bounded at 20 s so a launcher without a watchdog cannot leave it blocked forever.
DllCall("Sleep", "UInt", 20000)
FileAppend "hang_hard: finished sleeping`n", "*"
