import logging
import re
import requests
import datetime

from constants import (
    LOGGING_FILE, THREAD_LIMIT
)
from exceptions import (
    InvalidResponse
)

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
    THREAD_LIMIT = 40

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
    """
    Represents an interface with the Ed API that allows users to carry out various requests
    """
    def __init__(self, token):
        """
        Constructs a new ed helper instance from the given API token.
        
        Params: 'token' - The Ed API token to use with requests
        """
        self.token = token
    
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
        """
        Params: 'course_id' - The ID of the Ed course to get threads for
        Returns: A list of Ed thread objects for the course
        """
        payload = {'limit': EdConstants.THREAD_LIMIT, 'sort': 'new'}
        return get_response(EdConstants.THREAD_REQUEST.format(id=course_id), self.token, payload)['threads']
    
    def get_slide(self, url):
        """
        Params: 'url' - The url of the of the slide to get
        Returns: An Ed slide object
        """
        payload = {'view': 1}
        return get_response(EdConstants.SLIDE_REQUEST.format(slide_id=EdHelper.get_ids(url)[2]), self.token, payload)['slide']
    
    def get_challenge_users(self, challenge_id):
        """
        Params: 'challenge_id' - The ID of the Ed challenge to get users for
        Returns: A list of Ed user objects for the challenge
        """
        return get_response(EdConstants.CHALLENGE_USER_REQUEST.format(challenge_id=challenge_id), self.token)['users']
    
    def get_challenge(self, challenge_id):
        """
        Params: 'challenge_id' - The ID of the Ed challenge to get information for
        Returns: An Ed challenge object corresponding to the given ID
        """
        return get_response(EdConstants.BASE_CHALLENGE.format(challenge_id=challenge_id), self.token)['challenge']
    
    def get_challenge_submissions(self, user_id, challenge_id):
        """
        Params: 'user_id' - The ID of the Ed user to get submissions for
                'challenge_id' - The ID of the ed challenge
        Returns: A list of Ed submission objects for the challenge
        """
        get_response(EdConstants.CHALLENGE_SUBMISSIONS.format(user_id=user_id, challenge_id=challenge_id), self.token)['submissions']

    @staticmethod
    def get_ids(url):
        """
        Returns a list of all numeric IDs found within the given url
        """
        return re.findall(EdRegex.NUM_PATTERN, url)
    
    @staticmethod
    def parse_datetime(time, milliseconds=True):
        """
        Returns an appropriately formatted datetime object for the given Ed datetime formatting.
        'milliseconds' is whether or not the given time contains milliseconds
        """
        splitted = time.rsplit(':', 1)
        datetime_format = EdConstants.DATETIME_FORMAT.replace('.', '') if milliseconds else EdConstants.DATETIME_FORMAT
        return datetime.datetime.strptime(
            splitted[0] + splitted[1], datetime_format)

    @staticmethod
    async def valid_course_for_user(url, user):
        """
        Returns if the course represented by the given url is present with the Ed user object's courses
        """
        if EdRegex.COURSE_PATTERN.fullmatch(url):
            course_id = int(EdHelper.get_ids(url)[0])
            for course in user['courses']:
                course = course['course']
                if course['id'] == course_id:
                    return course
        raise InvalidResponse
    
    @staticmethod
    def valid_assignment_url(url):
        """
        Returns if the given url is formatted like a valid Ed assignment url
        """
        return EdRegex.ASSIGNMENT_PATTERN.fullmatch(url)
    
    @staticmethod
    def parse_content(content):
        """
        Removes a variety of junk escape characters found within an ed content box
        """
        return re.sub(EdRegex.CONTENT_JUNK_REGEX, ' ', content)

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