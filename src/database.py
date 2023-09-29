import logging
import json
from constants import (
    LOGGING_FILE, DB_FILE
)
from exceptions import (
    GuildNotFound, DBFileNotFound
)

logging.basicConfig(filename=LOGGING_FILE, encoding='utf-8', level=logging.INFO)

class Database:
    def __init__(self, file_path=DB_FILE):
        logging.info(f"Loading DB from file: {file_path}")
        try:
            self.guild_to_info = json.load(open(file_path))
        except:
            raise DBFileNotFound

    def __contains__(self, guild_id):
        return str(guild_id) in self.guild_to_info
    
    def guild_ids(self):
        return self.guild_to_info.keys()

    def _get(self, guild_id):
        if guild_id not in self.guild_to_info:
            raise GuildNotFound
        return self.guild_to_info.get(str(guild_id))

    def get_admin(self, guild_id):
        return self._get(guild_id)['admin']
    
    def get_channel(self, guild_id):
        return self._get(guild_id)['channel']
    
    def get_token(self, guild_id):
        return self._get(guild_id)['token']
    
    def get_course(self, guild_id):
        return self._get(guild_id)['course']
    
    def get_role(self, guild_id):
        return self._get(guild_id)['role']

    def get_approval(self, guild_id):
        return self._get(guild_id)['approval']
    
    def get_threads(self, guild_id):
        return self._get(guild_id)['threads']

    def register(self, guild_id, guild_info):
        self.guild_to_info[str(guild_id)] = guild_info
    
    def delete(self, guild_id):
        del self.guild_to_info[str(guild_id)]
        self.save()

    def remove_thread(self, guild_id, thread_id):
        self.get_threads(guild_id).pop(thread_id)
        self.save()
    
    def add_thread(self, guild_id, ed_id, discord_thread_id):
        self.get_threads(guild_id)[str(ed_id)] = int(discord_thread_id)
        self.save()
    
    def save(self):
        with open(DB_FILE, "w") as db:
            db.write(json.dumps(self.guild_to_info))