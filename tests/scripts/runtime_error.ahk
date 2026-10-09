; Raises a runtime error on line 3. The prelude must print it and exit non-zero instead of showing a dialog.
FileAppend "before`n", "*"
WinActivate "ahk_class NoSuchWindowClass_ACU"
FileAppend "after`n", "*"
