; Screen capture for every ACU script, included by the prelude. AcuScreenshot saves a PNG and reports where the
; image sits on the screen; screenshot.ahk is the command-line wrapper around it. Everything else here is internal
; and prefixed AcuShot so it cannot collide with a name an agent's script defines.
#Requires AutoHotkey v2.0

; Captures one display, one window, or a screen rectangle and saves it as a PNG:
;   AcuScreenshot()                            monitor 1
;   AcuScreenshot({monitor: 2})                another display, by AutoHotkey monitor number
;   AcuScreenshot({app: "ahk_id " hwnd})       one window as it renders itself; it is never activated
;   AcuScreenshot({rect: [x1, y1, x2, y2]})    a screen rectangle, far edge exclusive
; out is the PNG path; without it the file goes to <ACU_HOME>\shots\, where only the newest 30 are kept. maxSide is
; the longest side of the saved image, 0 for full size. Returns {saved, width, height, x, y, w, h, scale, text}: the
; source rectangle in screen pixels, scale in source pixels per image pixel, and text as the four lines
; screenshot.ahk prints. A point (px, py) in the image is the screen point (x + px * scale, y + py * scale).
AcuScreenshot(spec := "", out := "", maxSide := 1280) {
    if !IsObject(spec)
        spec := {monitor: spec = "" ? 1 : Integer(spec)}
    shot := AcuShotCapture(spec)
    pruneDir := ""
    if (out = "") {
        pruneDir := AcuShotDir()
        out := pruneDir "\" FormatTime(, "yyyyMMdd-HHmmss") "-" A_MSec "-" shot.action ".png"
    } else
        out := StrReplace(out, "/", "\")  ; shells like Git Bash hand over forward slashes
    saved := AcuShotSave(shot, maxSide, out)
    if (pruneDir != "")
        AcuShotPrune(pruneDir, 30)
    printedScale := saved.scale = Round(saved.scale) ? Integer(saved.scale) : Round(saved.scale, 4)
    text := "saved=" out "`nimage=" saved.width "x" saved.height "`nsource=" shot.x "," shot.y " " shot.w "x" shot.h "`nscale=" printedScale "`n"
    return {saved: out, width: saved.width, height: saved.height, x: shot.x, y: shot.y, w: shot.w, h: shot.h, scale: saved.scale, text: text}
}

; Grabs the pixels for the requested capture. Returns the source rectangle in screen pixels and an HBITMAP,
; plus the offset to crop when the bitmap is larger than the rectangle (a window's invisible border).
AcuShotCapture(spec) {
    if spec.HasProp("app") {
        hwnd := WinGetID(spec.app)
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
        return {action: "app", x: x, y: y, w: w, h: h, hbm: AcuShotWindow(hwnd, fullW, fullH), cropX: x - fullX, cropY: y - fullY}
    }
    if spec.HasProp("rect") {
        rect := spec.rect
        if (!(rect is Array) || rect.Length != 4)
            throw ValueError("rect needs [x1, y1, x2, y2]")
        x := Integer(rect[1]), y := Integer(rect[2])
        w := Integer(rect[3]) - x, h := Integer(rect[4]) - y
        if (w <= 0 || h <= 0)
            throw ValueError("custom rectangle must have x2 > x1 and y2 > y1")
        return {action: "custom", x: x, y: y, w: w, h: h, hbm: AcuShotScreen(x, y, w, h), cropX: 0, cropY: 0}
    }
    monitor := spec.HasProp("monitor") ? Integer(spec.monitor) : 1
    MonitorGet monitor, &left, &top, &right, &bottom
    return {action: "fullscreen", x: left, y: top, w: right - left, h: bottom - top, hbm: AcuShotScreen(left, top, right - left, bottom - top), cropX: 0, cropY: 0}
}

; Copies a screen rectangle into a new HBITMAP, exactly as it is displayed.
AcuShotScreen(x, y, w, h) {
    return AcuShotBitmap(w, h, "Screen capture failed (BitBlt).", (memory, screen) =>
        DllCall("BitBlt", "ptr", memory, "int", 0, "int", 0, "int", w, "int", h, "ptr", screen, "int", x, "int", y, "uint", 0x00CC0020))
}

; Asks a window to render itself into a new HBITMAP, so covered windows still show their own content
; and nothing is activated. PW_RENDERFULLCONTENT covers windows composed by DWM, such as browsers.
; A window that is not per-monitor DPI aware draws at the size it believes it has and Windows scales that on
; screen, so it is rendered at its own size here and scaled to its on-screen size, which is what w and h are.
AcuShotWindow(hwnd, w, h) {
    render := (memory, *) => DllCall("PrintWindow", "ptr", hwnd, "ptr", memory, "uint", 2)
    failure := "The window did not render (PrintWindow failed)."
    ; The window's size as seen from its own DPI awareness context is the size PrintWindow renders.
    previous := DllCall("SetThreadDpiAwarenessContext", "ptr", DllCall("GetWindowDpiAwarenessContext", "ptr", hwnd, "ptr"), "ptr")
    own := Buffer(16)
    DllCall("GetWindowRect", "ptr", hwnd, "ptr", own)
    DllCall("SetThreadDpiAwarenessContext", "ptr", previous, "ptr")
    renderedW := NumGet(own, 8, "int") - NumGet(own, 0, "int"), renderedH := NumGet(own, 12, "int") - NumGet(own, 4, "int")
    if (renderedW = w && renderedH = h)
        return AcuShotBitmap(w, h, failure, render)
    rendered := AcuShotBitmap(renderedW, renderedH, failure, render)
    try
        return AcuShotBitmap(w, h, "Scaling the rendered window failed (StretchBlt).", (memory, screen) =>
            AcuShotStretch(memory, screen, rendered, renderedW, renderedH, w, h))
    finally
        DllCall("DeleteObject", "ptr", rendered)
}

; Draws the whole source bitmap into the memory DC at w by h, with pixel averaging rather than dropping.
AcuShotStretch(memory, screen, source, sourceW, sourceH, w, h) {
    sourceDC := DllCall("CreateCompatibleDC", "ptr", screen, "ptr")
    previous := DllCall("SelectObject", "ptr", sourceDC, "ptr", source, "ptr")
    DllCall("SetStretchBltMode", "ptr", memory, "int", 4)  ; HALFTONE
    drawn := DllCall("StretchBlt", "ptr", memory, "int", 0, "int", 0, "int", w, "int", h, "ptr", sourceDC, "int", 0, "int", 0, "int", sourceW, "int", sourceH, "uint", 0x00CC0020)
    DllCall("SelectObject", "ptr", sourceDC, "ptr", previous, "ptr")
    DllCall("DeleteDC", "ptr", sourceDC)
    return drawn
}

; Creates a screen-compatible HBITMAP of the given size and lets draw(memoryDC, screenDC) fill it.
; draw returns zero on failure, which becomes an Error with the given message.
AcuShotBitmap(w, h, failure, draw) {
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
AcuShotSave(capture, maxSide, path) {
    pngEncoder := "{557CF406-1A04-11D3-9A73-0000F81EF32E}"
    pixelFormat32bppArgb := 0x26200A
    ; DllCall loads and frees a DLL named inline on every call. GDI+ keeps state between calls, so pin it.
    module := DllCall("LoadLibrary", "str", "gdiplus", "ptr")
    startup := Buffer(24, 0)
    NumPut("uint", 1, startup)
    token := 0
    if DllCall("gdiplus\GdiplusStartup", "ptr*", &token, "ptr", startup, "ptr", 0)
        throw Error("GDI+ failed to start.")
    try {
        bitmap := 0
        AcuShotGdip("GdipCreateBitmapFromHBITMAP", "ptr", capture.hbm, "ptr", 0, "ptr*", &bitmap)
        DllCall("DeleteObject", "ptr", capture.hbm)
        if (capture.cropX || capture.cropY) {
            cropped := 0
            AcuShotGdip("GdipCloneBitmapAreaI", "int", capture.cropX, "int", capture.cropY, "int", capture.w, "int", capture.h, "int", pixelFormat32bppArgb, "ptr", bitmap, "ptr*", &cropped)
            AcuShotGdip("GdipDisposeImage", "ptr", bitmap)
            bitmap := cropped
        }
        scale := 1
        longest := Max(capture.w, capture.h)
        if (maxSide > 0 && longest > maxSide)
            scale := longest / maxSide
        width := Max(1, Round(capture.w / scale)), height := Max(1, Round(capture.h / scale))
        if (scale != 1) {
            scaled := 0
            AcuShotGdip("GdipCreateBitmapFromScan0", "int", width, "int", height, "int", 0, "int", pixelFormat32bppArgb, "ptr", 0, "ptr*", &scaled)
            graphics := 0
            AcuShotGdip("GdipGetImageGraphicsContext", "ptr", scaled, "ptr*", &graphics)
            AcuShotGdip("GdipSetInterpolationMode", "ptr", graphics, "int", 7)  ; HighQualityBicubic
            AcuShotGdip("GdipSetPixelOffsetMode", "ptr", graphics, "int", 2)    ; HighQuality
            AcuShotGdip("GdipDrawImageRectI", "ptr", graphics, "ptr", bitmap, "int", 0, "int", 0, "int", width, "int", height)
            AcuShotGdip("GdipDeleteGraphics", "ptr", graphics)
            AcuShotGdip("GdipDisposeImage", "ptr", bitmap)
            bitmap := scaled
        }
        SplitPath path, , &directory
        if (directory != "" && !DirExist(directory))
            DirCreate directory
        encoder := Buffer(16)
        DllCall("ole32\CLSIDFromString", "wstr", pngEncoder, "ptr", encoder)
        status := DllCall("gdiplus\GdipSaveImageToFile", "ptr", bitmap, "wstr", path, "ptr", encoder, "ptr", 0)
        AcuShotGdip("GdipDisposeImage", "ptr", bitmap)
        if status
            throw Error("Could not save the PNG (GDI+ status " status "): " path)
        return {width: width, height: height, scale: scale}
    } finally {
        DllCall("gdiplus\GdiplusShutdown", "ptr", token)
        DllCall("FreeLibrary", "ptr", module)
    }
}

; Calls one GDI+ function and throws when it reports a non-zero status, so a failed step cannot save a blank image.
AcuShotGdip(name, args*) {
    status := DllCall("gdiplus\" name, args*)
    if status
        throw Error("GDI+ " name " failed with status " status)
}

; Default folder for screenshots: <ACU_HOME>\shots, with ACU_HOME defaulting to %LOCALAPPDATA%\ACU.
AcuShotDir() {
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
AcuShotPrune(dir, keep) {
    entries := ""
    Loop Files dir "\*.png"
        entries .= A_LoopFileTimeModified "`t" A_LoopFileFullPath "`n"
    if (entries = "")
        return
    Loop Parse Sort(RTrim(entries, "`n"), "R"), "`n"
        if (A_Index > keep)
            FileDelete StrSplit(A_LoopField, "`t")[2]
}
