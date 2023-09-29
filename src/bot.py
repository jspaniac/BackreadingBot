import json
import discord
from discord.ext import commands, tasks
import logging
from constants import (
    LOGGING_FILE, REFRESH_DELAY, AUTH_FILE
)
from utils import send_message

from database import Database
from discord_helper import DiscordHelper
from consistency_checker import ConsistencyChecker
from ed_helper import EdHelper

logging.basicConfig(filename=LOGGING_FILE, encoding='utf-8', level=logging.INFO)

#-------------------------------------------------------------------------------------------------------------------#
# START CONFIGURATIONs

intents = discord.Intents(messages=True, guilds=True,
                          members=True, message_content=True, reactions=True)
bot = commands.Bot(command_prefix='!', intents=intents)
database = Database()

#-------------------------------------------------------------------------------------------------------------------#
# START COMMANDS

@bot.command(name='br-setup', help="Setup the backreading bot, only available to grading-lead roles")
async def br_setup(ctx):
    logging.info(f"Setup command from guild: {ctx.guild.id}")
    try:
        if ctx.guild.id in database:
            logging.debug(f"{ctx.guild.id} already registered in database, returning")
            await send_message(ctx.channel, """Backreading bot already setup in this server. If you
                    wish to reset the bot or reconfigure, try 'backreading-reset' instead!""")
            return

        DiscordHelper.setup_bot(ctx, database, bot)
    except Exception as e:
        logging.exception(e)
        send_message(ctx.channel, f"Error encountered when handling request: {e}")

@bot.command(name='br-stop', help="Stops the backreading functionality of the bot, removing all data stored")
async def br_stop(ctx):
    logging.info(f"Stop command from guild {ctx.guild.id}")
    try:
        if ctx.guild.id not in database:
            logging.debug(f"{ctx.guild.id} not registered in database, returning")
            await send_message(ctx.channel, "Backreading bot not setup for this server, nothing to stop")
            return

        DiscordHelper.stop_bot(ctx, database)
    except Exception as e:
        logging.exception(e)
        send_message(ctx.channel, f"Error encountered when handling request: {e}")

@bot.command(name='br-push', help="Reply to the agreed on answer with this command to push it to ed")
async def br_push(ctx):
    logging.info(f"Pushing response from {ctx.channel}")
    try:
        if ctx.message.reference is None:
            logging.warning("Invalid channel")
            await send_message(ctx.channel, "This command must be used in response to the answer you wish to push")
            return

        thread = discord.utils.get(ctx.guild.threads, id=ctx.channel.id)
        if thread is None or thread.owner != bot.user:
            logging.warning("Invalid channel")
            await send_message(ctx.channel, "This command can only be used in a thread started by the intructor-bot")
            return
        
        DiscordHelper.push_ed_response(ctx, database, bot, thread)
    except Exception as e:
        logging.exception(e)
        send_message(ctx.channel, f"Error encountered when handling request: {e}")

@bot.command(name='br-pull', help="Pulls new threads from ed")
async def br_pull(ctx):
    logging.info(f"Refreshing for {ctx.guild.id}")
    try:
        if ctx.guild.id not in database:
            logging.debug(f"{ctx.guild.id} not registered in database, returning")
            return

        DiscordHelper.refresh_threads(ctx.guild.id, database, bot)
    except Exception as e:
        logging.exception(e)
        send_message(ctx.channel, f"Error encountered when handling request: {e}")

@bot.command(name='gr-check', help="""Checks to see if TAs are done grading. Call with submissions link. Optional
                                      attachment: .csv grading spreadsheet""")
async def gr_check(ctx, submission_link):
    logging.info(f"Checking submissions w/ completed grading - {submission_link}")
    try:
        if not EdHelper.valid_assignment_url(submission_link):
            send_message(ctx.channel, "Provided link is invalid, try again")
            return
        
        attachment_url = ctx.message.attachments[0].url if ctx.message.attachments else None
        ed_helper = EdHelper(database.get_token(ctx.guild.id))
        ConsistencyChecker.check_ungraded(ctx, ed_helper, submission_link, attachment_url)
    except Exception as e:
        logging.exception(e)
        send_message(ctx.channel, f"Error encountered when handling request: {e}")

@bot.command(name='gr-consistency', help="""Checks the consistency of grading. Call with the submission link.
                                            Optional 2nd arg: whether or not a template is used. Optional attachment:
                                            .csv grading spreadsheet""")
async def gr_consistency(ctx, submission_link, template: bool = False):
    logging.info(f"Checking submissions for consistency: {submission_link}, {template}")
    try:
        if not EdHelper.valid_assignment_url(submission_link):
            send_message(ctx.channel, "Provided link is invalid, try again")
            return
        
        attachment_url = ctx.message.attachments[0].url if ctx.message.attachments else None
        ed_helper = EdHelper(database.get_token(ctx.guild.id))
        ConsistencyChecker.check_consistency(ctx, ed_helper, submission_link, attachment_url, template)
        pass
    except Exception as e:
        logging.exception(e)
        send_message(ctx.channel, f"Error encountered when handling request: {e}")

#-------------------------------------------------------------------------------------------------------------------#
# START EVENTS

@bot.event
async def on_connect():
    logging.info("Bot finished loading external files!")
    pull_threads.start()

@tasks.loop(seconds=REFRESH_DELAY*60)
async def pull_threads():
    try:
        for guild_id in database.guild_ids():
            await DiscordHelper.refresh_threads(guild_id)
    except Exception as e:
        logging.exception(e)

@bot.event
async def close():
    logging.info("Shutting down, saving database")
    database.save()

#-------------------------------------------------------------------------------------------------------------------#
# START BOT

auth = json.load(open(AUTH_FILE))
bot.run(auth['token'])