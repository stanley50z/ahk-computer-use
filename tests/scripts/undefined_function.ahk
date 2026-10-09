; Calls a function that does not exist, a typo an agent will make. AutoHotkey treats the name as an unset
; variable: a load-time warning, then a runtime error. Neither may become a dialog.
FileAppend "before`n", "*"
NoSuchFunctionACU()
FileAppend "after`n", "*"
