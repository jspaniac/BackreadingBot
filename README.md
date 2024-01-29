# BackreadingBot

## Setup
There is a non-trivial amount of setup required to start executing this discord bot on your local machine, which has been segmented into the 3 primary parts below.
### Python
First, make sure you're on `python3.9` and that you're able to run python commands via a `python3.9` prefix. To test this, run the following:
```bash
python3.9 --version
```
Then create a conda environment for the python installation requirements
```bash
conda create --name backreading-bot
conda activate backreading-bot
```
Then, install the python dependencies
```bash
pip install -r requirements.txt
```
Currently, each of the listed requirements individually may/may not be actually necessary for the bot to function. These are just what was installed on the device used to run the bot in 2022-2024.

### Bash
Give the bash executables permissions to run
```bash
chmod +x bash/keep-running.sh
chmod +x bash/kill.sh
```

### Discord & API Tokens
First, you'll have to actually create and register the Discord application / bot via this [portal](https://discord.com/developers/applications). Create a new application, then create a new Bot within that application (feel free to name both of these what you wish, but the bot's name and image are what will show up on it's discord profile).

When you create the bot, copy it's token and paste it into `store/auth.json`, replacing the string labeled `TODO`. You'll also need to enable the server members and message content intents such that it is able to view server users and read command messages.

To actually add the bot to your discord use the following URL:

https://discord.com/api/oauth2/authorize?client_id=TODO&permissions=1497064598640&scope=bot%20applications.commands

Make sure to replace the client_id TODO with the one found on your Application's OAuth2 page.

## Running the Bot
Note that both of the following scripts assume that you have no other processes running on your computer launched using `python3.9`. Before running, it's worth checking if this assumption is valid via the following command:
```bash
ps -A | grep python3.9
```
If the command returns non-empty results, the following scripts should not be used and you should develop your own version of them that is compatible with the device in question.

To start running the bot execute the following terminal command:
```bash
./bash/keep-running.sh &
```
This will create a wrapper infinitely-looping process that consistently checks whether or not the bot has crashed (this frequently happens to me due to socket-related / internet connectivity issues). If it has, it relaunches so the bot is always up.

If you want to stop these infinitely looping processes (the `keep-running` script and the actual running bot), execute the follwoing:
```bash
./bash/kill.sh
```
This will stop the bot and related wrapper process.

# Using the Bot

If you aren't the owner of the bot in question, or if you've already completed the set up then the following describes how to use the bot with relevant commands

## Discord Command Examples
#### Backreading Functionality
The following are all tied to backread request adjacent useful functionality (hence the `br` prefix)
#### br-setup
```!br-setup```
- This command will setup backreading functionality which creates independent threads for assignment questions asked on Ed, allowing leads to organize their conversations surrounding different grading questions. Setting it up will launch a number of setup information queries. The information asked for will be in the following order:
    - Ed API token (via DM)
        - Your token can be found [here](https://edstem.org/us/settings/api-tokens).
    - Link to the staff Ed board to pull from
    - Link of the role to ping when a new thread is made
    - Whether or not you'd like to approve responses before they're made on your account (see `br-push`)
- When completed a #backread-requests thread should be created in the base channel directory (you might have to drag it where you'd like it to be organization-wise).
#### br-stop
```!br-stop```
- This command stops the backreading thread functionality, removing all relevant server information from the bot's database in the process. The previously created #backread-requests channel shouldn't be deleted so it can be referenced against in future quarters.
#### br-push
```!br-push```
- This command should be used in response to a discord message within a #backread-requests thread. Doing so will push the response to Ed on the account linked API token provided on setup.
#### br-pull
```!br-pull```
- This command performs a refresh of #backread-requests threads, pulling in new ones and closing previously answered ones. Note that this is run on a consistent interval by the bot itself, so this is only needed if you'd like to manually pull something into the server and quickly comment on it. 

#### Grading Functionality
The following are all tied to grading adjacent useful functionality (hence the `gr` prefix)
#### gr-check
```gr-check <ASSIGNMENT_LINK>```
- Checks which students that made a submission before the assignment deadline + grace period are missing feedback.
- ASSIGNMENT_LINK
    - Link to the assignment. If using the old Ed "checkpoints", you can just copy and paste the link for the 'Overall Grade' slide here:
i.e: https://edstem.org/us/courses/32019/lessons/51283/slides/296002
    - If using the newer Ed "submissions", you should copy the link for a student's 'Final Submission' slide and remove the student email from the URL:
i.e.: https://edstem.org/us/courses/50191/lessons/87264/attempts?slide=478583
- SCRUBBED_SPREADSHEET
    - Optionally, you can attach a scrubbed spreadsheet .csv file that maps TA name to Ed ID of student graded. If included, the consistency results will map ungraded students to the corresponding TA. If not, it will map to the student's registered section.
#### gr-consistency
```!gr-consistency <ASSIGNMENT_LINK> <CHECK_CONSISTENCY>```
- ASSIGNMENT_LINK
    - Link to the assignment. If using the old Ed "checkpoints", you can just copy and paste the link for the 'Overall Grade' slide here:
i.e: https://edstem.org/us/courses/32019/lessons/51283/slides/296002
    - If using the newer Ed "submissions", you should copy the link for a student's 'Final Submission' slide and remove the student email from the URL:
i.e.: https://edstem.org/us/courses/50191/lessons/87264/attempts?slide=478583
- CHECK_CONSISTENCY
    - Whether or not to check for consistency against the overall feedback template. Expects python boolean value
- SCRUBBED_SPREADSHEET
    - Optionally, you can attach a scrubbed spreadsheet .csv file that maps TA name to Ed ID of student graded. If included, the consistency results will map inconsistencies to the corresponding TA. If not, it will map to the student's registered section.


## Local Command Examples

Local execution is supported for the checking ungraded and consistency commands via the `src/commands.py` file. In doing so, as messages are no longer going through discord, you can actually generate *useful* Ed links (as they need to include student emails) if you run things this way. You'll need your [Ed API token](https://edstem.org/us/settings/api-tokens), a link to the assignment you wish to check, and some other optional paramters that are explained in more depth via the `--help` flag.

Below is an example of a consistency check run via this method (with the Ed API token removed):
```bash
python3.9 commands.py -c consistency -e ED_TOKEN -l 'https://edstem.org/us/courses/50191/lessons/87264/attempts?email=jspaniac@uw.edu&slide=478586' -t -f
```
The `-c` flag is for which command you'd like to run, `-e` is for your Ed API token, `-l` is for the link to the final submission slide for the assignment, `-t` indicates that we want to check against the overall grading template, and `-f` shows we want to have our results be FERPA compliant (not including student emails).

# Development
## Directory Layout
- `bash`
    - Where the bash scripts are located
    - `keep-running.sh`
        - Allows the bot to relaunch itself on crash
    - `kill.sh`
        - Kills both the currently running bot and `keep-running.sh`
- `src`
    - Where the actual library implementations exist.
    - `consistency_checker.py`
        - Running consistency checks:
            - Making sure selected dropdown matches value in overall feedback box
            - Most recent / final submission graded
            - TA email left on student submission
            - etc.
    - `constants.py`
        - Constant definition within the bot
            - Might be worth changing for your specific use case
    - `database.py`
        - Wrapper for database mapping
            - Connects server_id to relevant course information
    - `discord_helper.py`
        - Useful discord-related commands:
            - Getting user from server
            - Sending message to channel
            - etc.
    - `ed_helper.py`
        - Makes Ed API calls / restructures API response data in a more usable fashion
    - `exceptions.py`
        - Custom exception definitions used throughout the library
    - `html_constants.py`
        - Used to create HTML consistency_checker table formatting
    - `utils.py`
        - Useful functions used throughout the library
- `store`
    - For general storage purposes. Houses the physical database file and the user's Ed API token.
    - `logging`
        - Where the active logs are stored
- `temp`
    - Used by the bot when creating .csv / .html files for temporary storage before uploading to discord.
- `tests`
    - Where the 
- `bot.py`
    - Launch this to run the python bot
- `commands.py`
    - Local versions of the bot commands
