import os
import asyncio
import argparse
import datetime

from src.ed_helper import EdHelper
from src.consistency_checker import ConsistencyChecker
from src.utils import (
    progress_bar
)
from src.exceptions import (
    MissingArgument, InvalidArgument
)
from src.constants import TEMP_DIR

CHOICES = ['consistency', 'ungraded']


async def main():
    for choice in CHOICES:
        if choice not in globals() or not callable(globals()[choice]):
            raise Exception(f"Not a function with matching name: {choice}")

    parser = argparse.ArgumentParser(
        description="This script library allows CSE 12x/14x TAs perform " +
                    "various grading assistance checks"
    )
    parser.add_argument(
        '--command', '-c',
        help='What command would you like to run',
        choices=CHOICES, required=True
    )
    parser.add_argument(
        '--ed_token', '-e',
        help='Ed API token to make requests with'
    )
    parser.add_argument(
        '--assignment_link', '-l',
        help="Assignment link you'd like to check, should link to the Final " +
             "Submission slide"
    )
    parser.add_argument(
        '--scrubbed_spreadsheet', '-s',
        help="Path to the scrubbed grading spreadsheet"
    )
    parser.add_argument(
        '--template', '-t',
        help="Enables checking against the overall feedback template",
        dest='template', action='store_true'
    )
    parser.set_defaults(template=False)
    parser.add_argument(
        '--ferpa', '-f',
        help="Enables FERPA mode, removing student emails from results",
        dest='ferpa', action='store_true'
    )
    parser.set_defaults(ferpa=False)

    args = parser.parse_args()
    await globals()[args.command](args)


async def consistency(args):
    if args.ed_token is None:
        raise MissingArgument("Ed token required to run grading checks")
    if args.assignment_link is None:
        raise MissingArgument("Assignment link required to run grading checks")
    if not EdHelper.valid_token(args.ed_token):
        raise InvalidArgument("Ed token is invalid")
    if not EdHelper.valid_assignment_url(args.assignment_link):
        raise InvalidArgument("Assignment link is invalid")

    spreadsheet = None
    if args.scrubbed_spreadsheet is not None:
        spreadsheet = open(args.scrubbed_spreadsheet)

    ed_helper = EdHelper(args.ed_token)
    file_name = os.path.join(TEMP_DIR, f'user-{datetime.datetime.now()}')

    print("\nRunning consistency checker:")
    print(progress_bar(0, 1), end='\r', flush=True)
    update_progress = (
        lambda curr, total: print(
            progress_bar(curr, total), end='\n' if curr == total
            else '\r', flush=True
        )
    )

    fixes, not_present, total_issues = (
        await ConsistencyChecker.check_consistency(
            ed_helper, args.assignment_link, file_name, args.template,
            spreadsheet, update_progress, args.ferpa
        )
    )

    print()
    print("All clear!" if total_issues == 0 else
          f"{total_issues} students with consistency issues")
    if total_issues > 0:
        print("Found Issues:")
        for ta, issues in fixes.items():
            print(f"\t{'TA' if spreadsheet is not None else 'Section'}: " +
                  f"{ta}, Issues: {len(issues)}")
            for issue in issues:
                print(f"\t\t{issue}")
    if len(not_present) > 0:
        print()
        print("Student submissions not present in grading spreadsheet:")
        for link in not_present:
            print(f"\t{link}")
    print()
    print("Result files can be found at:" +
          f"\n\t{file_name}.csv\n\t{file_name}.html\n")


async def ungraded(args):
    if args.ed_token is None:
        raise MissingArgument("Ed token required to run grading checks")
    if args.assignment_link is None:
        raise MissingArgument("Assignment link required to run grading checks")
    if not EdHelper.valid_token(args.ed_token):
        raise InvalidArgument("Ed token is invalid")
    if not EdHelper.valid_assignment_url(args.assignment_link):
        raise InvalidArgument("Assignment link is invalid")

    spreadsheet = None
    if args.scrubbed_spreadsheet is not None:
        spreadsheet = open(args.scrubbed_spreadsheet)

    ed_helper = EdHelper(args.ed_token)
    print("\nRunning grade completion checker:")
    print(progress_bar(0, 1), end='\r', flush=True)
    update_progress = (
        lambda curr, total: print(
            progress_bar(curr, total), end='\n' if curr == total
            else '\r', flush=True
        )
    )

    key_to_ungraded, not_present, total_ungraded = (
        await ConsistencyChecker.check_ungraded(
            ed_helper, args.assignment_link, spreadsheet, update_progress
        )
    )

    print("All clear!" if total_ungraded == 0
          else f"{total_ungraded} students with incomplete grading")
    if total_ungraded > 0:
        print("Found Ungraded Instances:")
        for ta, ungraded in key_to_ungraded.items():
            print(f"\t{'TA' if spreadsheet is not None else 'Section'}: " +
                  "{ta}, Ungraded: {ungraded}")
    if not_present > 0:
        print()
        print("Total student submissions not present in grading " +
              f"spreadsheet: {not_present}")
        print("Refresh grading roster!")
    print()

if __name__ == "__main__":
    asyncio.run(main())
