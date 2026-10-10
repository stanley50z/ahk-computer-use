; Exercises AcuWaitUntil: the predicate's value comes back as soon as it is true, and 0 once the time ran out.
start := A_TickCount
value := AcuWaitUntil(() => A_TickCount - start >= 120 ? "seen" : 0, 2000)
late := AcuWaitUntil(() => 0, 150)
FileAppend "value=" value "`nlate=" late "`nelapsed=" (A_TickCount - start) "`n", "*"
