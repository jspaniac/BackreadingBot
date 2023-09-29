import os

STORAGE_DIR = '../store'
LOGGING_FILE = os.path.join(STORAGE_DIR, 'logging', 'base.log')
DB_FILE = os.path.join(STORAGE_DIR, 'database.json')
AUTH_FILE = os.path.join(STORAGE_DIR, 'auth.json')

TEMP_DIR = '../temp'

TIMEOUT = 45.
REFRESH_DELAY = 0
THREAD_LIMIT = 40
MESSAGE_DEPTH = 100

THREAD_NAME = "{author}: {title}"
THREAD_LINK = 'https://edstem.org/us/courses/{course_id}/discussion/{thread_id}'

GREEN_CHECK = "\U00002705"
RED_X = "\U0000274c"

EMPTY_SQUARE = "□"
FULL_SQUARE = "■"
BAR_SIZE = 40
PROGRESS_UPDATE_MULTIPLE = 50

ASSIGNMENT_GRACE_MINUTES= 15