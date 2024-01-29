import logging
import json
from typing import (
    Optional, Union, Set, Dict
)

from src.constants import (
    LOGGING_FILE, DB_FILE
)
from src.exceptions import (
    GuildNotFound, DBFileNotFound
)

logging.basicConfig(filename=LOGGING_FILE, encoding='utf-8', level=logging.INFO)

class Database:
    """
    Represents a database which stores a variety of information about a specific guild
    necessary for the bots use
    """

    def __init__(self, file_path: Optional[str]=DB_FILE):
        """
        Constructs a new database instance from the given file. If the file cannot be found,
        raises the DBFileNotFound exception

        Params: 'file_path' - Path to the file containins guild information to load
        """
        logging.info(f"Loading DB from file: {file_path}")
        try:
            self.guild_to_info = json.load(open(file_path))
            self.db_file = file_path
        except:
            raise DBFileNotFound("Database file cannot be found, unable to create/load database")

    def __contains__(self, guild_id: Union[str, int]) -> bool:
        """
        Params: 'guild_id' - The guild ID to check
        Returns: Whether or not the given guild ID is present
        """
        return str(guild_id) in self.guild_to_info
    
    def guild_ids(self) -> Set[str]:
        """
        Returns: A set of all guild IDs present within the database
        """
        return self.guild_to_info.keys()

    def _get(self, guild_id: Union[int, str]) -> Dict:
        """
        Helper method that returns the guild info for a given guild_id. Note that the id can be
        an int or str
        """
        if str(guild_id) not in self.guild_to_info:
            raise GuildNotFound(f"Guild ID {guild_id} not present in the database")
        return self.guild_to_info.get(str(guild_id))

    def get_admin(self, guild_id: Union[int, str]) -> str:
        """
        Params: 'guild_id' - The guild ID to get info for
        Returns: The discord user ID for the guild's admin (the user that initialized the bot)
        """
        return self._get(guild_id)['admin']
    
    def get_channel(self, guild_id: Union[int, str]) -> int:
        """
        Params: 'guild_id' - The guild ID to get info for
        Returns: The discord channel ID for the backread request channel
        """
        return self._get(guild_id)['channel']
    
    def get_token(self, guild_id: Union[int, str]) -> str:
        """
        Params: 'guild_id' - The guild ID to get info for
        Returns: The Ed API token for the admin user within the guild
        """
        return self._get(guild_id)['token']
    
    def get_course(self, guild_id: Union[int, str]) -> str:
        """
        Params: 'guild_id' - The guild ID to get info for
        Returns: The URL for the Ed staff board that contains backread requests
        """
        return self._get(guild_id)['course']
    
    def get_role(self, guild_id: Union[int, str]) -> int:
        """
        Params: 'guild_id' - The guild ID to get info for
        Returns: The discord role ID that will be pinged when a backreading thread is created
        """
        return self._get(guild_id)['role']

    def get_approval(self, guild_id: Union[int, str]) -> bool:
        """
        Params: 'guild_id' - The guild ID to get info for
        Returns: Whether or not approval is required before pushing repsonses to Ed
        """
        return self._get(guild_id)['approval']
    
    def get_threads(self, guild_id: Union[int, str]) -> Set[int]:
        """
        Params: 'guild_id' - The guild ID to get info for
        Returns: A set of all Ed thread IDs that have already been imported into discord
        """
        return self._get(guild_id)['threads']

    def register(self, guild_id: Union[int, str], guild_info: Dict) -> None:
        """
        Registers a guild with the necessary information required for the bot
        
        Params: 'guild_id' - The guild ID to import
                'guild_info' - The necessary guild information. Should be the result of GuildInfo.create
        """
        self.guild_to_info[str(guild_id)] = guild_info
        self.save()
    
    def delete(self, guild_id: Union[int, str]) -> None:
        """
        Removes all guild information for a registered with the bot
        
        Params: 'guild_id' - The guild ID to delete
        """
        del self.guild_to_info[str(guild_id)]
        self.save()

    def remove_thread(self, guild_id: Union[int, str], ed_id: Union[int, str]) -> None:
        """
        Removes a thread from the set of imported threads within the database
        
        Params: 'guild_id' - The guild ID
                'ed_id' - The Ed thread ID to delete
        """
        self.get_threads(guild_id).pop(str(ed_id))
        self.save()
    
    def add_thread(self, guild_id: Union[int, str], ed_id: Union[int, str], discord_id: Union[int, str]) -> None:
        """
        Adds a thread from the set of imported threads within the database
        
        Params: 'guild_id' - The guild ID
                'ed_id' - The Ed thread ID to add
                'discord_id' - The discord thread ID to add
        """
        self.get_threads(guild_id)[str(ed_id)] = int(discord_id)
        self.save()
    
    def save(self) -> None:
        """
        Saves current information to the file the database was created with. If the file
        cannot be found, raises the DBFileNotFound exception
        """
        try:
            open(self.db_file, "w").write(json.dumps(self.guild_to_info))
        except:
            raise DBFileNotFound("Original database file can't be found, unable to save")

class GuildInfo:
    @staticmethod
    def create(admin: str, channel: str, token: str, course: str, role: str, approval: bool) -> Dict:
        return {
            'admin': admin,
            'channel': channel,
            'token': token,
            'course': course,
            'role': role,
            'approval': approval,
            'threads': {}
        }