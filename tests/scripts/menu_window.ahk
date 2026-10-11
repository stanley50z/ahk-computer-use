; A native popup menu in a separate top-level window, used to distinguish on-screen and app rendering.
#Requires AutoHotkey v2.0
#NoTrayIcon
#Include "%A_LineFile%\..\english_keyboard.ahk"
#SingleInstance Off
win := Gui(, EnvGet("ACU_TEST_TITLE"))
win.BackColor := "006600"
win.AddText("w500 h300", "Right click to show the menu")
popupMenu := Menu()
popupMenu.Add("ACU popup item", (*) => 0)
win.OnEvent("ContextMenu", (*) => popupMenu.Show())
win.OnEvent("Close", (*) => ExitApp())
win.Show("x100 y100")
