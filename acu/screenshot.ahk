; ACU screenshot script: the agent's way to see the screen from the command line. Run it through the launcher:
;   acu run screenshot.ahk -- fullscreen [monitor]
;   acu run screenshot.ahk -- app <WinTitle>
;   acu run screenshot.ahk -- custom <x1> <y1> <x2> <y2>
; Options for every action: --out <path.png>, --max <pixels> (longest side of the saved image,
; default 1280, 0 keeps full size). Prints four lines:
;   saved=<path>  image=<w>x<h>  source=<x>,<y> <w>x<h>  scale=<source pixels per image pixel>
; A point (px, py) in the image is the screen point (x + px * scale, y + py * scale).
; Without --out the file goes to <ACU_HOME>\shots\ and only the newest 30 files there are kept.
; The capture itself is the prelude's AcuScreenshot, which any script can call directly; this file only parses arguments.
#Requires AutoHotkey v2.0

request := ParseArgs(A_Args)
FileAppend AcuScreenshot(request.spec, request.out, request.max).text, "*"

; Splits the command line into the capture spec AcuScreenshot takes and the two options.
ParseArgs(args) {
    request := {action: "", params: [], out: "", max: 1280, spec: ""}
    i := 1
    while (i <= args.Length) {
        arg := args[i]
        if (arg = "--out" || arg = "--max") {
            if (i = args.Length)
                throw ValueError(arg " needs a value")
            i++
            if (arg = "--out")
                request.out := args[i]
            else
                request.max := Integer(args[i])
        } else if (request.action = "")
            request.action := arg
        else
            request.params.Push(arg)
        i++
    }
    params := request.params
    switch request.action {
    case "fullscreen":
        request.spec := {monitor: params.Length ? Integer(params[1]) : 1}
    case "app":
        if (params.Length != 1)
            throw ValueError("app needs one WinTitle, for example `"ahk_exe notepad.exe`"")
        request.spec := {app: params[1]}
    case "custom":
        if (params.Length != 4)
            throw ValueError("custom needs x1 y1 x2 y2")
        request.spec := {rect: [Integer(params[1]), Integer(params[2]), Integer(params[3]), Integer(params[4])]}
    case "":
        throw ValueError("Usage: screenshot.ahk fullscreen [monitor] | app <WinTitle> | custom <x1> <y1> <x2> <y2>  [--out <path>] [--max <pixels>]")
    default:
        throw ValueError("Unknown action `"" request.action "`"; use fullscreen, app, or custom")
    }
    return request
}
