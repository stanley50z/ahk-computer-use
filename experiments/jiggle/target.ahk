; Jiggle test target: a window with a 24x24 physical-pixel button that counts clicks.
; Writes the running total to ACU_JIGGLE_COUNT_FILE on every hit. Stays alive until killed.
#NoTrayIcon
#SingleInstance Off
DllCall("SetThreadDpiAwarenessContext", "ptr", -4, "ptr")
countFile := EnvGet("ACU_JIGGLE_COUNT_FILE")
state := {hits: 0}
win := Gui("+AlwaysOnTop -DPIScale", "ACU jiggle target")
button := win.AddButton("w24 h24", "")
button.OnEvent("Click", (*) => (state.hits++, FileOpen(countFile, "w").Write(state.hits)))
win.Show("x600 y600")
