class TimeoutError(Exception):
    """
    A timeout exception for repeat request handling
    """
    pass


class InvalidResponse(Exception):
    """
    An exception for when users provide invalid responses to requests
    """
    pass


class DBFileNotFound(Exception):
    """
    An exception for when the database file for the bot cannot be found
    """
    pass


class GuildNotFound(Exception):
    """
    An exception for when the guild doesn't exist within the bot database
    """
    pass


class InvalidEdToken(Exception):
    """
    An exception for when the provided Ed API token isn't valid
    """
    pass


class MissingArgument(Exception):
    """
    An exception for when the client hasn't provided an argument when running
    commands locally
    """
    pass


class InvalidArgument(Exception):
    """
    An exception for when the client has provided a bad argument that isn't
    valid when running commands locally
    """
    pass
