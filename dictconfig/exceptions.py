class Error(Exception):
    """A general error."""


class InvalidSchemaError(Error):
    """An error while validating an dictconfig schema."""

    def __init__(self, reason, keypath):
        self.reason = reason
        self.keypath = keypath

    def __str__(self):
        dotted = ".".join(self.keypath)
        return f"Invalid schema at keypath: \"{dotted}\". {self.reason}"


class ResolutionError(Error):
    """An error while resolving an dictconfig."""

    def __init__(self, reason, keypath):
        self.reason = reason
        self.keypath = keypath

    def __str__(self):
        return f"Cannot resolve keypath: {self.keypath}: {self.reason}"


class ParseError(ResolutionError):
    """Could not parse the configuration value."""
