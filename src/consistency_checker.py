import os
from collections import defaultdict
import datetime
import re
import logging

from typing import (
    List, Dict, Optional, Callable, Tuple, Union
)
from src.utils import (
    write_csv, convert_csv_to_html
)
from src.constants import (
    TEMP_DIR, PROGRESS_UPDATE_MULTIPLE, ASSIGNMENT_GRACE_MINUTES, LOGGING_FILE
)

from src.ed_helper import EdHelper

logging.basicConfig(filename=LOGGING_FILE, encoding='utf-8',
                    level=logging.INFO)


class ConsistencyConstants:
    FEEDBACK_BOX_REGEX = r'({criteria_name})[a-zA-Z\s]*:\s*_*(\({criteria_mark}\)|{criteria_mark})'  # noqa: E501
    TEMPLATE_REGEX = r'({criteria_name})[a-zA-Z\s\\/]*:'  # noqa: E501
    VIEW_SUBMISSION_LINK = 'https://edstem.org/us/courses/{course_id}/lessons/{lesson_id}/slides/{slide_id}/submissions?u={user_id}&s={submission_id}'  # noqa: E501
    FERPA_VIEW_ATTEMPT_LINK = 'https://edstem.org/us/courses/{course_id}/lessons/{lesson_id}/attempts?slide={slide_id}&s={submission_id}'  # noqa: E501
    VIEW_ATTEMPT_LINK = 'https://edstem.org/us/courses/{course_id}/lessons/{lesson_id}/attempts?slide={slide_id}&email={email}'  # noqa: E501


class ConsistencyRegex:
    EMAIL_REGEX = re.compile(r'[A-Za-z0-9]+(@|%40)(uw|cs.washington).edu')  # noqa: E501


class ConsistencyChecker:
    @staticmethod
    def _count_ungraded(
        users: List[Dict],
        spreadsheet: Dict[str, str]
    ) -> Tuple[Dict[str, int], int, int]:
        """
        Counts the total number users with incomplete feedback in 'users' and
        keeps track of a dictionary mapping either (section | TA) -> total
        ungraded depending on if an attachment_url is provided

        Params: 'users' - A list of Ed user objects for a course
                'spreadsheet' - A dictionary mapping ed user_id -> TA name. If
                                none, section codes will be used instead
        Returns: The aforementioned dictionary, the total number of students
                 not present in the given spreadsheet, and the total number of
                 ungraded students
        """
        key_to_ungraded, not_present = defaultdict(int), 0
        total_ungraded = 0
        for user in users:
            if spreadsheet and str(user['id']) not in spreadsheet:
                # This student isn't present in the grading spreadsheet, skip
                not_present += 1
                continue

            key = (spreadsheet[str(user['id'])] if spreadsheet
                   else user['tutorial'])

            if user['completed'] and user['feedback_status'] != "complete":
                key_to_ungraded[key] += 1
                total_ungraded += 1
        return key_to_ungraded, not_present, total_ungraded

    @staticmethod
    async def check_ungraded(
        ed_helper: EdHelper,
        url: str,
        spreadsheet: Optional[Dict[str, str]] = None,
        progress_bar_update: Optional[Callable[[int, int], None]] = None
    ) -> Tuple[Dict[str, int], int, int]:
        """
        Checks and organizes information regarding ungraded students for a
        given ed assignment

        Params: 'ed_helper' - A properly initialized EdHelper object with API
                              access to the ed assignment
                'url' - The url of the ed assignment to check
                'spreadsheet' - A dictionary mapping ed user_id -> TA name. If
                                none, section codes will be used instead
                'progress_bar_update' - A function to call with incremental
                                        values that updates a user-viewable
                                        progress bar
                'attachment_url' - The url of the attachment sent with the
                                   initial user request (can be None)
        Returns: A dictionary mapping either (section | TA) -> total ungraded
                 depending on if an attachment_url, the total number of
                 students not present in the given spreadsheet, and the total
                 number of ungraded students
        """
        url = ConsistencyRegex.EMAIL_REGEX.sub('', url)
        attempt_slide = EdHelper.is_overall_submission_link(url)

        users = None
        if not attempt_slide:
            slide = ed_helper.get_slide(url)
            users = [user for user
                     in ed_helper.get_challenge_users(slide['challenge_id'])
                     if user['course_role'] == 'student']
        else:
            ids = EdHelper.get_ids(url)
            lesson_id, slide_id = ids[1], ids[2]
            rubric = ed_helper.get_rubric(ed_helper.get_rubric_id(slide_id))
            attempts, users = ed_helper.get_attempt_results(lesson_id), []

            for i in range(len(attempts)):
                if i % PROGRESS_UPDATE_MULTIPLE == 0:
                    if progress_bar_update:
                        await progress_bar_update(i, len(attempts))
                    logging.info(f"{i} / {len(attempts)} Converted")

                users.append(ed_helper.get_attempt_user(attempts[i], lesson_id,
                                                        slide_id, rubric))

        return ConsistencyChecker._count_ungraded(users, spreadsheet)

    @staticmethod
    def _check_criteria(
        all_criteria: List[Dict],
        content: str
    ) -> str:
        """
        Checks to see if the grade in Ed's feedback box matches that assigned
        in the corresponding dropdown menu

        Params: 'all_criteria' - Ed criteria dropdown objects
                'content' - The content within the feedback box
        Returns: A reason for any issue found, "" if no issues
        """
        for criteria in all_criteria:
            if "Reflection" in criteria['name']:
                criteria['name'] = "(Reflection)|(Testing)"
            elif "Concept" in criteria['name']:
                criteria['name'] = "Concepts{0,1}"

            if not re.compile(ConsistencyConstants.FEEDBACK_BOX_REGEX.format(
                criteria_name=criteria['name'], criteria_mark=criteria['mark']
            )).search(content):
                # Feedback not properly templated
                if not re.compile(ConsistencyConstants.TEMPLATE_REGEX.format(
                    criteria_name=criteria['name'])
                ).search(content):
                    if criteria['mark'] != "E":
                        return "Template not used, "
                else:
                    # Template was used, but the mark doesn't match
                    return "Assigned grade doesn't match feedback box, "
        return ""

    @staticmethod
    def _find_submission_fixes(
        submissions: List[Dict],
        num_criteria: int,
        due_at: datetime,
        template: bool
    ) -> Tuple[Union[None, str], Union[None, str]]:
        """
        Parses through a students graded submissions and reports any issues
        found with grading formatting

        Params: 'submissions' - A list of Ed submission objects
                'num_criteria' - The total number of criteria that need to be
                                 filled out
                'due_at' - A datetime object representing the due date of the
                           assignment
                'template' - Whether or not the grading template is expected
        Returns: Any grading fixes that need to be made and the id of the
                 submission. None, None if there are no issues
        """
        grace_period = datetime.timedelta(minutes=ASSIGNMENT_GRACE_MINUTES)
        for submission in submissions:
            created_at = EdHelper.parse_datetime(submission['created_at'],
                                                 milliseconds=True)
            if created_at < due_at + grace_period:
                if submission['feedback'] is None:
                    # Feedback not given to appropriate submission
                    return ("Missing grade / incorrect submission graded or " +
                            "marked final", submission['id'])

                reason = ""
                content = EdHelper.parse_content(
                    submission['feedback']['content']
                )
                if len(submission['feedback']['criteria']) != num_criteria:
                    # Didn't fill out all dimensions
                    reason += "Not all dimensions assigned a grade, "
                if not ConsistencyRegex.EMAIL_REGEX.search(content):
                    # Missing contact info email
                    reason += "Missing TA contact information, "
                if template:
                    # Lets check to see if a template is being used - assuming
                    # the format is "Dimension: Score"
                    reason += ConsistencyChecker._check_criteria(
                        submission['feedback']['criteria'], content
                    )
                if reason != "":
                    return reason[:-2], submission['id']
                break
        return None, None

    @staticmethod
    def _get_link(
        ids: List[int],
        user_id: int,
        email: str,
        submission_id: str,
        attempt_slide: bool,
        ferpa: bool
    ) -> str:
        """
        Creates a properly formatted ed link for a specific student submission

        Params: 'ids' - The course, lesson, and slide id for the assignment to
                        link to
                'user_id' - The Ed user id for the student
                'email' - The Ed account email for ths student
                'submission_id' - The SID value for this specific submission
                'attempt_slide' - Whether or not this is an attempt slide
                'ferpa' - Whether or not to censor the student email from
                          the link
        Returns: A properly formatted Ed assignment URL
        """
        if not attempt_slide:
            return ConsistencyConstants.VIEW_SUBMISSION_LINK.format(
                course_id=ids[0], lesson_id=ids[1], slide_id=ids[2],
                user_id=user_id, submission_id=submission_id
            )
        elif ferpa:
            return ConsistencyConstants.FERPA_VIEW_ATTEMPT_LINK.format(
                course_id=ids[0], lesson_id=ids[1], slide_id=ids[2],
                submission_id=EdHelper.convert_sid(submission_id)
            )
        else:
            return ConsistencyConstants.VIEW_ATTEMPT_LINK.format(
                course_id=ids[0], lesson_id=ids[1], slide_id=ids[2],
                email=email
            )

    @staticmethod
    async def _find_fixes(
        ed_helper: EdHelper,
        url: str,
        template: Optional[bool] = False,
        spreadsheet: Optional[Dict[str, str]] = None,
        progress_bar_update: Optional[Callable[[int, int], None]] = None,
        ferpa: Optional[bool] = True
    ) -> Tuple[Dict[str, List[Tuple[str, str]]], List[str]]:
        """
        Finds all student submissions that have inconsistently formatted
        grading feedback and creates a dictionary containing the fixes that
        need to be made before publishing grades

        Params: 'ed_helper' - A properly initialized EdHelper object with API
                              access to the ed assignment
                'url' - The ed assignment url
                'template' - Whether or not the grading template is expected,
                             default False
                'spreadsheet' - A dictionary mapping ed student ID to TA name,
                                default None
                'progress_bar_update' - A function to call with incremental
                                        values that updates a user-viewable
                                        progress bar, default None
                'ferpa' - Whether or not to censor student emails from links,
                          default True
        Returns: A dictionary mapping (TA | link) -> (link, fixes) for all
                 assignment that had incorrect formatting and a List of links
                 to student assignments not found in the grading spreadsheet
        """
        attempt_slide = EdHelper.is_overall_submission_link(url)

        # Get the challenge id for the assignment
        ids = EdHelper.get_ids(url)
        lesson_id, slide_id = ids[1], ids[2]
        challenge_id = (ed_helper.get_slide(url)['challenge_id']
                        if not attempt_slide else None)

        # Get user/challenge information
        users, due_at, num_criteria, rubric = None, None, None, None
        if not attempt_slide:
            users = [(user['id'], None, user['tutorial'], None)
                     for user in ed_helper.get_challenge_users(challenge_id)
                     if user['course_role'] == "student"]

            challenge = ed_helper.get_challenge(challenge_id)
            due_at = EdHelper.parse_datetime(challenge['due_at'],
                                             milliseconds=False)
            num_criteria = len(challenge['settings']['criteria'])
        else:
            users = [(attempt['user_id'], attempt['email'],
                      attempt['tutorial'], attempt['sourced_id'])
                     for attempt in ed_helper.get_attempt_results(lesson_id)
                     if attempt['course_role'] == 'student']

            lesson = ed_helper.get_lesson(lesson_id)
            due_at = EdHelper.parse_datetime(lesson['due_at'],
                                             milliseconds=False)
            rubric = ed_helper.get_rubric(ed_helper.get_rubric_id(slide_id))
            num_criteria = len(rubric['sections'])

        fixes, not_present, count = defaultdict(list), [], 0
        for (user_id, email, section, submission_id) in users:
            if spreadsheet and str(user_id) not in spreadsheet:
                # This student isn't present in the grading spreadsheet, skip
                not_present.append(ConsistencyChecker._get_link(
                    ids, user_id, email, submission_id, attempt_slide, ferpa
                ))
                continue

            if count % PROGRESS_UPDATE_MULTIPLE == 0:
                if progress_bar_update:
                    await progress_bar_update(count, len(users))
                logging.info(f"{count} / {len(users)} Completed")
            count += 1

            submissions = (ed_helper.get_challenge_submissions(
                                user_id, challenge_id
                           ) if not attempt_slide else
                           ed_helper.get_attempt_submissions(
                                user_id, lesson_id, slide_id,
                                submission_id, rubric
                           ))
            if submissions is None:
                continue

            submission_fixes, submission_id = (
                ConsistencyChecker._find_submission_fixes(
                    submissions, num_criteria, due_at, template
                )
            )
            if submission_fixes:
                link = ConsistencyChecker._get_link(
                    ids, user_id, email, submission_id, attempt_slide, ferpa
                )

                key = (section if spreadsheet is None
                       else spreadsheet[str(user_id)])
                fixes[key].append((link, submission_fixes))

        logging.info("Completed consistency check")
        return fixes, not_present

    @staticmethod
    def _convert_fixes_to_list(
        fixes: Dict[str, Tuple[str, str]]
    ) -> List[List[str]]:
        """
        Converts the fixes dictionary to a list format used to export .csv and
        .html files

        Params: 'fixes' - A dictionary mapping (TA | link) -> (link, issue)
        Returns: A list of [(TA | link), link, issue] lists
        """
        data = []
        for ta, issues in fixes.items():
            for (link, issue) in issues:
                data.append([ta, link, issue])
        return data

    @staticmethod
    async def check_consistency(
        ed_helper: EdHelper,
        url: str, file_name: str,
        template: Optional[bool] = False,
        spreadsheet: Optional[Dict[str, str]] = None,
        progress_bar_update: Optional[Callable[[int, int], None]] = None,
        ferpa: Optional[bool] = True
    ) -> Tuple[Dict[str, Tuple[str, str]], List[str], int]:
        """
        Checks and organizes information regarding grading consistency for a
        given ed assignment.

        Params: 'ed_helper' - A properly initialized EdHelper object with API
                              access to the ed assignment
                'url' - The url of the ed assignment to check
                'file_name' - The name to use for the two saved .csv and .html
                              files
                'spreadsheet' - A dictionary mapping ed student ID to TA name
                                (can be None)
                'progress_bar_update' - A function to call with incremental
                                        values that updates a user-viewable
                                        progress bar
                'ferpa' - Whether or not to censor student emails from links,
                          default True
        Returns: A dictionary mapping (TA | link) -> (link, fixes) for all
                 assignment that had incorrect formatting, a list of links to
                 student assignments not found in the grading spreadsheet, and
                 the total number of issues found
        """
        # Remove email since it mseese with ID regex
        url = ConsistencyRegex.EMAIL_REGEX.sub('', url)

        fixes, not_present = (
            await ConsistencyChecker._find_fixes(
                ed_helper, url, template, spreadsheet,
                progress_bar_update, ferpa
            )
        )
        if progress_bar_update:
            await progress_bar_update(1, 1)

        # Write the info into files to be sent
        data = ConsistencyChecker._convert_fixes_to_list(fixes)
        total_issues = len(data)

        file_path = os.path.join(TEMP_DIR, file_name)
        write_csv(file_path + ".csv", ['TA', 'Link', 'Issue'], data)
        convert_csv_to_html(file_path + ".csv", file_path + ".html")

        return fixes, not_present, total_issues
