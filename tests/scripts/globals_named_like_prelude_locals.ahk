; Declares globals with the same names as locals inside the prelude. That is the script's business and
; must not produce a warning about the prelude.
root := 1
x := 2
hwnd := 3
FileAppend "sum=" root + x + hwnd "`n", "*"
