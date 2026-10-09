; Creates its own window with one button, clicks the button's center by screen coordinate, and reports
; how many times the button's handler fired plus where the cursor ended up.
; The first script argument picks the monitor the window appears on (default 1).
monitor := A_Args.Length ? Integer(A_Args[1]) : 1
MonitorGet monitor, &left, &top

state := {hits: 0}
win := Gui("+AlwaysOnTop", "ACU click probe")
button := win.AddButton("w64 h64", "hit")
button.OnEvent("Click", (*) => state.hits++)
win.Show("x" left + 200 " y" top + 200)
if !WinWaitActive(win.Hwnd, , 2)
    throw Error("probe window never became active")

WinGetClientPos &clientX, &clientY, , , win.Hwnd
button.GetPos(&bx, &by, &bw, &bh)
targetX := clientX + bx + bw // 2
targetY := clientY + by + bh // 2
Click targetX, targetY
MouseGetPos &cursorX, &cursorY  ; read at once, before a human at the mouse can move it
Sleep 100  ; let the button's click message reach the handler

FileAppend "hits=" state.hits "`n", "*"
FileAppend "target=" targetX "," targetY "`n", "*"
FileAppend "cursor=" cursorX "," cursorY "`n", "*"
ExitApp
