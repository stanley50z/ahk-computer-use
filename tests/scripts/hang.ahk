; Moves the cursor, then sleeps far past the launcher timeout. Pumps messages, so the close request reaches
; both exit handlers: this script's own, which prints, and the prelude's, which puts the cursor back.
OnExit (reason, code) => (FileAppend("hang: exit handler ran, reason=" reason "`n", "*"), 0)
MouseMove 300, 300
Sleep 20000
FileAppend "hang: finished sleeping`n", "*"
