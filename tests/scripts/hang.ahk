; Moves the cursor, then sleeps far past the launcher timeout. Pumps messages, so the close request reaches
; this script's own exit handler, which prints. ACU leaves cursor and foreground unchanged at exit.
OnExit (reason, code) => (FileAppend("hang: exit handler ran, reason=" reason "`n", "*"), 0)
MouseMove 300, 300
Sleep 20000
FileAppend "hang: finished sleeping`n", "*"
