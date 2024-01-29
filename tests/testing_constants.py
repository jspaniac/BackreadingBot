import os

from src.database import GuildInfo

TESTING_DATABASE = os.path.join(os.getcwd(), 'tests', 'store', 'testing-db.json')
STANDARD_GUILD_ID = "0"
STANDARD_GUILD = GuildInfo.create("a", "b", "c", "d", "e", False)
STANDARD_GUILD_SAVED = {
    STANDARD_GUILD_ID: STANDARD_GUILD
}
