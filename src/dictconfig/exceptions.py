class Error(Exception):
    """A general error."""


class InvalidSchemaError(Error):
    """An error while validating an dictconfig schema."""

    def __init__(self, reason, keypath):
        self.reason = reason
        self.keypath = keypath

    def __str__(self):
        dotted = _join_dotted(self.keypath)
        return f'Invalid schema at keypath: "{dotted}". {self.reason}'


class ResolutionError(Error):
    """An error while resolving an dictconfig."""

    def __init__(self, reason, keypath):
        self.reason = reason
        self.keypath = keypath

    def __str__(self):
        dotted = _join_dotted(self.keypath)
        return f'Cannot resolve keypath: "{dotted}": {self.reason}'


class ParseError(Error):
    """Could not parse the configuration value."""


def _join_dotted(keypath):
    return ".".join(str(x) for x in keypath)
