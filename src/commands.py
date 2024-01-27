import os
import asyncio
import argparse
import datetime
from ed_helper import EdHelper
from consistency_checker import ConsistencyChecker
from utils import (
    progress_bar
)
from constants import TEMP_DIR

CHOICES = ['consistency', 'ungraded']

async def main():
    for choice in CHOICES:
        if choice not in globals() or not callable(globals()[choice]):
            raise Exception(f"Not a function with matching name: {choice}")

    parser = argparse.ArgumentParser(description="")
    parser.add_argument('--command', '-c', help='What command would you like to run', choices=CHOICES, required=True)
    parser.add_argument('--ed_token', '-e', help='Ed API token to make requests with')
    parser.add_argument('--assignment_link', '-l', help="Assignment link you'd like to check, should link to the Final Submission slide")
    parser.add_argument('--scrubbed_spreadsheet', '-s', help="Path to the scrubbed grading spreadsheet")
    parser.add_argument('--template', '-t', help="Enables checking against the overall feedback template", dest='template', action='store_true')
    parser.set_defaults(template=False)
    parser.add_argument('--ferpa', '-f', help="Enables FERPA mode, removing student emails from results", dest='ferpa', action='store_true')
    parser.set_defaults(ferpa=False)

    args = parser.parse_args()
    await globals()[args.command](args)

async def consistency(args):
    spreadsheet = None
    if args.ed_token is None:
        raise Exception("Ed token required to run consistency checks")
    if args.assignment_link is None:
        raise Exception("Assignment link required to run consistency checks")
    if args.scrubbed_spreadsheet is not None:
        spreadsheet = open(args.scrubbed_spreadsheet)
    
    ed_helper = EdHelper(args.ed_token)
    file_name =  os.path.join(TEMP_DIR, f'user-{datetime.datetime.now()}')

    print("\nRunning consistency checker:")
    print(progress_bar(0, 1), end='\r', flush=True)
    async def update_progress(curr, total):
        print(progress_bar(curr, total), end='\n' if curr == total else '\r', flush=True)

    fixes, not_present, total_issues = await ConsistencyChecker.check_consistency(ed_helper, args.assignment_link, file_name, args.template, spreadsheet,
                                                                                  update_progress, args.ferpa)
    
    print()
    print("All clear!" if total_issues == 0 else f"{total_issues} students with consistency issues")
    if total_issues > 0:
        print("Found Issues:")
        for ta, issues in fixes.items():
            print(f"\t{'TA' if spreadsheet is not None else 'Section'}: {ta}, issues: {len(issues)}")
            for issue in issues:
                print(f"\t\t{issue}")
    if len(not_present) > 0:
        print()
        print("Student submissions not present in grading spreadsheet:")
        for link in not_present:
            print(f"\t{link}")
    print()
    print(f"Result files can be found at:\n\t{file_name}.csv\n\t{file_name}.html\n")

async def ungraded(args):
    if 'ed_token' not in args:
        raise Exception("Ed token required to run grading checks")
    if 'assignment_link' not in args:
        raise Exception("Assignment link required to run grading checks")
    
    ed_helper = EdHelper(args.ed_token)
    # TODO: Implement
    pass

if __name__ == "__main__":
    asyncio.run(main())