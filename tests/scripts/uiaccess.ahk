; Prints whether this script's process holds the UI Access privilege, which is what lets it see and drive elevated windows.
token := 0
DllCall("advapi32\OpenProcessToken", "ptr", -1, "uint", 0x8, "ptr*", &token)
flag := 0
DllCall("advapi32\GetTokenInformation", "ptr", token, "int", 26, "uint*", &flag, "uint", 4, "uint*", &size := 0)
DllCall("CloseHandle", "ptr", token)
FileAppend "uiaccess=" flag "`n", "*"
