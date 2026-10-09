; A stand-in window whose controls publish an accessibility tree: a button, two labelled edits, and a check
; box whose name contains quotes. Not run through the launcher. Each click on the button writes the running
; count to ACU_TEST_COUNT_FILE; each change to an edit writes "<label>=<text>" to ACU_TEST_EDIT_FILE.
#NoTrayIcon
#SingleInstance Off
DllCall("SetThreadDpiAwarenessContext", "ptr", -4, "ptr")
title := EnvGet("ACU_TEST_TITLE")
countFile := EnvGet("ACU_TEST_COUNT_FILE")
editFile := EnvGet("ACU_TEST_EDIT_FILE")
state := {hits: 0}
win := Gui("", title)
button := win.AddButton("w120 h40", "hit")
button.OnEvent("Click", (*) => (state.hits++, FileOpen(countFile, "w").Write(state.hits)))
for pair in [["City", "Boston"], ["Street", "Main St"]] {
    win.AddText("xm", pair[1])  ; a Win32 edit takes its accessible name from the label before it
    field := win.AddEdit("w240", pair[2])
    field.OnEvent("Change", ((label, ctrl, *) => FileOpen(editFile, "w").Write(label "=" ctrl.Value)).Bind(pair[1]))
}
win.AddCheckbox("xm", 'agree "fully"')
win.OnEvent("Close", (*) => ExitApp())
win.Show("x" EnvGet("ACU_TEST_X") " y" EnvGet("ACU_TEST_Y"))
WinActivate win.Hwnd
