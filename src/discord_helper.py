import discord
import logging
import re
import requests
from utils import (
    send_message, repeat_request, dm_check, correct_user_check, y_n_emoji
)
from constants import (
    TIMEOUT, LOGGING_FILE, ASSIGNMENT_GRACE_MINUTES, THREAD_NAME, THREAD_LINK,
)
from exceptions import (
    TimeoutError, InvalidResponse
)

from ed_helper import EdHelper
from datetime import datetime

logging.basicConfig(filename=LOGGING_FILE, encoding='utf-8', level=logging.INFO)

class DiscordRegex:
    URL_REGEX = re.compile(
        r"https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/=]*)")

class DiscordHelper:
    @staticmethod
    def get_attachment(url):
        return requests.get(url).content.decode('utf-8') if url else None

    @staticmethod
    async def create_channel(guild, name, overwrites):
        return (await guild.create_text_channel(name, overwrites=overwrites)).id
    
    @staticmethod
    async def create_thread(channel, starting_message, thread_name):
        message = await send_message(channel, starting_message)
        return await message.create_thread(thread_name)

    @staticmethod
    async def get_role(guild, role_id):
        return discord.utils.get(guild.roles, id=role_id)
    
    @staticmethod
    async def resolve_thread(bot, thread, database, guild_id, thread_id, final_message):
        logging.debug(f"Resolving thread {thread}")
        # Send final message
        await send_message(thread, final_message)
        # Archive thread
        await thread.archive()
        # Remove thread from guild_info
        database.remove_thread(guild_id, thread_id)
        # Delete starting message
        channel = bot.get_channel(database.get_channel(guild_id))
        await (await channel.fetch_message(thread.id)).delete()

    @staticmethod
    async def _get_token(bot, respond_dm):
        """
        """
        async def invalid_wrapper():
            """
            """
            await respond_dm("""Error with the provided ed token. Please try again""")

        try:
            token, user = await repeat_request(bot, dm_check, EdHelper.check_token, TIMEOUT, invalid_wrapper)
            logging.debug(f"Successfully retrived valid ed token {token}, username {user['name']}")
            await respond_dm("""I'd recommend deleting that message now jic""")
            await respond_dm(f"""The account name associated with the provided token is {user['name']}. Now let's move back to the server""")
            return token, user
        except TimeoutError:
            await respond_dm("""Request timed out""")
            raise TimeoutError
    
    @staticmethod
    async def _get_course(bot, respond_public_channel, ed_user, discord_user):
        """
        """
        async def invalid_wrapper():
            """
            """
            await respond_public_channel("""No valid ed course found for that link. Please try again""")

        async def check_course_wrapper(url):
            """
            """
            return EdHelper.valid_course_for_user(url, ed_user)

        while True:
            url, course = await repeat_request(bot, correct_user_check, check_course_wrapper, TIMEOUT, invalid_wrapper)
            logging.debug(f"Successfully retrieved course from url {url}, name {course['code']}")
            if await y_n_emoji(
                bot, respond_public_channel,
                f"""The course you provided is named {course['code']}, is this correct?""",
                discord_user, TIMEOUT
            ):
                return course
            else:
                respond_public_channel("""Then please enter the correct link 💅""")
    
    @staticmethod
    async def _get_role(bot, respond_public_channel, roles):
        """
        """
        async def invalid_wrapper():
            """
            """
            await respond_public_channel("""""Role with provided name does not exist. Please re-enter""")
        
        async def valid_role_check(role):
            """
            """
            role = discord.utils.get(roles, name=role)
            if role is None:
                raise InvalidResponse
            return role

        role_name, role = await repeat_request(bot, correct_user_check, valid_role_check, TIMEOUT, invalid_wrapper)
        logging.debug(f"Successfully retrieved role with id {role.id} from name {role_name}")
        return role_name, role

    @staticmethod
    async def setup_bot(ctx, database, bot):
        """
        """
        requester = discord.utils.get(ctx.guild.members, id=user)
        async def respond_dm(message):
            """
            Sends 'message' to the dm of the user that originated the request
            """
            await send_message(requester, message)

        async def respond_public_channel(message):
            """
            Sends 'message' to the same channel as the original message was sent in
            """
            await send_message(ctx.channel, message)

        try:
            # 1. Store the user-id
            user = ctx.author.id

            # 2. Ask for ed token
            await respond_public_channel("""The first step requires entering a valid ed token. For the
                    sake of privacy, I'll ask in a DM""")
            await respond_dm("""What is your ed token? Note that this application will be using this token
                    to read and respond to threads on the server you provide. If you're not comfortable
                    with this, feel free to let the request timeout""")
            token, ed_user = await DiscordHelper._get_token(bot, respond_dm)

            # 3. Get the url with checking
            await respond_public_channel("""Now, provide the url of the discussion board for the ed course
                    you wish the bot to connect to"""
            )
            course = await DiscordHelper._get_course(bot, respond_public_channel, ed_user, ctx.author)

            # 4. Get backreading role for pings
            logging.info("Retrieving backreading role")
            await respond_public_channel("""What is the name of your backreading role?""")
            role_name, role = await DiscordHelper._get_role(bot, respond_public_channel, ctx.guild.roles)

            # 5. Get approval
            approval = await y_n_emoji(
                bot, respond_public_channel,
                "Finally, do you want to manually approve responses before they are made on your account?",
                ctx.author, TIMEOUT
            )
            
            # 6. Make the channel
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
                role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
                discord.utils.get(ctx.guild.members, id=bot.user.id): discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            channel_id = DiscordHelper.create_channel(ctx.guild, 'backread-requests', overwrites)
            
            # 7. Store it into the map that will be loaded into the json on shutdown
            database.register(str(ctx.guild.id), GuildInfo(user, channel_id, token, course['id'], role.id, approval))
            database.save()

            await send_message(ctx.channel, f"Congrats! Your backreading bot is setup and running!")
        except TimeoutError:
            logging.debug("Request timed out")
        except Exception as e:
            logging.exception(e)
    
    @staticmethod
    async def stop_bot(ctx, database):
        """
        """
        guild_id = ctx.guild.id
        await discord.utils.get(ctx.guild.text_channels, id=database.get_channel(guild_id)).delete()
        database.delete(guild_id)

        await send_message(ctx.channel, "Backreading bot stopped")
    
    @staticmethod
    async def push_ed_response(ctx, database, bot, thread):
        """
        """
        async def respond_thread(message):
            """
            """
            await send_message(ctx.channel, message)

        guild_id = ctx.guild.id
        ed_helper = EdHelper(database.get_token(guild_id))

        # Double-checking w/ admin or sender
        checker = discord.utils.get(ctx.guild.members, id=database.get_admin(guild_id)) if database.get_approval(guild_id) else ctx.author
        message = checker.mention + (" do you approve of this response?" if database.get_approval(guild_id) else
                                    " just as a double-check, is this the message you want to send?")

        if not await y_n_emoji(bot, respond_thread, message, checker, TIMEOUT):
            await respond_thread("Answer not approved")
            return

        starting_message = await thread.parent.fetch_message(thread.id)
        to_push = (await thread.fetch_message(ctx.message.reference.message_id)).content
        course_thread_ids = EdHelper.get_ids(starting_message.embeds[0].url)
        if ed_helper.push_answer(course_thread_ids[1], to_push):
            await DiscordHelper.resolve_thread(bot, thread, database, ctx.guild.id, int(course_thread_ids[1]), "Pushed to Ed!")
        else:
            await send_message(ctx.channel, "Issue in pushing to Ed")

    @staticmethod
    def _format_backreading_embed(thread, course_id, simple=False):
        time = EdHelper.parse_datetime(thread['created_at'])
        if simple:
            return discord.Embed(title=THREAD_NAME.format(author=thread['user']['name'], title=thread['title']),
                                 url=THREAD_LINK.format(course_id=course_id, thread_id=thread['id']))
        else:
            # Replace the link for FERPA reasons
            embed = discord.Embed(title=THREAD_NAME.format(author=thread['user']['name'], title=thread['title']),
                                  url=THREAD_LINK.format(course_id=course_id, thread_id=thread['id']),
                                  description=re.sub(DiscordRegex.URL_REGEX, "Link on original post [removed for FERPA]", thread['document']),
                                  timestamp=time)
            embed.set_author(name=thread['category'] + (" - " + thread['subcategory'] if thread['subcategory'] != "" else ""))
            return embed

    @staticmethod
    async def refresh_threads(guild_id, database, bot):
        # jic it's needed: 'filter': 'unanswered'
        guild = await bot.fetch_guild(int(guild_id))
        channel = await bot.fetch_channel(database.get_channel(guild_id))

        today = datetime.datetime.now(datetime.timezone.utc)
        delay_delta = datetime.timedelta(minutes=ASSIGNMENT_GRACE_MINUTES)

        ed_helper = EdHelper(database.get_token(guild_id))
        threads = ed_helper.get_threads(database.get_course(guild_id))
        for thread in reversed(threads):
            if thread['category'] != "Assignments" or thread['type'] != "question":
                # Check to see if the post is actually a question related to assignments
                continue

            thread_id = str(thread['id'])
            threads = database.get_threads(guild_id)
            if thread_id in threads and thread['is_answered']:
                # If we've already posted about it, resolve if answered
                logging.info(f"Closing thread {thread_id} with channel id {threads[thread_id]}")
                old_thread = bot.get_channel(threads[thread_id])
                await DiscordHelper.resolve_thread(bot, old_thread, database, guild_id, old_thread, "Resolved on Ed")
                continue
            if thread['is_answered']:
                # Thread has already been answered
                continue
            if thread_id in threads:
                # Thread has already been pulled into discord
                continue
            if today - EdHelper.parse_datetime(thread['created_at']) < delay_delta:
                # Hasn't been enough delay since initial posting
                continue

            logging.info(f"Creating thread for guild {guild} with id {thread['id']}")
            # Create a thread with appropriate title and message
            course = database.get_course(guild_id)
            starting_message = DiscordHelper._format_backreading_embed(thread, course, simple=True)
            created_thread = DiscordHelper.create_thread(channel, starting_message, thread['title'])
            
            # Create detailed message so starting message can be deleted after
            embed = DiscordHelper._format_backreading_embed(thread, course, simple=False)
            await send_message(created_thread, embed)

            # Ping so it appears on the left, but delete after
            ping = await created_thread.send(DiscordHelper.get_role(guild, database.get_role(guild_id)).mention)
            await ping.delete()

            # Add thread id to guild_info
            database.add_thread(guild_id, thread_id, created_thread.id)