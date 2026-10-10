; The accessibility-tree dump for every ACU script, included by the prelude. AcuTree returns the listing as text;
; tree.ahk is the command-line wrapper around it.
#Requires AutoHotkey v2.0

; Lists a window's control-view tree, depth first, one line per element, exactly as tree.ahk prints it:
;   2,2,2,5,3 Button "Six" id="num6Button" @2073,1917 157x71 invoke
; Path, type, name when present, id= when present, value= when present and in full, screen bounds, then the
; actions the element supports (invoke toggle value select expand scroll; value means writable) and its state
; (disabled offscreen focused selected). Quoted fields are AutoHotkey string contents, so they paste into a script
; between quotes as they are. Paths number the control view, which is the view ElementFromPath walks.
; target is any WinTitle or "ahk_id <hwnd>". options: find (name or id contains the text), type (one control type
; such as Button), depth (default 25), max (element budget, default 300). The text starts with
; window=<hwnd> "<title>" <exe> and ends with elements=N and truncated=no|max|depth|max+depth, naming the limit that
; cut it. The whole subtree is fetched in one round trip before filtering, so the budget bounds the output, not the fetch.
AcuTree(target, options := "") {
    option(name, default) {
        return IsObject(options) && options.HasProp(name) && options.%name% != "" ? options.%name% : default
    }
    findText := option("find", ""), wantedType := option("type", "")
    maxDepth := Integer(option("depth", 25)), maxCount := Integer(option("max", 300))
    if (maxDepth < 1 || maxCount < 1)
        throw ValueError("depth and max must be at least 1")
    if (wantedType != "" && !UIA.Type.HasOwnProp(wantedType))
        throw ValueError("type must be a UI Automation control type such as Button, Edit, or Text; got `"" wantedType "`"")
    cachedProperties := ["Type", "Name", "AutomationId", "Value", "ValueIsReadOnly", "BoundingRectangle", "IsEnabled", "IsOffscreen"
        , "HasKeyboardFocus", "SelectionItemIsSelected", "IsInvokePatternAvailable", "IsTogglePatternAvailable"
        , "IsValuePatternAvailable", "IsSelectionItemPatternAvailable", "IsExpandCollapsePatternAvailable", "IsScrollPatternAvailable"]
    actionFlags := [["invoke", "IsInvokePatternAvailable"], ["toggle", "IsTogglePatternAvailable"]
        , ["select", "IsSelectionItemPatternAvailable"], ["expand", "IsExpandCollapsePatternAvailable"], ["scroll", "IsScrollPatternAvailable"]]
    hwnd := WinGetID(target)
    ; One cross-process round trip fetches the whole control-view subtree with the properties above; the walk then reads memory.
    cacheRequest := UIA.CreateCacheRequest(cachedProperties, , UIA.TreeScope.ElementDescendants, UIA.AutomationElementMode.None, UIA.ControlViewCondition)
    root := AcuTreeFetch(hwnd, cacheRequest)
    state := {count: 0, hitMax: false, hitDepth: false, lines: ""}

    ; Whether an element passes the find and type filters. Both are case-insensitive.
    wanted(element) {
        if (wantedType != "" && UIA.Type[element.CachedType] != wantedType)
            return false
        if (findText != "" && !InStr(element.CachedName, findText) && !InStr(element.CachedAutomationId, findText))
            return false
        return true
    }

    ; One dump line for an element, from its cached properties only.
    describe(element, path) {
        line := path " " UIA.Type[element.CachedType]
        if (element.CachedName != "")
            line .= " `"" AcuTreeLiteral(element.CachedName) "`""
        if (element.CachedAutomationId != "")
            line .= " id=`"" AcuTreeLiteral(element.CachedAutomationId) "`""
        if (element.CachedValue != "")
            line .= " value=`"" AcuTreeLiteral(element.CachedValue) "`""
        try
            location := element.CachedLocation
        catch
            location := {x: 0, y: 0, w: 0, h: 0}
        line .= " @" location.x "," location.y " " location.w "x" location.h
        for pair in actionFlags
            if element.GetCachedPropertyValue(UIA.Property.%pair[2]%)
                line .= " " pair[1]
        if (element.GetCachedPropertyValue(UIA.Property.IsValuePatternAvailable) && !element.GetCachedPropertyValue(UIA.Property.ValueIsReadOnly))
            line .= " value"
        if !element.CachedIsEnabled
            line .= " disabled"
        if element.CachedIsOffscreen
            line .= " offscreen"
        if element.CachedHasKeyboardFocus
            line .= " focused"
        if element.GetCachedPropertyValue(UIA.Property.SelectionItemIsSelected)
            line .= " selected"
        return line
    }

    ; Appends one line per matching element below `element`, depth first. Stops at the element budget and the
    ; depth budget, and records which one cut the dump.
    walk(element, path, level) {
        for index, child in element.CachedChildren {
            if state.hitMax
                return
            childPath := path (path != "" ? "," : "") index
            if wanted(child) {
                if (state.count >= maxCount) {
                    state.hitMax := true
                    return
                }
                state.lines .= describe(child, childPath) "`n"
                state.count++
            }
            if (level < maxDepth)
                walk(child, childPath, level + 1)
            else if (child.CachedChildren.Length > 0)
                state.hitDepth := true
        }
    }

    walk(root, "", 1)
    truncated := state.hitMax && state.hitDepth ? "max+depth" : state.hitMax ? "max" : state.hitDepth ? "depth" : "no"
    return "window=" hwnd " `"" AcuTreeLiteral(WinGetTitle(hwnd)) "`" " WinGetProcessName(hwnd) "`n" state.lines "elements=" state.count "`ntruncated=" truncated "`n"
}

; Fetches the cached subtree, waiting while the window's accessibility provider is still waking up. A Chromium or
; Electron window exists before its provider answers, and the first full-subtree request then fails with UIA_E_TIMEOUT
; (0x80131505); seen on the ChatGPT app four seconds after launch. A plain root query first nudges such a provider
; into life, then the cached fetch is retried until waitMs runs out. Other errors are rethrown unchanged.
AcuTreeFetch(hwnd, cacheRequest, waitMs := 5000) {
    deadline := A_TickCount + waitMs
    loop {
        try {
            UIA.ElementFromHandle(hwnd)
            return UIA.ElementFromHandle(hwnd, cacheRequest)
        } catch Error as failure {
            if !InStr(failure.Message, "0x80131505")
                throw failure
            if (A_TickCount >= deadline)
                throw Error("the window's accessibility tree did not answer within " waitMs " ms (UIA_E_TIMEOUT); the application may still be starting, look again", -1)
            Sleep 250
        }
    }
}

; Text as the contents of an AutoHotkey double-quoted string: backticks, quotes, and line breaks escaped,
; so what the dump shows is what a script writes.
AcuTreeLiteral(text) {
    return StrReplace(StrReplace(StrReplace(StrReplace(text, "``", "````"), '"', '``"'), "`r", "``r"), "`n", "``n")
}
