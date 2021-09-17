class Error(Exception):
    """A general error."""


class SchemaError(Error):
    """An error while validating an dictconfig schema."""


class ResolutionError(Error):
    """An error while resolving an dictconfig."""


class MissingKeyError(ResolutionError):
    """A required key is missing."""

    def __init__(self, path):
        self.path = path

    def __str__(self):
        dotted = ".".join(self.path)
        return f'Missing key at path: "{dotted}".'


class ExtraKeyError(ResolutionError):
    """An unexpected extra key has been provided."""


class ParseError(ResolutionError):
    """Could not parse the configuration value."""
