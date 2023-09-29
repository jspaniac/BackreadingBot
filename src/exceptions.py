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