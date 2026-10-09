; ACU screenshot script: the agent's way to see the screen. Run it through the launcher:
;   python acu/run.py acu/screenshot.ahk -- fullscreen [monitor]
;   python acu/run.py acu/screenshot.ahk -- app <WinTitle>
;   python acu/run.py acu/screenshot.ahk -- custom <x1> <y1> <x2> <y2>
; Options for every action: --out <path.png>, --max <pixels> (longest side of the saved image,
; default 1280, 0 keeps full size). Prints four lines:
;   saved=<path>  image=<w>x<h>  source=<x>,<y> <w>x<h>  scale=<source pixels per image pixel>
; A point (px, py) in the image is the screen point (x + px * scale, y + py * scale).
; Without --out the file goes to <ACU_HOME>\shots\ and only the newest 30 files there are kept.
#Requires AutoHotkey v2.0

DEFAULT_MAX := 1280
KEEP_SHOTS := 30
PNG_ENCODER := "{557CF406-1A04-11D3-9A73-0000F81EF32E}"
PIXEL_FORMAT_32BPP_ARGB := 0x26200A

request := ParseArgs(A_Args)
shot := Capture(request)
pruneDir := ""
if (request.out = "") {
    pruneDir := ShotsDir()
    request.out := pruneDir "\" FormatTime(, "yyyyMMdd-HHmmss") "-" A_MSec "-" request.action ".png"
}
saved := SavePng(shot, request.max, request.out)
if (pruneDir != "")
    Prune(pruneDir, KEEP_SHOTS)

FileAppend "saved=" request.out "`n", "*"
FileAppend "image=" saved.width "x" saved.height "`n", "*"
FileAppend "source=" shot.x "," shot.y " " shot.w "x" shot.h "`n", "*"
FileAppend "scale=" (saved.scale = Round(saved.scale) ? Integer(saved.scale) : Round(saved.scale, 4)) "`n", "*"

; Splits the command line into the action, its positional parameters, and the two options.
ParseArgs(args) {
    request := {action: "", params: [], out: "", max: DEFAULT_MAX}
    i := 1
    while (i <= args.Length) {
        arg := args[i]
        if (arg = "--out" || arg = "--max") {
            if (i = args.Length)
                throw ValueError(arg " needs a value")
            i++
            if (arg = "--out")
                request.out := StrReplace(args[i], "/", "\")  ; shells like Git Bash hand over forward slashes
            else
                request.max := Integer(args[i])
        } else if (request.action = "")
            request.action := arg
        else
            request.params.Push(arg)
        i++
    }
    if (request.action = "")
        throw ValueError("Usage: screenshot.ahk fullscreen [monitor] | app <WinTitle> | custom <x1> <y1> <x2> <y2>  [--out <path>] [--max <pixels>]")
    return request
}

; Grabs the pixels for the requested action. Returns the source rectangle in screen pixels and an HBITMAP,
; plus the offset to crop when the bitmap is larger than the rectangle (a window's invisible border).
Capture(request) {
    params := request.params
    switch request.action {
    case "fullscreen":
        monitor := params.Length ? Integer(params[1]) : 1
        MonitorGet monitor, &left, &top, &right, &bottom
        return {x: left, y: top, w: right - left, h: bottom - top, hbm: CaptureScreen(left, top, right - left, bottom - top), cropX: 0, cropY: 0}
    case "custom":
        if (params.Length != 4)
            throw ValueError("custom needs x1 y1 x2 y2")
        x := Integer(params[1]), y := Integer(params[2])
        w := Integer(params[3]) - x, h := Integer(params[4]) - y
        if (w <= 0 || h <= 0)
            throw ValueError("custom rectangle must have x2 > x1 and y2 > y1")
        return {x: x, y: y, w: w, h: h, hbm: CaptureScreen(x, y, w, h), cropX: 0, cropY: 0}
    case "app":
        if (params.Length != 1)
            throw ValueError("app needs one WinTitle, for example `"ahk_exe notepad.exe`"")
        hwnd := WinGetID(params[1])
        if (WinGetMinMax(hwnd) = -1)
            throw Error("Window is minimized; restore or activate it first.")
        full := Buffer(16)
        DllCall("GetWindowRect", "ptr", hwnd, "ptr", full)
        frame := Buffer(16)
        if DllCall("dwmapi\DwmGetWindowAttribute", "ptr", hwnd, "uint", 9, "ptr", frame, "uint", 16)
            frame := full
        fullX := NumGet(full, 0, "int"), fullY := NumGet(full, 4, "int")
        fullW := NumGet(full, 8, "int") - fullX, fullH := NumGet(full, 12, "int") - fullY
        x := NumGet(frame, 0, "int"), y := NumGet(frame, 4, "int")
        w := NumGet(frame, 8, "int") - x, h := NumGet(frame, 12, "int") - y
        return {x: x, y: y, w: w, h: h, hbm: CaptureWindow(hwnd, fullW, fullH), cropX: x - fullX, cropY: y - fullY}
    default:
        throw ValueError("Unknown action `"" request.action "`"; use fullscreen, app, or custom")
    }
}

; Copies a screen rectangle into a new HBITMAP, exactly as it is displayed.
CaptureScreen(x, y, w, h) {
    return CaptureToBitmap(w, h, "Screen capture failed (BitBlt).", (memory, screen) =>
        DllCall("BitBlt", "ptr", memory, "int", 0, "int", 0, "int", w, "int", h, "ptr", screen, "int", x, "int", y, "uint", 0x00CC0020))
}

; Asks a window to render itself into a new HBITMAP, so covered windows still show their own content
; and nothing is activated. PW_RENDERFULLCONTENT covers windows composed by DWM, such as browsers.
CaptureWindow(hwnd, w, h) {
    return CaptureToBitmap(w, h, "The window did not render (PrintWindow failed).", (memory, *) =>
        DllCall("PrintWindow", "ptr", hwnd, "ptr", memory, "uint", 2))
}

; Creates a screen-compatible HBITMAP of the given size and lets draw(memoryDC, screenDC) fill it.
; draw returns zero on failure, which becomes an Error with the given message.
CaptureToBitmap(w, h, failure, draw) {
    screen := DllCall("GetDC", "ptr", 0, "ptr")
    memory := DllCall("CreateCompatibleDC", "ptr", screen, "ptr")
    hbm := DllCall("CreateCompatibleBitmap", "ptr", screen, "int", w, "int", h, "ptr")
    previous := DllCall("SelectObject", "ptr", memory, "ptr", hbm, "ptr")
    drawn := draw(memory, screen)
    DllCall("SelectObject", "ptr", memory, "ptr", previous, "ptr")
    DllCall("DeleteDC", "ptr", memory)
    DllCall("ReleaseDC", "ptr", 0, "ptr", screen)
    if !drawn {
        DllCall("DeleteObject", "ptr", hbm)
        throw Error(failure)
    }
    return hbm
}

; Crops, downscales so the longest side is at most maxSide (0 disables), and writes the PNG through GDI+.
; Returns the saved width and height and the scale, in source pixels per image pixel.
SavePng(capture, maxSide, path) {
    ; DllCall loads and frees a DLL named inline on every call. GDI+ keeps state between calls, so pin it.
    module := DllCall("LoadLibrary", "str", "gdiplus", "ptr")
    startup := Buffer(24, 0)
    NumPut("uint", 1, startup)
    token := 0
    if DllCall("gdiplus\GdiplusStartup", "ptr*", &token, "ptr", startup, "ptr", 0)
        throw Error("GDI+ failed to start.")
    try {
        bitmap := 0
        Gdip("GdipCreateBitmapFromHBITMAP", "ptr", capture.hbm, "ptr", 0, "ptr*", &bitmap)
        DllCall("DeleteObject", "ptr", capture.hbm)
        if (capture.cropX || capture.cropY) {
            cropped := 0
            Gdip("GdipCloneBitmapAreaI", "int", capture.cropX, "int", capture.cropY, "int", capture.w, "int", capture.h, "int", PIXEL_FORMAT_32BPP_ARGB, "ptr", bitmap, "ptr*", &cropped)
            Gdip("GdipDisposeImage", "ptr", bitmap)
            bitmap := cropped
        }
        scale := 1
        longest := Max(capture.w, capture.h)
        if (maxSide > 0 && longest > maxSide)
            scale := longest / maxSide
        width := Max(1, Round(capture.w / scale)), height := Max(1, Round(capture.h / scale))
        if (scale != 1) {
            scaled := 0
            Gdip("GdipCreateBitmapFromScan0", "int", width, "int", height, "int", 0, "int", PIXEL_FORMAT_32BPP_ARGB, "ptr", 0, "ptr*", &scaled)
            graphics := 0
            Gdip("GdipGetImageGraphicsContext", "ptr", scaled, "ptr*", &graphics)
            Gdip("GdipSetInterpolationMode", "ptr", graphics, "int", 7)  ; HighQualityBicubic
            Gdip("GdipSetPixelOffsetMode", "ptr", graphics, "int", 2)    ; HighQuality
            Gdip("GdipDrawImageRectI", "ptr", graphics, "ptr", bitmap, "int", 0, "int", 0, "int", width, "int", height)
            Gdip("GdipDeleteGraphics", "ptr", graphics)
            Gdip("GdipDisposeImage", "ptr", bitmap)
            bitmap := scaled
        }
        SplitPath path, , &directory
        if (directory != "" && !DirExist(directory))
            DirCreate directory
        encoder := Buffer(16)
        DllCall("ole32\CLSIDFromString", "wstr", PNG_ENCODER, "ptr", encoder)
        status := DllCall("gdiplus\GdipSaveImageToFile", "ptr", bitmap, "wstr", path, "ptr", encoder, "ptr", 0)
        Gdip("GdipDisposeImage", "ptr", bitmap)
        if status
            throw Error("Could not save the PNG (GDI+ status " status "): " path)
        return {width: width, height: height, scale: scale}
    } finally {
        DllCall("gdiplus\GdiplusShutdown", "ptr", token)
        DllCall("FreeLibrary", "ptr", module)
    }
}

; Calls one GDI+ function and throws when it reports a non-zero status, so a failed step cannot save a blank image.
Gdip(name, args*) {
    status := DllCall("gdiplus\" name, args*)
    if status
        throw Error("GDI+ " name " failed with status " status)
}

; Default folder for screenshots: <ACU_HOME>\shots, with ACU_HOME defaulting to %LOCALAPPDATA%\ACU.
ShotsDir() {
    home := EnvGet("ACU_HOME")
    if (home = "")
        home := EnvGet("LOCALAPPDATA") "\ACU"
    dir := home "\shots"
    if !DirExist(dir)
        DirCreate dir
    return dir
}

; Deletes all but the newest `keep` PNG files in dir, whoever wrote them. Screenshots can contain secrets,
; so the default folder is managed and they do not pile up.
Prune(dir, keep) {
    entries := ""
    Loop Files dir "\*.png"
        entries .= A_LoopFileTimeModified "`t" A_LoopFileFullPath "`n"
    if (entries = "")
        return
    Loop Parse Sort(RTrim(entries, "`n"), "R"), "`n"
        if (A_Index > keep)
            FileDelete StrSplit(A_LoopField, "`t")[2]
}
