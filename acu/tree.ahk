; ACU tree script: the agent's way to find controls by name. Run it through the launcher:
;   python run.py tree.ahk -- "<WinTitle>" [--find <text>] [--type <Type>] [--depth N] [--max N]
; Prints window=<hwnd> "<title>" <exe>, then one line per element of the window's accessibility tree,
; depth first:
;   2,2,2,5,3 Button "Six" id="num6Button" @2073,1917 157x71 invoke
; Path, type, name when present, id= when present, value= when present and in full, screen bounds, then
; the actions the element supports (invoke toggle value select expand scroll; value means writable) and its
; state (disabled offscreen focused selected). Quoted fields are AutoHotkey string contents, so they paste
; into a script between quotes as they are. Paths number the control view, which is the view
; ElementFromPath walks (verified on Calculator: raw-view numbering does not resolve).
; --find keeps elements whose name or id contains the text; --type keeps one control type. The element
; budget counts printed lines. Ends with elements=N and truncated=no|max|depth|max+depth, naming the limit
; that cut the dump. Defaults: depth 25, 300 elements.
#Requires AutoHotkey v2.0

DEFAULT_DEPTH := 25
DEFAULT_MAX := 300
CACHED_PROPERTIES := ["Type", "Name", "AutomationId", "Value", "ValueIsReadOnly", "BoundingRectangle", "IsEnabled", "IsOffscreen"
    , "HasKeyboardFocus", "SelectionItemIsSelected", "IsInvokePatternAvailable", "IsTogglePatternAvailable"
    , "IsValuePatternAvailable", "IsSelectionItemPatternAvailable", "IsExpandCollapsePatternAvailable", "IsScrollPatternAvailable"]
ACTION_FLAGS := [["invoke", "IsInvokePatternAvailable"], ["toggle", "IsTogglePatternAvailable"]
    , ["select", "IsSelectionItemPatternAvailable"], ["expand", "IsExpandCollapsePatternAvailable"], ["scroll", "IsScrollPatternAvailable"]]

request := ParseArgs(A_Args)
hwnd := WinGetID(request.target)
; One cross-process round trip fetches the whole control-view subtree with the properties above; the walk then reads memory.
cacheRequest := UIA.CreateCacheRequest(CACHED_PROPERTIES, , UIA.TreeScope.ElementDescendants, UIA.AutomationElementMode.None, UIA.ControlViewCondition)
root := UIA.ElementFromHandle(hwnd, cacheRequest)
state := {count: 0, hitMax: false, hitDepth: false, lines: ""}
Walk(root, "", 1)
FileAppend "window=" hwnd " `"" Literal(WinGetTitle(hwnd)) "`" " WinGetProcessName(hwnd) "`n", "*"
truncated := state.hitMax && state.hitDepth ? "max+depth" : state.hitMax ? "max" : state.hitDepth ? "depth" : "no"
FileAppend state.lines "elements=" state.count "`ntruncated=" truncated "`n", "*"

; Splits the command line into the WinTitle and the options, and rejects values that would print nothing.
ParseArgs(args) {
    request := {target: "", find: "", type: "", depth: DEFAULT_DEPTH, max: DEFAULT_MAX}
    i := 1
    while (i <= args.Length) {
        arg := args[i]
        if (arg = "--depth" || arg = "--max" || arg = "--find" || arg = "--type") {
            if (i = args.Length)
                throw ValueError(arg " needs a value")
            i++
            value := args[i]
            if (arg = "--depth" || arg = "--max") {
                if !IsInteger(value) || Integer(value) < 1
                    throw ValueError(arg " must be at least 1")
                value := Integer(value)
            } else if (arg = "--type" && !UIA.Type.HasOwnProp(value))
                throw ValueError("--type must be a UI Automation control type such as Button, Edit, or Text; got `"" value "`"")
            request.%SubStr(arg, 3)% := value
        } else if (request.target = "")
            request.target := arg
        else
            throw ValueError("Unexpected argument `"" arg "`"; usage: tree.ahk `"<WinTitle>`" [--find <text>] [--type <Type>] [--depth N] [--max N]")
        i++
    }
    if (request.target = "")
        throw ValueError("Usage: tree.ahk `"<WinTitle>`" [--find <text>] [--type <Type>] [--depth N] [--max N]")
    return request
}

; Appends one line per matching element below `element`, depth first. Stops at the element budget and the
; depth budget, and records which one cut the dump.
Walk(element, path, level) {
    for index, child in element.CachedChildren {
        if state.hitMax
            return
        childPath := path (path != "" ? "," : "") index
        if Wanted(child) {
            if (state.count >= request.max) {
                state.hitMax := true
                return
            }
            state.lines .= Describe(child, childPath) "`n"
            state.count++
        }
        if (level < request.depth)
            Walk(child, childPath, level + 1)
        else if (child.CachedChildren.Length > 0)
            state.hitDepth := true
    }
}

; Whether an element passes the --find and --type filters. Both are case-insensitive.
Wanted(element) {
    if (request.type != "" && UIA.Type[element.CachedType] != request.type)
        return false
    if (request.find != "" && !InStr(element.CachedName, request.find) && !InStr(element.CachedAutomationId, request.find))
        return false
    return true
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

; Text as the contents of an AutoHotkey double-quoted string: backticks, quotes, and line breaks escaped,
; so what the dump shows is what a script writes.
Literal(text) {
    return StrReplace(StrReplace(StrReplace(StrReplace(text, "``", "````"), '"', '``"'), "`r", "``r"), "`n", "``n")
}
