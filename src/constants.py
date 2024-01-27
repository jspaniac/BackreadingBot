import os

# Various files and directories
STORAGE_DIR = os.path.join(os.getcwd(), 'store')
TEMP_DIR = os.path.join(os.getcwd(), 'temp')
LOGGING_FILE = os.path.join(STORAGE_DIR, 'logging', 'base.log')
DB_FILE = os.path.join(STORAGE_DIR, 'database.json')
AUTH_FILE = os.path.join(STORAGE_DIR, 'auth.json')

TIMEOUT = 45.0
REFRESH_DELAY = 5
PULL_DELAY = 5

# Viewable Ed link
SUBMISSION_LINK = "https://edstem.org/us/courses/{course_id}/lessons/{lesson_id}/attempts?slide={slide_id}&email={email}"
THREAD_LINK = 'https://edstem.org/us/courses/{course_id}/discussion/{thread_id}'

# Misc symbols
GREEN_CHECK = "\U00002705"
RED_X = "\U0000274c"
EMPTY_SQUARE = "□"
FULL_SQUARE = "■"

# Progress bar constants
BAR_SIZE = 40
PROGRESS_UPDATE_MULTIPLE = 50

# What the assignment due time grace period is
ASSIGNMENT_GRACE_MINUTES = 15

# Turns out discord has a max number of embed fields...
DISCORD_MAX_EMBED_FIELDS = 25