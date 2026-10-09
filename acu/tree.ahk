; ACU tree script: the agent's way to find controls by name. Run it through the launcher:
;   python run.py tree.ahk -- "<WinTitle>" [--depth N] [--max N]
; Prints window=<hwnd> "<title>" <exe>, then one line per control of the window's accessibility tree,
; depth first:
;   2,2,2,5,3 Button "Six" id="num6Button" @2073,1917 157x71 invoke
; Path, type, name when present, id= when present, value= when present, screen bounds, then the actions
; the control supports (invoke toggle value select expand scroll) and its state (disabled offscreen focused).
; Quoted fields are AutoHotkey string contents, so they paste into a script between quotes as they are.
; Paths number the control view, which is the view ElementFromPath walks (verified on Calculator: raw-view
; numbering does not resolve). Ends with elements=N and truncated=yes|no; a depth cut that hides children
; counts as truncation. Defaults: depth 25, 300 elements.
#Requires AutoHotkey v2.0

DEFAULT_DEPTH := 25
DEFAULT_MAX := 300
CACHED_PROPERTIES := ["Type", "Name", "AutomationId", "Value", "BoundingRectangle", "IsEnabled", "IsOffscreen"
    , "HasKeyboardFocus", "IsInvokePatternAvailable", "IsTogglePatternAvailable", "IsValuePatternAvailable"
    , "IsSelectionItemPatternAvailable", "IsExpandCollapsePatternAvailable", "IsScrollPatternAvailable"]
ACTION_FLAGS := [["invoke", "IsInvokePatternAvailable"], ["toggle", "IsTogglePatternAvailable"], ["value", "IsValuePatternAvailable"]
    , ["select", "IsSelectionItemPatternAvailable"], ["expand", "IsExpandCollapsePatternAvailable"], ["scroll", "IsScrollPatternAvailable"]]

request := ParseArgs(A_Args)
hwnd := WinGetID(request.target)
; One cross-process round trip fetches the whole control-view subtree with the properties above; the walk then reads memory.
cacheRequest := UIA.CreateCacheRequest(CACHED_PROPERTIES, , UIA.TreeScope.ElementDescendants, UIA.AutomationElementMode.None, UIA.ControlViewCondition)
root := UIA.ElementFromHandle(hwnd, cacheRequest)
state := {count: 0, truncated: false, lines: ""}
Walk(root, "", 1)
FileAppend "window=" hwnd " `"" Literal(WinGetTitle(hwnd)) "`" " WinGetProcessName(hwnd) "`n", "*"
FileAppend state.lines "elements=" state.count "`ntruncated=" (state.truncated ? "yes" : "no") "`n", "*"

; Splits the command line into the WinTitle and the two options, and rejects budgets that would print nothing.
ParseArgs(args) {
    request := {target: "", depth: DEFAULT_DEPTH, max: DEFAULT_MAX}
    i := 1
    while (i <= args.Length) {
        arg := args[i]
        if (arg = "--depth" || arg = "--max") {
            if (i = args.Length)
                throw ValueError(arg " needs a value")
            i++
            if !IsInteger(args[i]) || Integer(args[i]) < 1
                throw ValueError(arg " must be at least 1")
            request.%SubStr(arg, 3)% := Integer(args[i])
        } else if (request.target = "")
            request.target := arg
        else
            throw ValueError("Unexpected argument `"" arg "`"; usage: tree.ahk `"<WinTitle>`" [--depth N] [--max N]")
        i++
    }
    if (request.target = "")
        throw ValueError("Usage: tree.ahk `"<WinTitle>`" [--depth N] [--max N]")
    return request
}

; Appends one line per control below `element`, depth first. Stops at the element and depth budgets and
; records that something was left out.
Walk(element, path, level) {
    for index, child in element.CachedChildren {
        if (state.count >= request.max) {
            state.truncated := true
            return
        }
        childPath := path (path != "" ? "," : "") index
        state.lines .= Describe(child, childPath) "`n"
        state.count++
        if (level < request.depth)
            Walk(child, childPath, level + 1)
        else if (child.CachedChildren.Length > 0)
            state.truncated := true
    }
}

; One dump line for an element, from its cached properties only.
Describe(element, path) {
    line := path " " UIA.Type[element.CachedType]
    if (element.CachedName != "")
        line .= " `"" Literal(element.CachedName) "`""
    if (element.CachedAutomationId != "")
        line .= " id=`"" Literal(element.CachedAutomationId) "`""
    if (element.CachedValue != "")
        line .= " value=`"" Literal(element.CachedValue) "`""
    try
        location := element.CachedLocation
    catch
        location := {x: 0, y: 0, w: 0, h: 0}
    line .= " @" location.x "," location.y " " location.w "x" location.h
    for pair in ACTION_FLAGS
        if element.GetCachedPropertyValue(UIA.Property.%pair[2]%)
            line .= " " pair[1]
    if !element.CachedIsEnabled
        line .= " disabled"
    if element.CachedIsOffscreen
        line .= " offscreen"
    if element.CachedHasKeyboardFocus
        line .= " focused"
    return line
}

; Text as the contents of an AutoHotkey double-quoted string: backticks, quotes, and line breaks escaped,
; so what the dump shows is what a script writes.
Literal(text) {
    return StrReplace(StrReplace(StrReplace(StrReplace(text, "``", "````"), '"', '``"'), "`r", "``r"), "`n", "``n")
}
