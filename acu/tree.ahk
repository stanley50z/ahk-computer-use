; ACU tree script: the agent's way to find controls by name from the command line. Run it through the launcher:
;   acu run tree.ahk -- "<WinTitle>" [--find <text>] [--type <Type>] [--depth N] [--max N]
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
; The dump itself is the prelude's AcuTree, which any script can call directly; this file only parses arguments.
#Requires AutoHotkey v2.0

request := ParseArgs(A_Args)
FileAppend AcuTree(request.target, request), "*"

; Splits the command line into the WinTitle and the options, and rejects values that would print nothing.
ParseArgs(args) {
    request := {target: "", find: "", type: "", depth: 25, max: 300}
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
