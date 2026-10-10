; List window identities before an agent chooses a target; no activation or input.
for hwnd in WinGetList() {
    target := "ahk_id " hwnd
    FileAppend hwnd " | " WinGetTitle(target) " | " WinGetClass(target) " | " WinGetProcessName(target) "`n", "*"
}
