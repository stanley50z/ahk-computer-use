; Launches a hidden child that lives for about 5 s and exits at once. The child inherits the launcher's
; output pipe, so a launcher that waited for end-of-file instead of the script would stall until the child ended.
Run "cmd.exe /c ping -n 6 127.0.0.1 >nul", , "Hide"
FileAppend "spawned`n", "*"
