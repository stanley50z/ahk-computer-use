"""Process adapter for launcher tests; no OS process or desktop access."""

import signal
import subprocess
from pathlib import Path


class FakeValidator:
    """Model validation communication, cancellation, and pipe ownership."""

    def __init__(self, events):
        self.events = events
        self.returncode = None
        self.stdout = self
        self.output = b""
        self.timeout = False
        self.budgets = []
        self.on_communicate = None

    def communicate(self, timeout=None):
        if self.on_communicate is not None:
            self.on_communicate()
        if timeout is not None:
            self.budgets.append(timeout)
            if self.timeout:
                raise subprocess.TimeoutExpired("validate", timeout, output=self.output)
        self.returncode = 0 if self.returncode is None else self.returncode
        return self.output, None

    def poll(self):
        return self.returncode

    def kill(self):
        self.events.append("validator.kill")
        self.returncode = -9

    def wait(self):
        self.events.append("validator.wait")
        assert self.returncode is not None
        return self.returncode

    def close(self):
        self.events.append("validator.close")


class FakeScript:
    """Keep process ownership observable until wait confirms exit."""

    def __init__(self, events):
        self.events = events
        self.alive = False
        self.closed = False
        self.finish = True
        self.ignore_close = False
        self.interrupt_wait = False
        self.interrupt_close = False
        self.kill_failure = False
        self.failed_kill = False
        self.checks_after_failure = 0
        self.code = 0
        self.budgets = []

    def wait(self, timeout):
        self.budgets.append(timeout)
        if self.interrupt_wait:
            self.interrupt_wait = False
            raise KeyboardInterrupt
        if self.failed_kill:
            self.checks_after_failure += 1
            if self.checks_after_failure >= 3:
                self.alive = False
        elif self.finish:
            self.alive = False
        self.events.append("script.exited" if not self.alive else "script.running")
        return not self.alive

    def request_close(self):
        self.events.append("script.request_close")
        if self.interrupt_close:
            self.interrupt_close = False
            raise KeyboardInterrupt
        if not self.ignore_close:
            self.alive = False

    def kill(self):
        self.events.append("script.kill")
        if self.kill_failure:
            self.failed_kill = True
            raise OSError("termination denied")
        self.alive = False

    def exit_code(self):
        assert not self.alive
        return self.code

    def close(self):
        assert not self.alive, "released ownership of a live script"
        self.events.append("script.close_handle")
        self.closed = True


class FakeProcessAdapter:
    """Supply both process types through the launcher's public adapter seam."""

    def __init__(self, output=""):
        self.events = []
        self.validator = FakeValidator(self.events)
        self.script = FakeScript(self.events)
        self.output = output
        self.interrupt_creation = None
        self.validation_command = None
        self.script_arguments = None

    def start_validation(self, command):
        self.events.append("validator.start")
        self.validation_command = command
        if self.interrupt_creation == "validation":
            signal.raise_signal(signal.SIGINT)
        return self.validator

    def start_script(self, exe, arguments):
        self.events.append("script.start")
        self.script_arguments = arguments
        output_path = next(value.removeprefix("--acu-out=") for value in arguments if value.startswith("--acu-out="))
        Path(output_path).write_text(self.output, encoding="utf-8")
        self.script.alive = True
        if self.interrupt_creation == "execution":
            signal.raise_signal(signal.SIGINT)
        return self.script
