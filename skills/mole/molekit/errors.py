"""Stable errors shared across CLI and engine boundaries."""


class MoleError(Exception):
    def __init__(self, code, message, exit_code=2, action="Correct the request and retry."):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.action = action
