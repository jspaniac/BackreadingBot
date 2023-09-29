import logging
import re
import requests
import datetime
from constants import (
    LOGGING_FILE, THREAD_LIMIT
)

from exceptions import InvalidResponse

logging.basicConfig(filename=LOGGING_FILE, encoding='utf-8', level=logging.INFO)

class EdConstants:
    USER_REQUEST = 'https://us.edstem.org/api/user'
    SLIDE_REQUEST = 'https://us.edstem.org/api/lessons/slides/{slide_id}'
    THREAD_REQUEST = 'https://us.edstem.org/api/courses/{id}/threads'

    BASE_CHALLENGE = 'https://us.edstem.org/api/challenges/{challenge_id}'
    CHALLENGE_USER_REQUEST = 'https://us.edstem.org/api/challenges/{challenge_id}/users'
    CHALLENGE_SUBMISSIONS = 'https://us.edstem.org/api/users/{user_id}/challenges/{challenge_id}/submissions'

    POST_REQUEST = 'https://us.edstem.org/api/threads/{thread_id}/comments'
    ACCEPT_REQUEST = 'https://us.edstem.org/api/comments/{comment_id}/accept'

    DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"

class EdRegex:
    NUM_PATTERN = re.compile(
        r'[0-9]+')
    COURSE_PATTERN = re.compile(
        r'https://edstem.org/us/courses/[0-9]+/discussion/')
    ASSIGNMENT_PATTERN = re.compile(
        r'https://edstem.org/us/courses/[0-9]+/lessons/[0-9]+/slides/[0-9]+')
    CONTENT_JUNK_REGEX = ed_junk_regex = re.compile(
        r'\u003c[^\u003c\u003e]*\u003e')

class EdHelper:

    def __init__(self, token):
        self.token = token

    @staticmethod
    def get_ids(url):
        return re.findall(EdRegex.NUM_PATTERN, url)
    
    @staticmethod
    def parse_datetime(time, milliseconds=True):
        splitted = time.rsplit(':', 1)
        datetime_format = EdConstants.DATETIME_FORMAT.replace('.', '') if milliseconds else EdConstants.DATETIME_FORMAT
        return datetime.datetime.strptime(
            splitted[0] + splitted[1], datetime_format)

    @staticmethod
    async def valid_course_for_user(url, user):
        if EdRegex.COURSE_PATTERN.fullmatch(url):
            course_id = int(EdHelper.get_ids(url)[0])
            for course in user['courses']:
                course = course['course']
                if course['id'] == course_id:
                    return course
        raise InvalidResponse
    
    @staticmethod
    def valid_assignment_url(url):
        return EdRegex.ASSIGNMENT_PATTERN.fullmatch(url)
    
    @staticmethod
    def parse_content(content):
        return re.sub(EdRegex.CONTENT_JUNK_REGEX, ' ', content)

    def push_answer(self, ed_url, answer):
        """
        """
        thread_id = EdHelper.get_course_thread_ids(ed_url)[1]
        logging.info(f"Pusing answer to {thread_id}")
        payload = {
            'comment': {'type': 'answer',
            'content': f"<document version=\"2.0\"><paragraph>{answer}</paragraph></document>",
            'is_private': False,
            'is_anonymous': False}
        }
        response = post_payload(EdConstants.POST_REQUEST.format(thread_id=thread_id), self.token, payload)

        # Don't wrap since ed doesn't give a response for accepting an answer
        requests.post(EdConstants.ACCEPT_REQUEST.format(comment_id=response['comment']['id']), headers={'x-token': self.token})
    
    def get_threads(self, course_id):
        payload = {'limit': THREAD_LIMIT, 'sort': 'new'}
        return get_response(EdConstants.THREAD_REQUEST.format(id=course_id), self.token, payload)['threads']
    
    def get_slide(self, url):
        payload = {'view': 1}
        return get_response(EdConstants.SLIDE_REQUEST.format(slide_id=EdHelper.get_ids(url)[2]), self.token, payload)['slide']
    
    def get_challenge_users(self, challenge_id):
        return get_response(EdConstants.CHALLENGE_USER_REQUEST.format(challenge_id=challenge_id), self.token)['users']
    
    def get_challenge(self, challenge_id):
        return get_response(EdConstants.BASE_CHALLENGE.format(challenge_id=challenge_id), self.token)['challenge']
    
    def get_challenge_submissions(self, user_id, challenge_id):
        get_response(EdConstants.CHALLENGE_SUBMISSIONS.format(user_id=user_id, challenge_id=challenge_id), self.token)['submissions']

def get_response(url, token, payload={}):
    """
    Makes a GET request to the given 'url' endpoint using the authorization bearer 'token' and url params 'payload'
    """
    return requests.get(url=url, params=payload, headers={'Authorization': 'Bearer ' + token}).json()

def post_payload(url, token, payload={}):
    """
    Makes a POST request to the given 'url' endpoint using the authorization bearer 'token' and form params 'payload'
    """
    return requests.post(url=url, json=payload, headers={'Authorization': 'Bearer ' + token}).json()