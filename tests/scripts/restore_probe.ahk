; Exercises the prelude's end-of-script restore. The first argument selects the scenario, the second is the
; handle of another process's window:
;   click_own       click a button in the script's own window, then exit
;   move_cursor     same, then move the cursor with SetCursorPos the way a user would, then exit
;   activate_other  same, then activate the other window as if an unrelated window had appeared
;   click_other     same, then click the center of the other window
;   keep_other      click_other, then call AcuKeepForeground() so the other window stays in front at exit
mode := A_Args[1]
other := Integer(A_Args[2])

state := {hits: 0}
win := Gui("+AlwaysOnTop", "ACU restore probe")
button := win.AddButton("w64 h64", "hit")
button.OnEvent("Click", (*) => state.hits++)
win.Show("x600 y600")
if !WinWaitActive(win.Hwnd, , 2)
    throw Error("probe window never became active")

WinGetClientPos &clientX, &clientY, , , win.Hwnd
button.GetPos(&bx, &by, &bw, &bh)
Click clientX + bx + bw // 2, clientY + by + bh // 2
Sleep 100
FileAppend "hits=" state.hits "`n", "*"

if (mode = "move_cursor") {
    DllCall("SetCursorPos", "int", clientX + 300, "int", clientY + 300)
    MouseGetPos &movedX, &movedY
    FileAppend "moved=" movedX "," movedY "`n", "*"
} else if (mode = "activate_other") {
    WinActivate other
    if !WinWaitActive(other, , 2)
        throw Error("other window never became active")
} else if (mode = "click_other" || mode = "keep_other") {
    WinGetPos &ox, &oy, &ow, &oh, other
    Click ox + ow // 2, oy + oh // 2
    if !WinWaitActive(other, , 2)
        throw Error("other window never became active after the click")
    if (mode = "keep_other")
        AcuKeepForeground()
}
ExitApp
