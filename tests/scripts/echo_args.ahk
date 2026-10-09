; Prints the command-line arguments the launcher forwarded, joined with |.
joined := ""
for arg in A_Args
    joined .= (A_Index > 1 ? "|" : "") arg
FileAppend "args=" joined "`n", "*"
