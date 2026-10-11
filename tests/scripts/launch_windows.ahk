; A launched app with a main window and a splash window; the transient mode closes only the splash.
#Requires AutoHotkey v2.0
#NoTrayIcon
#Include "%A_LineFile%\..\english_keyboard.ahk"
#SingleInstance Off
prefix := A_Args[1]
mode := A_Args[2]
FileAppend DllCall("GetCurrentProcessId"), A_Args[3], "UTF-8-RAW"
main := Gui(, prefix " main")
main.AddText("w200 h60", "main")
main.OnEvent("Close", (*) => ExitApp())
main.Show("x100 y100")
splash := Gui(, prefix " splash")
splash.AddText("w200 h60", "splash")
splash.OnEvent("Close", (*) => ExitApp())
splash.Show("x400 y100")
if mode = "transient" || mode = "slow-transient"
    SetTimer (() => splash.Destroy()), mode = "transient" ? -350 : -1200
