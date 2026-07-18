"""Expected operational errors surfaced by the Autumn CLI."""


class AutumnError(Exception):
    """Base class for failures that should be shown without a traceback."""


class ConfigError(AutumnError):
    """Configuration could not be read, validated, or saved."""


class ReminderError(AutumnError):
    """A background reminder could not be validated or started."""
