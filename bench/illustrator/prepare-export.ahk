; Commit one blank calibration export through the real dialogs: Illustrator caches PNG options beyond its preference API.
hwnd := Integer(A_Args[1])
pid := Integer(A_Args[2])
target := "ahk_id " hwnd
if !WinExist(target) || WinGetPID(target) != pid
    throw Error("Illustrator identity changed")
WinActivate target
if !WinWaitActive(target, , 3)
    throw Error("Illustrator did not activate")
SetKeyDelay 30,30
SendEvent "!fe{Right}{Down}{Enter}"
dialog := AcuWaitUntil(() => WinExist("Export ahk_class #32770 ahk_pid " pid), 5000)
if !dialog || WinGetTitle("ahk_id " dialog) != "Export"
    throw Error("Export As dialog did not appear")
root := UIA.ElementFromHandle(dialog)
root.FindElement({Type:"ComboBox", Name:"Save as type:"}).Expand()
root.FindElement({Type:"ListItem", Name:"PNG (*.PNG)"}).Select()
root.FindElement({Type:"Edit", Name:"File name:"}).Value := A_Args[3]
artboards := root.FindElement({Type:"CheckBox", Name:"Use Artboards"})
if artboards.GetPropertyValue(UIA.Property.ToggleToggleState) != 1
    artboards.Toggle()
suffix := root.FindElement({Type:"CheckBox", Name:"Suffix"})
if suffix.GetPropertyValue(UIA.Property.ToggleToggleState) != 0
    suffix.Toggle()
root.FindElement({Type:"Button", Name:"Export", AutomationId:"1"}).Invoke()
options := AcuWaitUntil(() => WinExist("PNG Options ahk_pid " pid), 5000)
if !options
    throw Error("PNG Options did not appear")
root := UIA.ElementFromHandle(options)
root.FindElement({Type:"ListItem", Name:"Screen (72 ppi)"}).Select()
root.FindElement({Type:"ListItem", Name:"Art Optimized (Supersampling)"}).Select()
root.FindElement({Type:"ListItem", Name:"White"}).Select()
interlaced := root.FindElement({Type:"CheckBox", Name:"Interlaced"})
if interlaced.GetPropertyValue(UIA.Property.ToggleToggleState) != 0
    interlaced.Toggle()
values := Map()
for box in root.FindElements({Type:"ComboBox"})
    values[box.Value] := true
for expected in ["Screen (72 ppi)", "Art Optimized (Supersampling)", "White"]
    if !values.Has(expected)
        throw Error("PNG option did not take effect: " expected)
FileAppend AcuTree("ahk_id " options, {depth:8,max:100}), "*"
root.FindElement({Type:"Button", Name:"OK"}).Invoke()
if !WinWaitClose("ahk_id " options, , 5) || !AcuWaitUntil(() => FileExist(A_Args[3]), 5000)
    throw Error("Blank calibration export did not finish at its requested path")
FileAppend '{"resolution":"Screen (72 ppi)","anti_aliasing":"Art Optimized (Supersampling)","background":"White","interlaced":false,"use_artboards":true,"suffix":false}', A_Args[4], "UTF-8-RAW"
