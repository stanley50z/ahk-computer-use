# Calculator buttons, v3

Open a new Windows Calculator window and calculate:

128+465*12387/138473-12343

Perform the calculation by activating Calculator's UI buttons, including any mode changes. Pointer clicks and semantic button activation (such as UI Automation Invoke) are both allowed. Do not type, send keyboard input or shortcuts, set field values directly, use the clipboard, or evaluate the arithmetic in code. Accessibility information may locate controls and read state. Follow normal mathematical operator precedence.

Use only the selected computer-use tool and its corresponding skill. First read that skill. Do not explore the project, load another skill, inspect other agent sessions, or use another desktop automation route. Ordinary shell/file tools may launch the selected tool and manage evidence files, not substitute for UI interaction.

You have permission to open and visibly operate your own Calculator window for this run. Preserve all pre-existing windows and documents. Determine which window you opened; do not reuse an existing Calculator. Immediately write ownership.json in the workspace with the returned window_id or hwnd and its returned target identity before any clicks, so the bench can clean up even if the task fails. Include pid if the selected tool exposes it; otherwise omit it rather than using another automation route or inventing it. The independent bench observer will check the native window/process identity outside the timed run. If you cannot obtain a separate window, stop and report the precondition failure. If the tool reports user takeover or a permission boundary, stop; do not work around it.

Keep every script and other evidence you create inside the current workspace. Do not delete scripts: the bench needs them for audit. Observe the displayed result and expression, then write result.json in the workspace with these fields: status (completed or blocked), window_id or hwnd (as returned by the selected tool), observed_result (the actual displayed text), observed_expression, input_method, and hiccups (an array of concrete problems or mistakes encountered). Record facts, not a result computed independently. Do not invent missing evidence.

Leave your Calculator window open for the independent bench verifier; the bench will capture its state and close only your window. Give a short final answer with the observed result, completion status, and blunt feedback on the selected skill. Do not improve the skill or tool implementation during the test.
