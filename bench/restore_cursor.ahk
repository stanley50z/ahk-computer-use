; Restore the active Windows cursor scheme after the benchmark, without changing saved pointer settings.
info := Buffer(A_PtrSize = 8 ? 24 : 20, 0)
NumPut "UInt", info.Size, info, 0
if !DllCall("GetCursorInfo", "Ptr", info)
    throw OSError()
FileAppend "before_flags=" NumGet(info, 4, "UInt") " before_cursor=" NumGet(info, 8, "Ptr") "`n", "*"
if !DllCall("SystemParametersInfoW", "UInt", 0x57, "UInt", 0, "Ptr", 0, "UInt", 0)
    throw OSError()
arrow := DllCall("LoadCursorW", "Ptr", 0, "Ptr", 32512, "Ptr")
DllCall "SetCursor", "Ptr", arrow, "Ptr"
DllCall "GetCursorInfo", "Ptr", info
if !(NumGet(info, 4, "UInt") & 1)
    throw Error("Windows still reports a hidden cursor after restoring its saved scheme")
FileAppend "reloaded_saved_cursor_scheme=1 after_flags=" NumGet(info, 4, "UInt") " after_cursor=" NumGet(info, 8, "Ptr") "`n", "*"
