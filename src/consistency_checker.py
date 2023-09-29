import os
from collections import defaultdict
import discord
import datetime
import re

from utils import (
    invert_csv, write_csv, send_message, progress_bar, convert_csv_to_html
)
from constants import (
    TEMP_DIR, PROGRESS_UPDATE_MULTIPLE, ASSIGNMENT_GRACE_MINUTES
)

from ed_helper import EdHelper
from discord_helper import DiscordHelper

class ConsistencyConstants:
    FEEDBACK_BOX_REGEX ='{criteria_name}[a-zA-Z\s]*:[\s]*(\({criteria_mark}\)|{criteria_mark})'
    TEMPLATE_REGEX = '{criteria_name}[a-zA-Z\s]*:'
    VIEW_SUBMISSION_LINK = 'https://edstem.org/us/courses/{course_id}/lessons/{lesson_id}/slides/{slide_id}/submissions?u={user_id}&s={submission_id}'

class ConsistencyRegex:
    EMAIL_REGEX = re.compile(
        r'[A-Za-z0-9]+@(uw|cs.washington).edu')

class ConsistencyChecker:
    @staticmethod
    def _count_ungraded(users, spreadsheet):
        """
        Counts the total number users with incomplete feedback in 'users' and keeps track of a dictionary
        mapping either (section | TA) -> total ungraded depending on if an attachment_url is provided

        Params: 'users' - A list of Ed user objects for a course
                'spreadsheet' - A dictionary mapping ed user_id -> TA name. If none, section codes will be
                                used instead
        Returns: The aforementioned dictionary and the total number of ungraded students
        """
        key_to_ungraded = {}
        total_ungraded = 0
        for user in users:
            if user['course_role'] != "student":
                continue
            
            key = user['tutorial']
            if spreadsheet:
                if str(user['id']) not in spreadsheet:
                    continue
                key = spreadsheet[str(user['id'])]
            
            if not key in key_to_ungraded:
                key_to_ungraded[key] = 0
            if user['completed'] and user['feedback_status'] != "complete":
                    key_to_ungraded[key] += 1
                    total_ungraded += 1
        return key_to_ungraded, total_ungraded

    @staticmethod
    def _format_ungraded_embed(key_to_ungraded, slide_title):
        """
        Creates and formats a discord embed that contains relevant information on ungraded submissions

        Params: 'key_to_ungraded' - A dictionary mapping either (section | TA) -> total ungraded
                'slide_title' - The title of the ed assignment slide
        Returns: A properly formatted discord embed
        """
        embed = discord.Embed(title=slide_title,
                              description="Report of students with uncomplete feedback")
        for key, ungraded in key_to_ungraded.items():
            embed.add_field(name=key, value=ungraded)
        return embed

    @staticmethod
    async def check_ungraded(ed_helper, channel, url, attachment_url):
        """
        Checks and organizes information regarding ungraded students for a given ed assignment

        Params: 'ctx' - The context of the user request
                'ed_helper' - A properly initialized EdHelper object with API access to the ed assignment
                'url' - The url of the ed assignment to check
                'attachment_url' - The url of the attachment sent with the initial user request (can be None)
        """
        slide = ed_helper.get_slide(url)
        challenge_users = ed_helper.get_challenge_users(slide['challenge_id'])
        attachment = invert_csv(DiscordHelper.get_attachment(attachment_url)) if attachment_url else None
        
        key_to_ungraded, total_ungraded = ConsistencyChecker._count_ungraded(challenge_users, attachment)
        await send_message(channel, ConsistencyChecker._format_ungraded_embed(key_to_ungraded, slide['title']))
        await send_message(channel, "All clear!" if total_ungraded == 0 else f"{total_ungraded} students still ungraded")

    @staticmethod
    def _check_criteria(all_criteria, content):
        """
        Checks to see if the grade in Ed's feedback box matches that assigned in the corresponding dropdown menu

        Params: 'all_criteria' - Ed criteria dropdown objects
                'content' - The content within the feedback box
        Returns: A reason for any issue found, "" if no issues
        """
        for criteria in all_criteria:
            # TODO: This is gross - either fix the template or figure out a better way
            if criteria['name'] == "Testing/Reflection":
                criteria['name'] = "(Reflection|Testing/Reflection|Testing\s/\sReflection)"

            if not re.compile(ConsistencyConstants.FEEDBACK_BOX_REGEX.format(criteria_name=criteria['name'],
                                                                             criteria_mark=criteria['mark'])).search(content):
                # Feedback not properly templated
                if not re.compile(ConsistencyConstants.TEMPLATE_REGEX.format(criteria_name=criteria['name'])).search(content):
                    if criteria['mark'] != "E":
                        return "Template not used, "
                else:
                    # Template was used, but the mark doesn't match
                    return "Assigned grade doesn't match feedback box, "
        return ""

    @staticmethod
    def _find_submission_fixes(submissions, challenge, due_at, template):
        """
        Parses through a students graded submissions and reports any issues found with grading formatting

        Params: 'submissions' - A list of Ed submission objects
                'challenge' - Ed challenge objects
                'due_at' - A datetime object representing the due date of the assignment
                'template' - Whether or not the grading template is expected
        Returns: Any grading fixes that need to be made and the id of the submission. None, None if there is no issue
        """
        grace_period = datetime.timedelta(minutes=ASSIGNMENT_GRACE_MINUTES)
        for submission in submissions:
            created_at = EdHelper.parse_datetime(submission['created_at'], milliseconds=False)
            if created_at < due_at + grace_period:
                if submission['feedback'] is None:
                    # Feedback not given to appropriate submission
                    return "Missing grade / incorrect submission graded", submission['id']

                reason = ""
                content = EdHelper.parse_content(submission['feedback']['content'])
                if len(submission['feedback']['criteria']) != len(challenge['settings']['criteria']):
                    # Didn't fill out all dimensions
                    reason += "Not all dimensions assigned a grade, "
                if not ConsistencyRegex.EMAIL_REGEX.search(content):
                    # Missing contact info email
                    reason += "Missing TA contact information, "
                if template:
                    # Lets check to see if a template is being used - assuming the format is "Dimension: Score"
                    reason += ConsistencyChecker._check_criteria(submission['feedback']['criteria'], content)
                if reason != "":
                    return reason[:-2], submission['id']
                break
        return None, None

    @staticmethod
    async def _find_fixes(progress_bar, url, ed_helper, spreadsheet, template):
        """
        Finds all student submissions that have inconsistently formatted grading feedback and creates a dictionary
        containing the fixes that need to be made before publishing grades

        Params: 'progress_bar' - The discord progress bar message so it can be edited and show progress
                'url' - The ed assignment url
                'ed_helper' - A properly initialized EdHelper object with API access to the ed assignment
                'spreadsheet' -  A dictionary mapping ed student ID to TA name (can be None)
                'template' - Whether or not the grading template is expected
        Returns: A dictionary mapping (TA | link) -> (link, fixes) for all assignment that had incorrect formatting
        """
        # Get the challenge id for the assignment
        ids = EdHelper.get_ids(url)
        challenge_id = ed_helper.get_slide(url)['challenge_id']

        # Get user/challenge information
        users = {user['id']: user['email'] for user in ed_helper.get_challenge_users(challenge_id) if user['course_role'] == "student"}
        challenge = ed_helper.get_challenge(challenge_id)
        due_at = EdHelper.parse_datetime(challenge['due_at'], milliseconds=False)
        
        fixes = defaultdict(list)
        count = 0
        for user_id, _ in users.items():
            if count % PROGRESS_UPDATE_MULTIPLE == 0:
                await progress_bar.edit(embed=discord.Embed(description=progress_bar(count, len(users))))
            count += 1

            submissions = ed_helper.get_challenge_submissions(user_id, challenge_id)
            submission_fixes, submission_id = ConsistencyChecker._find_submission_fixes(submissions, challenge, due_at, template)
            if submission_fixes:
                link = ConsistencyConstants.VIEW_SUBMISSION_LINK.format(
                            course_id=ids[0], lesson_id=ids[1], slide_id=ids[2],
                            user_id=user_id, submission_id=submission_id)
                key = link if spreadsheet is None else spreadsheet[str(user_id)]
                fixes[key].append((link, submission_fixes))

        return fixes

    @staticmethod
    def _convert_fixes_to_list(fixes):
        """
        Converts the fixes dictionary to a list format used to export .csv and .html files

        Params: 'fixes' - A dictionary mapping (TA | link) -> (link, issue)
        Returns: A list of [(TA | link), link, issue] lists
        """
        data = []
        for ta, issues in fixes.items():
            for (link, issue) in issues:
                data.append([ta, link, issue])
        return data

    @staticmethod
    def _format_fixes_embed(spreadsheet, fixes, slide_title):
        """
        Creates and formats a discord embed that contains relevant information on inconsistently graded submissions

        Params: 'spreadsheet' - A dictionary mapping ed student ID to TA name (can be None)
                'fixes' - A dictionary (TA | link) -> fixes depending on if a grading spreadsheet was provided
                'slide_title' - The title of the ed assignment slide
        Returns: A properly formatted discord embed
        """
        embed = discord.Embed(title=slide_title,
                              description="Report of students with inconsistent feedback")
        if spreadsheet is not None:
            for ta, issues in fixes.items():
                embed.add_field(name=ta, value=len(issues))
        return embed
    
    @staticmethod
    async def check_consistency(ed_helper, channel, url, attachment_url, template):
        """
        Checks and organizes information regarding grading consistency for a given ed assignment

        Params: 'ctx' - The context of the user request
                'ed_helper' - A properly initialized EdHelper object with API access to the ed assignment
                'url' - The url of the ed assignment to check
                'attachment_url' - The url of the attachment sent with the initial user request (can be None)
        """
        spreadsheet = invert_csv(DiscordHelper.get_attachment(attachment_url)) if attachment_url else None
        progress_bar_message = await send_message(channel, progress_bar(0, 1))
        fixes = await ConsistencyChecker._find_fixes(progress_bar_message, url, ed_helper, spreadsheet, template)
        await progress_bar_message.edit(embed=discord.Embed(description=progress_bar(1, 1)))

        # Write the info into files to be sent
        now = datetime.datetime.now()
        data = ConsistencyChecker._convert_fixes_to_list(fixes)
        total_issues = len(data)

        file_path = os.path.join(TEMP_DIR, f'{channel}-{now}') 
        write_csv(file_path + ".csv", ['TA', 'Link', 'Issue'], data)
        convert_csv_to_html(file_path + ".csv", file_path + ".html")

        # Send the files back
        embed = ConsistencyChecker._format_fixes_embed(spreadsheet, fixes, ed_helper.get_slide(url)['title'])
        await send_message(channel, embed=embed, files=[discord.File(file_path + ".csv"), discord.File(file_path + ".html")])
        await send_message(channel, "All clear!" if total_issues == 0 else f"{total_issues} students with consistency issues")

        # Remove the files
        os.remove(file_path + ".csv")
        os.remove(file_path + ".html")