import json
import os
import discord
import datetime
from discord.ext import commands, tasks
import logging
from src.constants import (
    LOGGING_FILE, REFRESH_DELAY, AUTH_FILE, TEMP_DIR
)
from src.utils import (
    send_message, invert_csv, progress_bar
)

from src.database import Database
from src.discord_helper import DiscordHelper
from src.consistency_checker import ConsistencyChecker
from src.ed_helper import EdHelper

logging.basicConfig(filename=LOGGING_FILE, encoding='utf-8',
                    level=logging.INFO)

# -----------------------------------------------------------------------------#
# START CONFIGURATIONs

intents = discord.Intents(messages=True, guilds=True,
                          members=True, message_content=True, reactions=True)
bot = commands.Bot(command_prefix='!', intents=intents)
database = Database()

# -----------------------------------------------------------------------------#
# START COMMANDS


@bot.command(
    name='br-setup',
    help="Setup the backreading bot, only available to grading-lead roles"
)
async def br_setup(ctx):
    logging.info(f"Setup command from guild: {ctx.guild.id}")
    try:
        if ctx.guild.id in database:
            logging.info(f"{ctx.guild.id} already registered in database")
            await send_message(ctx.channel,
                               "Backreading bot already setup in this server" +
                               ". If you wish to reset the bot or re" +
                               "configure, try 'br-stop' first instead!")
            return

        await DiscordHelper.setup_bot(ctx, database, bot)
        logging.info(f"Successfully added {ctx.guild.id} to bot database")
    except Exception as e:
        logging.exception(e)
        await send_message(ctx.channel,
                           f"Error encountered when handling request: {e}")


@bot.command(
    name='br-stop',
    help=("Stops the backreading functionality of the bot, "
          "removing all data stored")
)
async def br_stop(ctx):
    logging.info(f"Stop command from guild {ctx.guild.id}")
    try:
        if ctx.guild.id not in database:
            logging.info(f"{ctx.guild.id} not registered in database")
            await send_message(ctx.channel,
                               "Backreading bot not setup for this server, " +
                               "nothing to stop")
            return

        await DiscordHelper.stop_bot(ctx, database)
        logging.info(f"Successfully removed {ctx.guild.id} from bot database")
    except Exception as e:
        logging.exception(e)
        await send_message(ctx.channel,
                           f"Error encountered when handling request: {e}")


@bot.command(
    name='br-push',
    help="Reply to the agreed on answer with this command to push it to ed"
)
async def br_push(ctx):
    logging.info(f"Pushing response from {ctx.channel}")
    try:
        if ctx.message.reference is None:
            logging.info("Not used as a message reply")
            await send_message(ctx.channel,
                               "This command must be used in response to the" +
                               " answer you wish to push")
            return

        thread = DiscordHelper.get_thread(ctx.guild, ctx.channel.id)
        if thread is None or thread.owner != bot.user:
            logging.info("Not used in an appropriate backreading thread")
            await send_message(ctx.channel,
                               "This command can only be used in a thread " +
                               "started by the intructor-bot")
            return

        await DiscordHelper.push_ed_response(ctx, database, bot, thread)
        logging.info(f"Successfully pushed response from {ctx.channel}")
    except Exception as e:
        logging.exception(e)
        await send_message(ctx.channel,
                           f"Error encountered when handling request: {e}")


@bot.command(
    name='br-pull',
    help="Pulls new threads from ed"
)
async def br_pull(ctx):
    logging.info(f"Refreshing backreading threads for {ctx.guild.id}")
    try:
        if ctx.guild.id not in database:
            logging.info(f"{ctx.guild.id} not registered in database")
            send_message(ctx.channel,
                         "Unable to pull as this server is unregistered")
            return

        await DiscordHelper.refresh_threads(ctx.guild.id, database, bot)
        await send_message(ctx.channel, "Refreshed!")
        logging.info("Successfully refreshed backreading threads for " +
                     f"{ctx.guild.id}")
    except Exception as e:
        logging.exception(e)
        await send_message(ctx.channel,
                           f"Error encountered when handling request: {e}")


@bot.command(
    name='gr-check',
    help=("Checks to see if TAs are done grading. Call with submissions "
          "link. Optional attachment: .csv grading spreadsheet"))
async def gr_check(ctx, submission_link):
    logging.info(f"Checking submissions for {ctx.guild.id} w/ completed " +
                 f"grading - {submission_link}")
    try:
        if not EdHelper.valid_assignment_url(submission_link):
            send_message(ctx.channel, "Provided link is invalid, try again")
            return
        if "attempt" in submission_link and "email" in submission_link:
            await send_message(ctx.channel,
                               "Provided link accidentally contains FERPA " +
                               "protected information (email). Please call " +
                               "again with the email removed")
            return

        spreadsheet = invert_csv(
            DiscordHelper.get_attachment(ctx.message.attachments[0].url)
        ) if ctx.message.attachments else None
        ed_helper = EdHelper(database.get_token(ctx.guild.id))

        update_progress = None
        if "attempt" in submission_link:
            # Converting requires a lot of API calls which takes much longer
            progress_bar_message = await send_message(ctx.channel,
                                                      progress_bar(0, 1))

            async def update_progress(curr, total):  # noqa: F811
                await progress_bar_message.edit(
                    embed=discord.Embed(description=progress_bar(curr, total))
                )

        key_to_ungraded, total_ungraded = (
            await ConsistencyChecker.check_ungraded(
                ed_helper, submission_link, spreadsheet, update_progress
            )
        )

        embeds = DiscordHelper._format_ungraded_embed(
            key_to_ungraded, ed_helper.get_slide(submission_link)['title']
        )
        for embed in embeds:
            await send_message(ctx.channel, embed)
        await send_message(ctx.channel,
                           "All clear!" if total_ungraded == 0 else
                           f"{total_ungraded} students still ungraded")

        logging.info("Successfully checked grading completion for " +
                     f"{ctx.guild.id}")
    except Exception as e:
        logging.exception(e)
        await send_message(ctx.channel,
                           f"Error encountered when handling request: {e}")


@bot.command(
    name='gr-consistency',
    help=("Checks the consistency of grading. Call with the submission link. "
          "Optional 2nd arg: whether or not a template is used. Optional "
          "attachment: .csv grading spreadsheet"))
async def gr_consistency(ctx, submission_link, template: bool = False):
    logging.info(f"Checking submissions for consistency in {ctx.guild.id}: "
                 f"{submission_link}, {template}")
    try:
        if not EdHelper.valid_assignment_url(submission_link):
            await send_message(ctx.channel,
                               "Provided link is invalid, try again")
            return
        if "attempt" in submission_link and "email" in submission_link:
            await send_message(ctx.channel,
                               "Provided link accidentally contains FERPA " +
                               "protected information (email). Please call " +
                               "again with the email removed")
            return

        ed_helper = EdHelper(database.get_token(ctx.guild.id))
        spreadsheet = invert_csv(
            DiscordHelper.get_attachment(ctx.message.attachments[0].url)
        ) if ctx.message.attachments else None
        file_path = os.path.join(TEMP_DIR,
                                 f'{ctx.guild.id}-{datetime.datetime.now()}')

        progress_bar_message = await send_message(ctx.channel,
                                                  progress_bar(0, 1))

        async def update_progress(curr, total):
            await progress_bar_message.edit(
                embed=discord.Embed(description=progress_bar(curr, total))
            )

        # TODO: shard blocking issue
        fixes, not_present, total_issues = (
            await ConsistencyChecker.check_consistency(
                ed_helper, submission_link, file_path, template,
                spreadsheet, update_progress
            )
        )

        if total_issues > 0:
            embeds = DiscordHelper._format_fixes_embed(
                spreadsheet, fixes,
                ed_helper.get_slide(submission_link)['title']
            )
            await send_message(
                ctx.channel, embeds[0],
                files=[discord.File(file_path + ".csv"),
                       discord.File(file_path + ".html")]
            )
            for i in range(1, len(embeds)):
                await send_message(ctx.channel, embeds[i])
        if len(not_present) > 0:
            await send_message(ctx.channel,
                               f"{len(not_present)} students not on the " +
                               "grading spreadsheet, refresh the roster")
        await send_message(ctx.channel,
                           "All clear!" if total_issues == 0 else
                           f"{total_issues} students with consistency issues")

        logging.info("Successfully completed consistency check for " +
                     f"{ctx.guild.id}")
    except Exception as e:
        logging.exception(e)
        await send_message(ctx.channel,
                           f"Error encountered when handling request: {e}")

# -----------------------------------------------------------------------------#
# START EVENTS


@bot.event
async def on_connect():
    logging.info("Bot finished loading external files!")
    if not pull_threads.is_running():
        pull_threads.start()


@tasks.loop(seconds=REFRESH_DELAY*60)
async def pull_threads():
    try:
        for guild_id in database.guild_ids():
            # TODO: Shard blocking
            await DiscordHelper.refresh_threads(guild_id, database, bot)
    except Exception as e:
        logging.exception(e)


@bot.event
async def close():
    logging.info("Shutting down, saving database")
    database.save()

# -----------------------------------------------------------------------------#
# START BOT

bot.run(json.load(open(AUTH_FILE))['token'])
