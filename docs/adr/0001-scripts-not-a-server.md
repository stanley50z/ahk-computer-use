# A script is the unit of action, run by a launcher; there is no server

The agent already has a shell, a file writer, and fluency in AutoHotkey v2, so each action chain is a plain script the agent writes and runs through the launcher, and nothing runs between scripts. Vendor computer-use protocols and every comparable project put a daemon or MCP server between the model and the operating system; we chose against one because it adds a process to install, a protocol to version, and a model round trip per action, while a script collapses a predictable chain into one run of a few hundred milliseconds.

## Consequences

- The agent writes code, not tool calls, so the skill document is the main lever on its behavior and the cheapest thing to iterate on.
- An MCP front end can be added later for a client without a shell, without changing what a script is.
- Scripts share one cursor and one keyboard focus; the skill tells the agent to run one at a time.
