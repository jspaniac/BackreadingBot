import logging
import re
import requests
import datetime

from typing import (
    Optional, List, Dict, Union, Any
)
from constants import (
    LOGGING_FILE
)
from exceptions import (
    InvalidResponse, InvalidEdToken
)

DEBUG = False
logging.basicConfig(filename=LOGGING_FILE, encoding='utf-8',
                    level=logging.INFO)


class EdConstants:
    USER_REQUEST = 'https://us.edstem.org/api/user'  # noqa: E501
    SLIDE_REQUEST = 'https://us.edstem.org/api/lessons/slides/{slide_id}'  # noqa: E501
    THREAD_REQUEST = 'https://us.edstem.org/api/courses/{id}/threads'  # noqa: E501

    BASE_CHALLENGE = 'https://us.edstem.org/api/challenges/{challenge_id}'  # noqa: E501
    CHALLENGE_USER_REQUEST = 'https://us.edstem.org/api/challenges/{challenge_id}/users'  # noqa: E501
    CHALLENGE_SUBMISSIONS = 'https://us.edstem.org/api/users/{user_id}/challenges/{challenge_id}/submissions'  # noqa: E501

    ED_ATTEMPT_RESULTS_REQUEST = "https://us.edstem.org/api/lessons/{lesson_id}/results?students=1&strategy=latest&observers=0"  # noqa: E501
    ED_LESSON_REQUEST = "https://us.edstem.org/api/lessons/{lesson_id}?view=1"  # noqa: E501
    ED_RUBRIC_REQUEST = "https://us.edstem.org/api/rubrics/{rubric_id}"  # noqa: E501
    ED_QUESTION_REQUEST = "https://us.edstem.org/api/lessons/slides/{slide_id}/questions"  # noqa: E501
    ED_ATTTEMPT_REQUEST = "https://us.edstem.org/api/lessons/{lesson_id}/attempts/{user_id}"  # noqa: E501
    ED_MARK_REQUEST = "https://us.edstem.org/api/lesson_marks/{mark_id}?rubric_items=true"  # noqa: E501
    ED_QUIZ_REQUEST = "https://us.edstem.org/api/attempts/{lesson_attempt_id}/quiz_responses/{slide_id}"  # noqa: E501

    POST_REQUEST = 'https://us.edstem.org/api/threads/{thread_id}/comments'  # noqa: E501
    ACCEPT_REQUEST = 'https://us.edstem.org/api/comments/{comment_id}/accept'  # noqa: E501

    DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"  # noqa: E501
    THREAD_LIMIT = 40

    CRITERIA_MAP = {
        "Exemplary": "E", "Excellent": "E",
        "Satisfactory": "S",
        "Not yet": "N", "Not Yet": "N",
        "Unassessable": "U"
    }


class EdRegex:
    NUM_PATTERN = re.compile(r'[0-9]+')  # noqa: E501
    COURSE_PATTERN = re.compile(r'https://edstem.org/us/courses/[0-9]+/discussion/')  # noqa: E501
    ASSIGNMENT_PATTERN = re.compile(r'https://edstem.org/us/courses/[0-9]+/lessons/[0-9]+/slides/[0-9]+')  # noqa: E501
    ATTEMPT_PATTERN = re.compile(r'https://edstem.org/us/courses/[0-9]+/lessons/[0-9]+/attempts\?(email=[A-Za-z0-9]+(@|%40)uw.edu&)?slide=[0-9]+')  # noqa: E501
    CONTENT_JUNK_REGEX = re.compile(r'\u003c[^\u003c\u003e]*\u003e')  # noqa: E501
    REMOVE_HTML_REGEX = re.compile('<.*?>')  # noqa: E501
    EMAIL_REGEX = re.compile(r'[A-Za-z0-9]+(@|%40)(uw|cs.washington).edu')  # noqa: E501


class EdHelper:
    """
    Represents an interface with the Ed API that allows users to carry out
    various requests
    """

    def __init__(
        self,
        token: str,
        retries: Optional[int] = 5
    ):
        """
        Constructs a new ed helper instance from the given API token. If the
        given token is invalid, raises InvalidEdToken

        Params: 'token' - The Ed API token to use with requests
        """
        try:
            EdHelper.valid_token(token)
            self.token = token
            self.retries = retries
        except InvalidResponse:
            raise InvalidEdToken

    def push_answer(
        self,
        thread_id: str,
        answer: str
    ) -> None:
        """
        Pushes an answer to the given Ed thread

        Params: 'thread_id' - ID of the Ed thread to push a response to
                'answer' - The answer to be pushed
        """
        logging.info(f"Pushing answer to {thread_id}")
        payload = {'comment': {
            'type': 'answer',
            'content': f"<document version=\"2.0\"><paragraph>{answer}" +
                       "</paragraph></document>",
            'is_private': False,
            'is_anonymous': False
        }}
        response = post_payload(EdConstants.POST_REQUEST.format(
            thread_id=thread_id), self.token, self.retries, payload
        )
        logging.info(response)
        # Don't wrap since ed doesn't give a response for accepting an answer

        requests.post(EdConstants.ACCEPT_REQUEST.format(
            comment_id=response['comment']['id']),
            headers={'x-token': self.token}
        )

    def valid_course(
        self,
        url: str
    ) -> bool:
        """
        Returns if the course represented by the given url is valid for the
        initial auth token
        """
        courses = EdHelper.valid_token(self.token)['courses']
        if EdRegex.COURSE_PATTERN.fullmatch(url):
            course_id = int(EdHelper.get_ids(url)[0])
            for course in courses:
                if course['course']['id'] == course_id:
                    return course['course']
        raise InvalidResponse

    def get_threads(
        self,
        course_id: int
    ) -> List[Dict]:
        """
        Params: 'course_id' - The ID of the Ed course to get threads for
        Returns: A list of Ed thread objects for the course
        """
        payload = {'limit': EdConstants.THREAD_LIMIT, 'sort': 'new'}
        return get_response(EdConstants.THREAD_REQUEST.format(id=course_id),
                            self.token, self.retries, payload)['threads']

    def get_slide(
        self,
        url: str
    ) -> Dict:
        """
        Params: 'url' - The url of the of the slide to get
        Returns: An Ed slide object
        """
        payload = {'view': 1}
        return get_response(EdConstants.SLIDE_REQUEST.format(
            slide_id=EdHelper.get_ids(url)[2]
        ), self.token, self.retries, payload)['slide']

    def get_challenge_users(
        self,
        challenge_id: int
    ) -> List[Dict]:
        """
        Params: 'challenge_id' - The ID of the Ed challenge to get users for
        Returns: A list of Ed user objects for the challenge
        """
        return get_response(EdConstants.CHALLENGE_USER_REQUEST.format(
            challenge_id=challenge_id
        ), self.token, self.retries)['users']

    def get_challenge(
        self,
        challenge_id: int
    ) -> Dict:
        """
        Params: 'challenge_id' - The ID of the Ed challenge to get
                                 information for
        Returns: An Ed challenge object corresponding to the given ID
        """
        return get_response(EdConstants.BASE_CHALLENGE.format(
            challenge_id=challenge_id
        ), self.token, self.retries)['challenge']

    def get_challenge_submissions(
        self,
        user_id: int,
        challenge_id: int
    ) -> List[Dict]:
        """
        Params: 'user_id' - The ID of the Ed user to get submissions for
                'challenge_id' - The ID of the ed challenge
        Returns: A list of Ed submission objects for the challenge
        """
        return get_response(EdConstants.CHALLENGE_SUBMISSIONS.format(
            user_id=user_id, challenge_id=challenge_id
        ), self.token, self.retries)['submissions']

    def get_attempt_results(
        self,
        lesson_id: int
    ) -> List[Dict]:
        """
        Params: 'lesson_id' - The ID of the Ed lesson to get the attempt
                              results for
        Returns: A list of Ed result objects for the lesson
        """
        return get_response(EdConstants.ED_ATTEMPT_RESULTS_REQUEST.format(
            lesson_id=lesson_id
        ), self.token, self.retries)

    def get_lesson(
        self,
        lesson_id: int
    ) -> Dict:
        """
        Params 'lesson_id' - The ID of the Ed lesson to get the attempt
                             results for
        Returns: An Ed lesson object matching the given id
        """
        return get_response(EdConstants.ED_LESSON_REQUEST.format(
            lesson_id=lesson_id
        ), self.token, self.retries)['lesson']

    def get_rubric(
        self,
        rubric_id: int
    ) -> Dict:
        """
        Params 'rubric_id' - The ID of the rubric to get
        Returns: An Ed rubric object matching the given ID
        """
        return get_response(EdConstants.ED_RUBRIC_REQUEST.format(
            rubric_id=rubric_id
        ), self.token, self.retries)['rubric']

    def get_rubric_id(
        self,
        slide_id: int
    ) -> Dict:
        """
        Params 'slide_id' - The ID of the quiz slide to get the rubric of
        Returns: The rubric ID for this quiz slide
        """
        return get_response(EdConstants.ED_QUESTION_REQUEST.format(
            slide_id=slide_id
        ), self.token, self.retries)['questions'][0]['rubric_id']

    def get_attempt_mark(
        self,
        mark_id: int
    ) -> Dict:
        """
        Params 'mark_id' - The ID of the _____
        Returns: The Ed mark object matching the given ID
        """
        return get_response(EdConstants.ED_MARK_REQUEST.format(
            mark_id=mark_id
        ), self.token, self.retries)

    def get_quiz_responses(
        self,
        attempt_id: int,
        slide_id: int
    ) -> List[Dict]:
        """
        Params: 'attempt_id' - The ID of the attempt to get response for
                'slide_id' - The ID of the quiz slide with responses
        Returns: The responses for the quiz on the given slide and on the
                 attempt matching the given id. Includes selected rubric
                 options
        """
        return get_response(EdConstants.ED_QUIZ_REQUEST.format(
            lesson_attempt_id=attempt_id, slide_id=slide_id
        ), self.token, self.retries)['responses']

    def get_attempt_submissions(
        self,
        user_id: int,
        lesson_id: int,
        slide_id: int,
        submission_id: int,
        rubric: Dict
    ) -> List[Dict]:
        """
        Converts Ed attempt feedback information into the previous challenge
        format

        Params: 'user_id' - The ID of the user to get submission information
                            for
                'lesson_id' - The ID of the lesson to check
                'slide_id' - The ID of the slide containing feedback
                'submission_id' - The ID of the specific submission to check
                                  feedback of
                'rubric' - The rubric for the slide to be joined on
        Returns: A dict containing relevant submission feedback information
                 for the user
        """
        attempt_response = get_response(EdConstants.ED_ATTTEMPT_REQUEST.format(
            lesson_id=lesson_id, user_id=user_id
        ), self.token, self.retries)
        if "final_id" not in attempt_response:
            return None
        final_id = attempt_response['final_id']

        final_submission_time = None
        for attempt in attempt_response['attempts']:
            if attempt['id'] == final_id:
                final_submission_time = attempt['submitted_at']
                break

        # TODO: Have some notion of handling a too late final submission mark
        if final_submission_time is None:
            # No final submission submitted
            return None

        all_criteria = []
        ed_quiz_responses = self.get_quiz_responses(final_id, slide_id)
        mark = self.get_attempt_mark(ed_quiz_responses[0]['lesson_mark']['id'])

        selected_rubric_items = (mark['selected_rubric_items']
                                 if 'selected_rubric_items' in mark else
                                 [])
        for section in rubric['sections']:
            section_title = section['title']
            for item in section['items']:
                if item['id'] in selected_rubric_items:
                    item_title = EdHelper.remove_html(item['title'])
                    all_criteria.append({
                        'name': section_title,
                        'mark': EdConstants.CRITERIA_MAP.get(item_title,
                                                             item_title)
                    })

        feedback_comment = ed_quiz_responses[0]['lesson_mark']['comment']
        parsed_feedback_comment = EdHelper.remove_html(
            "" if feedback_comment is None else feedback_comment
        )

        return [{
            'id': submission_id,
            'created_at': final_submission_time,
            'feedback': {
                'criteria': all_criteria,
                'content': parsed_feedback_comment
            }
        }]

    def get_attempt_user(
        self,
        user: Dict,
        lesson_id: int,
        slide_id: int,
        rubric: Dict
    ) -> Dict:
        """
        Converts Ed attempt feedback completion information into the previous
        challenge format

        Params: 'user' - An Ed attempt user object
                'lesson_id' - The ID of the lesson to check
                'slide_id' - The ID of the slide containing feedback
                'rubric' - The rubric for the slide to be joined on
        Returns: A dict containing relevant submission information for the user
        """
        ret = {
            'id': user['user_id'],
            'tutorial': user['tutorial'],
            'completed': False,
            'feedback_status': 'incomplete'
        }

        attempt_response = get_response(EdConstants.ED_ATTTEMPT_REQUEST.format(
            lesson_id=lesson_id, user_id=user['user_id']
        ), self.token, self.retries)
        if "final_id" not in attempt_response:
            return ret
        final_id = attempt_response['final_id']

        ret['completed'] = True
        rubric = self.get_rubric(self.get_rubric_id(slide_id))

        ed_quiz_responses = self.get_quiz_responses(final_id, slide_id)
        mark = self.get_attempt_mark(ed_quiz_responses[0]['lesson_mark']['id'])
        selected_rubric_items = (mark['selected_rubric_items']
                                 if 'selected_rubric_items' in mark else
                                 [])

        if len(selected_rubric_items) == len(rubric['sections']):
            ret['feedback_status'] = 'complete'

        return ret

    @staticmethod
    def get_ids(
        url: str
    ) -> List[int]:
        """
        Returns a list of all numeric IDs found within the given url
        """
        url = EdRegex.EMAIL_REGEX.sub('', url)
        return re.findall(EdRegex.NUM_PATTERN, url)

    @staticmethod
    def parse_datetime(
        time: str,
        milliseconds: Optional[bool] = True
    ) -> datetime.datetime:
        """
        Returns an appropriately formatted datetime object for the given Ed
        datetime formatting. 'milliseconds' is whether or not the given time
        contains milliseconds
        """
        splitted = time.rsplit(':', 1)
        datetime_format = (EdConstants.DATETIME_FORMAT.replace('.', '')
                           if not milliseconds else
                           EdConstants.DATETIME_FORMAT)
        return datetime.datetime.strptime(
            splitted[0] + splitted[1], datetime_format)

    @staticmethod
    def valid_token(
        token: str,
        retries: Optional[int] = 5
    ) -> Dict:
        """
        If the given token is valid, returns the corresponding ed user object.
        Otherwise raises InvalidResponse
        """
        try:
            return get_response(EdConstants.USER_REQUEST, token, retries)
        except Exception:
            raise InvalidResponse("Invalid Ed token")

    @staticmethod
    def valid_assignment_url(url: str) -> bool:
        """
        Returns if the given url is formatted like a valid Ed assignment url
        """
        return (EdRegex.ASSIGNMENT_PATTERN.fullmatch(url) or
                EdRegex.ATTEMPT_PATTERN.fullmatch(url))

    @staticmethod
    def parse_content(content: str) -> str:
        """
        Removes a variety of junk escape characters found within an
        Ed contentbox
        """
        return re.sub(EdRegex.CONTENT_JUNK_REGEX, ' ', content)

    @staticmethod
    def remove_html(content: str) -> str:
        """
        Removes the html from a given content box
        """
        return re.sub(EdRegex.REMOVE_HTML_REGEX, '', content)

    @staticmethod
    def is_overall_submission_link(url: str) -> bool:
        """
        Returns whether or not a url is for an overall submission on a lesson
        """
        # TODO: Better way?
        return "attempts" in url

    @staticmethod
    def convert_sid(sid: str) -> str:
        """
        Stopgap for Ed bug, parses the sid as an int if it starts with an int,
        otherwise a string
        """
        if sid[0].isdigit():
            return str(int(re.search(r'\d+', sid).group()))
        return sid


def get_response(
    url: str,
    token: str,
    retries: int,
    payload: Optional[Dict] = {}
) -> Union[Any, None]:
    """
    Makes a GET request to the given 'url' endpoint using the authorization
    bearer 'token' and url params 'payload'
    """
    for i in range(retries):
        try:
            response = requests.get(url=url, params=payload, headers={
                'Authorization': 'Bearer ' + token
            })
            if DEBUG:
                print(response.json())
            if response.ok:
                logging.debug(f"GET response for {url}: {response}")
                return response.json()
        except requests.exceptions.ConnectionError:
            logging.debug(f"GET Attempt {i}/{retries} failed, retrying")
    return None


def post_payload(
    url: str,
    token: str,
    retries: int,
    payload: Optional[Dict] = {}
) -> Union[Any, None]:
    """
    Makes a POST request to the given 'url' endpoint using the authorization
    bearer 'token' and form params 'payload'
    """
    for i in range(retries):
        try:
            response = requests.post(url=url, json=payload, headers={
                'Authorization': 'Bearer ' + token
            })
            if DEBUG:
                print(response.json())
            if response.ok:
                logging.debug(f"POST Response for {url}: {response}")
                return response.json()
        except requests.exceptions.ConnectionError:
            logging.debug(f"GET Attempt {i}/{retries} failed, retrying")
    return None
