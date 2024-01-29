import discord
import logging
import re
import math
import requests
import datetime

from typing import (
    Union, Callable, Tuple, Dict, Optional, List, Any
)
from utils import (
    send_message, repeat_request, dm_check, correct_user_check, y_n_emoji
)
from constants import (
    TIMEOUT, LOGGING_FILE, PULL_DELAY, THREAD_LINK, DISCORD_MAX_EMBED_FIELDS
)
from exceptions import (
    TimeoutError, InvalidResponse
)

from database import Database
from ed_helper import EdHelper
from database import GuildInfo

logging.basicConfig(filename=LOGGING_FILE, encoding='utf-8',
                    level=logging.INFO)


class DiscordRegex:
    URL_REGEX = re.compile(r"https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/=]*)")  # noqa: E501


class DiscordHelper:
    @staticmethod
    def get_attachment(
        url: str
    ) -> Union[None, str]:
        """
        Params: 'url' - The url corresponding to a discord attachment
        Returns: The discord attachment for the given attachment url
        """
        return requests.get(url).content.decode('utf-8') if url else None

    @staticmethod
    async def create_channel(
        guild: Any, name: str,
        overwrites: Any
    ) -> int:
        """
        Params: 'guild' - The guild in which to create a channel
                'name' - The channel name
                'overwrites' - The appropriate overwrites for the channel
                               (found via discord API)
        Returns: The channel id for the newly created channel
        """
        return (
            await guild.create_text_channel(name, overwrites=overwrites)
        ).id

    @staticmethod
    async def create_thread(
        channel: Any,
        starting_message: str,
        thread_name: str
    ) -> Any:
        """
        Params: 'channel' - The channel in which to create the thread
                'starting_message' - The starting message to created the
                                     thread off of
                'thread_name' - The name of the thread
        Returns: The newly created discord thread
        """
        message = await send_message(channel, starting_message)
        return await message.create_thread(name=thread_name)

    @staticmethod
    def get_role(
        guild: Any,
        role_id: int
    ) -> Any:
        """
        Params: 'guild' - The guild in which the role is
                'role_id' - The role ID to get
        Returns: The role object corresponding to the given role ID
        """
        return discord.utils.get(guild.roles, id=role_id)

    @staticmethod
    def get_thread(
        guild: Any,
        thread_id: int
    ) -> Any:
        """
        Params: 'guild' - The guild in which the role is
                'thread_id' - The thread ID to get
        Returns: The thread object corresponding to the given thread ID
        """
        return discord.utils.get(guild.threads, id=thread_id)

    @staticmethod
    async def resolve_thread(
        bot: Any,
        database: Database,
        guild_id: int,
        ed_thread_id: int,
        final_message: str
    ) -> None:
        """
        Resolves the given thread, sending a final message and removing it
        from the database

        Params: 'bot' - The discord bot object
                'thread' - The discord thread object to archive
                'database' - The bot's database
                'guild_id' - The ID of the guild where the thread is being
                             archived
                'thread_id' - The Ed ID of the thread being archived
                'final_message' - The final message to send to the thread
        """
        discord_thread_id = database.get_threads(guild_id)[ed_thread_id]
        logging.debug(f"Resolving thread {discord_thread_id}")
        thread = bot.get_channel(discord_thread_id)

        await send_message(thread, final_message)
        await thread.edit(archived=True, locked=True,)
        database.remove_thread(guild_id, ed_thread_id)

    @staticmethod
    async def _get_token(
        ctx: Any,
        bot: Any,
        respond_dm: Callable[[str], None]
    ) -> Tuple[str, Dict]:
        """
        Gets the users Ed API token via repeat request. Raises TimeoutError if
        the user request times out

        Params: 'bot' - The discord bot object
                'respond_dm' - A method that will send a given string as a DM
                               to the user
        Returns: The API token, Ed user object
        """
        async def invalid_wrapper():
            await respond_dm("Error with the provided ed token. " +
                             "Please try again")

        def check_wrapper(message):
            return dm_check(message, ctx)

        logging.info("Getting Ed API token from user")
        try:
            token, user = await repeat_request(bot, check_wrapper,
                                               EdHelper.valid_token, TIMEOUT,
                                               invalid_wrapper)
            logging.debug(f"Successfully retrived valid ed token {token}, " +
                          f"username {user['user']['name']}")
            await respond_dm("I'd recommend deleting that message now jic")
            await respond_dm("The account name associated with the provided " +
                             f"token is {user['user']['name']}. Now let's " +
                             "move back to the server")
            return token, user['user']
        except TimeoutError:
            await respond_dm("Request timed out")
            raise TimeoutError

    @staticmethod
    async def _get_course(
        ctx: Any,
        bot: Any,
        respond_public_channel: Callable[[str], None],
        ed_helper: EdHelper
    ) -> Tuple[str, Dict]:
        """
        Gets the appropriate Ed staff course URL via repeat request. Raises
        TimeoutError if the user request times out

        Params: 'bot' - The discord bot object
                'respond_public_channel' - A method that will send a given
                                           string as a message to a public
                                           channel
                'ed_user' - The ed user object retrieved via the user's API
                            token
                'discord_user' - The requesters discord user object
        Returns: The course URL, Ed course object
        """
        async def invalid_wrapper():
            await respond_public_channel("No valid ed course found for that " +
                                         "link. Please try again")

        def check_wrapper(message):
            return correct_user_check(message, ctx)

        logging.info("Getting Ed course information from user")
        while True:
            url, course = await repeat_request(bot, check_wrapper,
                                               ed_helper.valid_course, TIMEOUT,
                                               invalid_wrapper)
            logging.debug(f"Successfully retrieved course from url {url}, " +
                          f"name {course['code']}")
            if await y_n_emoji(
                bot, respond_public_channel,
                f"The course you provided is named {course['code']}, is " +
                "this correct?",
                ctx.author, TIMEOUT
            ):
                return url, course
            else:
                respond_public_channel("Then please enter the correct link 💅")

    @staticmethod
    async def _get_role(
        ctx: Any,
        bot: Any,
        respond_public_channel: Callable[[str], None]
    ) -> Tuple[str, Dict]:
        """
        Gets the backreading role to ping via repeat request. Raises
        TimeoutError if the user request times out

        Params: 'bot' - The discord bot object
                'respond_public_channel' - A method that will send a given
                                           string as a message to a public
                                           channel
                'roles' - A collection of all available roles within the
                          discord server
        Returns: The role name, and discord role object
        """
        async def invalid_wrapper():
            await respond_public_channel("Role with provided name does not " +
                                         "exist. Please re-enter")

        def valid_role_check(role):
            role = discord.utils.get(ctx.guild.roles, name=role)
            if role is None:
                raise InvalidResponse
            return role

        def check_wrapper(message):
            return correct_user_check(message, ctx)

        logging.info("Getting discord role from user")
        role_name, role = await repeat_request(
            bot, check_wrapper, valid_role_check, TIMEOUT, invalid_wrapper
        )
        logging.debug(f"Successfully retrieved role with id {role.id} from " +
                      f"name {role_name}")
        return role_name, role

    @staticmethod
    async def setup_bot(
        ctx: Any,
        database: Database, bot
    ) -> None:
        """
        Sets up the bot, gather necessary information from the user and
        storing it with the bot's database

        Params: 'ctx' - THe original request context
                'database' - The bot's database
                'bot' - The discord bot object
        """
        user_id = ctx.author.id
        requester = discord.utils.get(ctx.guild.members, id=user_id)

        async def respond_dm(message: str):
            """
            Sends 'message' to the dm of the user that originated the request
            """
            return (await send_message(requester, message))

        async def respond_public_channel(message: str):
            """
            Sends 'message' to the same channel as the original message was
            sent in
            """
            return (await send_message(ctx.channel, message))

        try:
            # 1. Store the user-id

            # 2. Ask for ed token
            await respond_public_channel("The first step requires entering " +
                                         "a valid ed token. For the sake of " +
                                         "privacy, I'll ask in a DM")
            await respond_dm("What is your ed token? Note that this " +
                             "application will be using this token to read " +
                             "and respond to threads on the server you " +
                             "provide. If you're not comfortable with this, " +
                             "feel free to let the request timeout")
            token, _ = await DiscordHelper._get_token(ctx, bot, respond_dm)
            ed_helper = EdHelper(token)

            # 3. Get the url with checking
            await respond_public_channel("Now, provide the url of the " +
                                         "discussion board for the ed " +
                                         "course you wish the bot to " +
                                         "connect to")
            _, course = await DiscordHelper._get_course(
                ctx, bot, respond_public_channel, ed_helper
            )

            # 4. Get backreading role for pings
            logging.info("Retrieving backreading role")
            await respond_public_channel("What is the name of your " +
                                         "backreading role?")
            _, role = await DiscordHelper._get_role(
                ctx, bot, respond_public_channel
            )

            # 5. Get approval
            approval = await y_n_emoji(
                bot, respond_public_channel,
                "Finally, do you want to manually approve responses before " +
                "they are made on your account?",
                ctx.author, TIMEOUT
            )

            # 6. Make the channel
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(
                    read_messages=False, send_messages=False
                ),
                role: discord.PermissionOverwrite(
                    read_messages=True, send_messages=False
                ),
                discord.utils.get(ctx.guild.members, id=bot.user.id):
                    discord.PermissionOverwrite(
                        read_messages=True, send_messages=True
                    )
            }
            channel_id = await DiscordHelper.create_channel(
                ctx.guild, 'backread-requests', overwrites
            )

            # 7. Store it into the map that will be loaded into the json
            #    on shutdown
            database.register(ctx.guild.id, GuildInfo.create(
                user_id, channel_id, token, course['id'], role.id, approval
            ))

            await send_message(ctx.channel,
                               "Congrats! Your backreading bot is setup and " +
                               "running!")
        except TimeoutError:
            logging.debug("Request timed out")
            respond_public_channel("Request timed out")

    @staticmethod
    async def stop_bot(
        ctx: Any,
        database: Database
    ) -> None:
        """
        Stops the bot from running on the on the server where the ctx was sent

        Params: 'ctx': The request message context
                'database': The bot's database
        """
        database.delete(ctx.guild.id)
        await send_message(ctx.channel, "Backreading bot stopped")

    @staticmethod
    async def push_ed_response(
        ctx: Any,
        database: Database,
        bot: Any,
        thread: Any
    ) -> None:
        """
        Pushes a grading question response from discord to Ed

        Params: 'ctx': The request message context
                'database': The bot's database
                'bot': The discord bot object
                'thread': The discord thread object containing the response
        """
        async def respond_thread(message):
            return (await send_message(ctx.channel, message))

        guild_id = ctx.guild.id
        ed_helper = EdHelper(database.get_token(guild_id))

        # Double-checking w/ admin or sender
        checker = discord.utils.get(
            ctx.guild.members, id=database.get_admin(guild_id)
        ) if database.get_approval(guild_id) else ctx.author
        message = checker.mention + (" do you approve of this response?"
                                     if database.get_approval(guild_id) else
                                     " just as a double-check, is this the" +
                                     " message you want to send?")

        if not await y_n_emoji(bot, respond_thread, message, checker, TIMEOUT):
            await respond_thread("Answer not approved")
            return

        starting_message = await thread.parent.fetch_message(thread.id)
        to_push = (
            await thread.fetch_message(ctx.message.reference.message_id)
        ).content
        course_thread_ids = EdHelper.get_ids(starting_message.embeds[0].url)

        ed_helper.push_answer(course_thread_ids[1], to_push)
        await DiscordHelper.resolve_thread(
            bot, database, ctx.guild.id, course_thread_ids[1], "Pushed to Ed!"
        )

    @staticmethod
    def _format_backreading_embed(
        thread: Any,
        course_id: int,
        simple: Optional[bool] = False
    ) -> Any:
        """
        Creates and formats a discord embed that contains relevant information
        on backread requests

        Params: 'thread' - The ed thread object of the request
                'course_id' - The Ed course ID
                'simple' - Whether or not the time and message description
                           should be added
        Returns: A properly formatted discord embed
        """
        time = EdHelper.parse_datetime(thread['created_at'])
        if simple:
            return discord.Embed(
                title=f"{thread['user']['name']}: {thread['title']}",
                url=THREAD_LINK.format(course_id=course_id,
                                       thread_id=thread['id'])
            )
        else:
            # Replace the link for FERPA reasons
            embed = discord.Embed(
                title=f"{thread['user']['name']}: {thread['title']}",
                url=THREAD_LINK.format(course_id=course_id,
                                       thread_id=thread['id']),
                description=re.sub(DiscordRegex.URL_REGEX,
                                   "Link on original post [removed for FERPA]",
                                   thread['document']),
                timestamp=time)
            embed.set_author(name=thread['category'] +
                             (" - " + thread['subcategory']
                              if thread['subcategory'] != "" else ""))
            return embed

    @staticmethod
    def _format_fixes_embed(
        spreadsheet: Dict[str, str],
        fixes: Dict[str, List[Tuple[str, str]]],
        slide_title: str
    ) -> Any:
        """
        Creates and formats a discord embed that contains relevant information
        on inconsistently graded submissions

        Params: 'spreadsheet' - A dictionary mapping ed student ID to TA name
                                (can be None)
                'fixes' - A dictionary (TA | link) -> fixes depending on if a
                          grading spreadsheet was provided
                'slide_title' - The title of the ed assignment slide
        Returns: A properly formatted discord embed
        """
        if spreadsheet is None:
            return [discord.Embed(title=slide_title,
                                  description="Report of students with " +
                                              "inconsistent feedback (1/1)")]

        total_embeds = math.ceil(len(fixes) / DISCORD_MAX_EMBED_FIELDS)
        embeds = [discord.Embed(title=slide_title,
                                description="Report of students with " +
                                            "inconsistent feedback " +
                                            f"({i + 1}/{total_embeds})")
                  for i in range(total_embeds)]

        i = 0
        for ta, issues in fixes.items():
            embeds[int(math.floor(i / DISCORD_MAX_EMBED_FIELDS))].add_field(
                name=ta, value=len(issues)
            )
            i += 1
        return embeds

    @staticmethod
    def _format_ungraded_embed(
        key_to_ungraded: Dict[str, int],
        slide_title: str
    ) -> Any:
        """
        Creates and formats a discord embed that contains relevant information
        on ungraded submissions

        Params: 'key_to_ungraded' - A dictionary mapping either
                                    (section | TA) -> total ungraded
                'slide_title' - The title of the ed assignment slide
        Returns: A properly formatted discord embed
        """
        total_embeds = math.ceil(len(key_to_ungraded) /
                                 DISCORD_MAX_EMBED_FIELDS)
        embeds = [discord.Embed(title=slide_title,
                                description="Report of students with "
                                            "uncomplete feedback " +
                                            f"({i + 1}/{total_embeds})")
                  for i in range(total_embeds)]

        i = 0
        for key, ungraded in key_to_ungraded.items():
            embeds[int(math.floor(i / DISCORD_MAX_EMBED_FIELDS))].add_field(
                name=key, value=ungraded
            )
            i += 1
        return embeds

    @staticmethod
    async def refresh_threads(
        guild_id: Any,
        database: Database,
        bot: Any
    ) -> Any:
        """
        Refreshes backreading threads for the given guild

        Params: 'guild_id' - The ID of the guild to refresh
                'database' - The bot's database
                'bot' - The discord bot object
        """
        # jic it's needed: 'filter': 'unanswered'
        guild = await bot.fetch_guild(int(guild_id))
        channel = await bot.fetch_channel(database.get_channel(guild_id))

        today = datetime.datetime.now(datetime.timezone.utc)  # noqa: F841
        delay_delta = datetime.timedelta(minutes=PULL_DELAY)  # noqa: F841

        ed_helper = EdHelper(database.get_token(guild_id))
        ed_threads = ed_helper.get_threads(database.get_course(guild_id))
        server_threads = database.get_threads(guild_id)

        deleted_threads = (server_threads -
                           {thread['id'] for thread in ed_threads})
        for thread_id in deleted_threads:
            # Thread's been deleted from ed and is still in discord (or in
            # theory the thread is really old and unanswered on ed)
            logging.info(f"Closing deleted thread {thread_id} with channel " +
                         f"id {server_threads[thread_id]}")
            await DiscordHelper.resolve_thread(bot, database, guild_id,
                                               thread_id, "Deleted from Ed")
            continue

        for thread in reversed(ed_threads):
            if (thread['category'] != "Assignments" or
               thread['type'] != "question"):
                # Check to see if the post is actually a question related to
                # assignments
                continue

            ed_thread_id = str(thread['id'])
            if ed_thread_id in server_threads and thread['is_answered']:
                # If we've already posted about it, resolve if answered
                logging.info(f"Closing thread {ed_thread_id} with channel " +
                             f"id {server_threads[ed_thread_id]}")
                await DiscordHelper.resolve_thread(
                    bot, database, guild_id, ed_thread_id, "Resolved on Ed"
                )
                continue
            if thread['is_answered']:
                # Thread has already been answered
                continue
            if ed_thread_id in server_threads:
                # Thread has already been pulled into discord
                continue
            # if today - EdHelper.parse_datetime(thread['created_at']) < delay_delta:  # noqa: E501
                # Hasn't been enough delay since initial posting
                # continue

            logging.info(f"Creating thread for guild {guild} with id " +
                         f"{thread['id']}")
            # Create a thread with appropriate title and message
            course = database.get_course(guild_id)
            starting_message = DiscordHelper._format_backreading_embed(
                thread, course, simple=True
            )
            created_thread = await DiscordHelper.create_thread(
                channel, starting_message, thread['title']
            )

            # Create detailed message so starting message can be deleted after
            embed = DiscordHelper._format_backreading_embed(
                thread, course, simple=False
            )
            await send_message(created_thread, embed)

            # Ping so it appears on the left, but delete after
            ping = await created_thread.send(DiscordHelper.get_role(
                guild, database.get_role(guild_id)).mention
            )
            await ping.delete()

            # Add thread id to guild_info
            database.add_thread(guild_id, ed_thread_id, created_thread.id)
            logging.info(f"Thread created for guild {guild} and added to " +
                         "database")
