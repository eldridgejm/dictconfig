class Error(Exception):
    """A general error."""


class SchemaError(Error):
    """An error while validating an dictconfig schema."""

    def __init__(self, message, path):
        dotted_path = ".".join(path)
        self.message = f'When parsing "{dotted_path}": {message}'
        self.path = path
        super().__init__(self, self.message)


class ResolutionError(Error):
    """An error while resolving an dictconfig."""


class ParseError(ResolutionError):
    """Could not parse the configuration value."""
