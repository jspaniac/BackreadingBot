import os, json, time, datetime, requests, asyncio, re, traceback
from datetime import time
import discord
from discord.ext import commands, tasks

intents = discord.Intents(messages=True, guilds=True, members=True, message_content=True, reactions=True)
bot = commands.Bot(command_prefix='!', intents=intents)

#-----------#
# CONSTANTS #
#-----------#

storage_dir = '../store'
db_file = 'database.json'   # File name for database
auth_file = 'auth.json'     # File name for auth

timeout = 45.0
min_delay = 0
thread_limit = 40
message_depth = 100

start_time = time(hour=9)
end_time = time(hour=22)

course_pattern = re.compile('https://edstem.org/us/courses/[0-9]+/discussion/')
num_pattern = re.compile('[0-9]+')

user_request = 'https://us.edstem.org/api/user'
thread_request = 'https://us.edstem.org/api/courses/{id}/threads'
thread_link = 'https://edstem.org/us/courses/{course_id}/discussion/{thread_id}'
post_request = 'https://us.edstem.org/api/threads/{thread_id}/comments'
accept_request = 'https://us.edstem.org/api/comments/{comment_id}/accept'


assignment_pattern = re.compile('https://edstem.org/us/courses/[0-9]+/lessons/[0-9]+/slides/[0-9]+')
slide_request = 'https://us.edstem.org/api/lessons/slides/{slide_id}'
challenge_request = 'https://us.edstem.org/api/challenges/{challenge_id}/users'

thread_name = "{author}: {title}"
ed_datetime_format = "%Y-%m-%dT%H:%M:%S.%f%z"

green_check = "\U00002705"
red_x = "\U0000274c"

#--------------------#
# Loading from files #
#--------------------#

guild_to_info = []
with open(os.path.join(storage_dir, db_file)) as guild_file:
    guild_to_info = json.load(guild_file)

#-------------------#
# BACKREAD COMMANDS #
#-------------------#

async def send_message(channel, message):
    await channel.send(embed=discord.Embed(description=message))

#-------------------------------------------------------------------#

@bot.command(name='br-setup', help="Setup the backreading bot, only available to grading-lead roles")
async def br_setup(ctx):
    def standard_check(message):
        return (message.author == ctx.author and
                message.channel == ctx.channel)
    
    try:
        # TODO: Make sure user is qualified
        
        # 0. get guild id
        if ctx.guild.id in guild_to_info:
            await send_message(ctx.channel, "Backreading bot already setup in this server. If you wish to reset the bot or reconfigure, try 'backreading-reset' instead!")
            return
        
        # 1. Store the user-id
        user = ctx.author.id

        # 2. Ask for ed token
        await send_message(ctx.channel, "The first step requires entering a valid ed token. For the sake of privacy, I'll ask in a DM")
        member = discord.utils.get(ctx.guild.members, id=user)
        await send_message(member, "What is your ed token? Note that this application will be using this token to read and respond to threads on the server you provide. If you're not comfortable with this, feel free to let the request timeout")

        user_response, token = await get_token(ctx, member)
        if user_response is None:
            return
        
        # 3. Get the url with checking
        await send_message(ctx.channel, "Now, provide the url of the discussion board for the ed course you wish the bot to connect to")

        course_id = await get_course(ctx, user_response, standard_check)
        if course_id is None:
            return
        
        # 4. Get delay
        await send_message(ctx.channel, f"Now provide the minutes the bot should wait before creating a thread after a post is made (>= {min_delay})")
        
        def check_delay(message):
            return (standard_check(message) and
                    num_pattern.fullmatch(message.content))
       
        delay = (await bot.wait_for('message', check=check_delay, timeout=timeout)).content
        delay = max(int(delay), min_delay)

        # 5. Get backreading role for pings
        await send_message(ctx.channel, "What is the name of your backreading role?")

        role_id = await get_role(ctx, standard_check)
        if role_id is None:
            return
        
        # 6. Get approval
        approval = await y_n_emoji(ctx.channel, 
                                   "Finally, do you want to manually approve responses before they are made on your account?",
                                   ctx.author, timeout)
                                
        await send_message(ctx.channel, f"Congrats! Your backreading bot is setup and running between the hours of {start_time}-{end_time}")

        # 7. Make the channel
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
            discord.utils.get(ctx.guild.roles, id=role_id): discord.PermissionOverwrite(read_messages=True, send_messages=False),
            discord.utils.get(ctx.guild.members, id=bot.user.id): discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel_id = (await ctx.guild.create_text_channel('backread-requests', overwrites=overwrites)).id

        # 8. Store it into the map that will be loaded into the json on shutdown
        guild_to_info[str(ctx.guild.id)] = {'admin': user,
                                            'channel': channel_id,
                                            'token': token,
                                            'course': course_id,
                                            'delay': delay,
                                            'role': role_id,
                                            'approval': approval,
                                            'threads': []}

        # TODO: What string will be present in all categories of backreading questions?
 
        # 9. Pull the threads since we probably aren't on a cycle perfectly
        await guild_threads(str(ctx.guild.id))
    except asyncio.TimeoutError:
        await send_message(ctx.channel, "Request timed out, try again by re-running backreading-setup")
    except Exception as e:
        print(e)

async def get_role(ctx, standard_check):
    try:
        role = (await bot.wait_for('message', check=standard_check, timeout=timeout)).content
        role = discord.utils.get(ctx.guild.roles, name=role)
        if role is not None:
            return role.id
        
        await send_message(ctx.channel, "Role with provided name does not exist. Please re-enter")
        return await get_role(ctx, standard_check)
    except asyncio.TimeoutError:
        await send_message(ctx.channel, "Request timed out, try again by re-running backreading-setup")
        return None

async def get_token(ctx, member):
    def check_token(message):
        return (message.author == ctx.author and 
                isinstance(message.channel, discord.DMChannel))
    
    try:
        token = (await bot.wait_for('message', check=check_token, timeout=timeout)).content
        user_response = get_response(user_request, token)
        ed_name = user_response['user']['name']
        
        await send_message(member, "I'd recommend deleting that message now jic")
        await send_message(member, f"The account name associated with the provided token is {ed_name}. Now let's move back to the server")
        return user_response, token
    except asyncio.TimeoutError:
        await send_message(member, "Request timed out")
        await send_message(ctx.channel, "Request timed out, try again by re-running backreading-setup")
        return None, None
    except Exception as e:
        await send_message(member, "Error with the provided ed token. Please try again")
        return await get_token(ctx, member)

async def get_course(ctx, user_response, standard_check):
    def check_course(message):
        return (standard_check(message) and
                course_pattern.fullmatch(message.content))
    
    try:
        course_url = (await bot.wait_for('message', check=check_course, timeout=timeout)).content
        course_id = int(re.findall('[0-9]+', course_url)[0])

        # Verify that they've entered the correct course
        for course in user_response['courses']:
            if course['course']['id'] == course_id:
                course_name = course['course']['code']
                break

        if course_name is None:
            await send_message(ctx.channel, "No valid ed course found for that link. Please try again")
        elif await y_n_emoji(ctx.channel, f"The course you provided is named {course_name}, is this correct?",
                             ctx.author, timeout):
            return course_id
        else:
            await send_message(ctx.channel, "Then please enter the correct link 💅")
    except asyncio.TimeoutError:
        await send_message(ctx.channel, "Request timed out, try again by re-running backreading-setup")
        return None
    except Exception as e:
        await send_message(ctx.channel, "An exception occured, please renter the discussion link")
    
    return await get_course(ctx, user_response, standard_check)

#-------------------------------------------------------------------#
       
@bot.command(name='br-stop', help="Stops the backreading functionality of the bot, removing all data stored")
async def br_stop(ctx):
    if str(ctx.guild.id) not in guild_to_info:
        await send_message(ctx.channel, "Backreading bot not setup for this server")
        return
    
    await discord.utils.get(ctx.guild.text_channels, id=guild_to_info[str(ctx.guild.id)]['channel']).delete()
    del guild_to_info[str(ctx.guild.id)]
    save()
    
    await send_message(ctx.channel, "Backreading bot stopped")

#-------------------------------------------------------------------#

@bot.command(name='br-push', help="Reply to the agreed on answer with this command to push it to ed")
async def br_push(ctx):
    try:
        if ctx.message.reference is None:
            await send_message(ctx.channel, "This command must be used in response to the answer you wish to push")
            return
        
        thread = discord.utils.get(ctx.guild.threads, id=ctx.channel.id)
        if thread is None or thread.owner != bot.user:
            await send_message(ctx.channel, "This command can only be used in a thread started by the intructor-bot")
            return

        guild_info = guild_to_info[str(ctx.guild.id)]
        
        # Double-checking w/ admin or sender
        checker = discord.utils.get(ctx.guild.members, id=guild_info['admin']) if guild_info['approval'] else ctx.author
        message = checker.mention + (" do you approve of this response?" if guild_info['approval'] 
                                        else " just as a double-check, is this the message you want to send?")

        if not await y_n_emoji(ctx.channel, message, checker, None):
            await send_message(ctx.channel, "Answer not approved")
            return

        starting_message = await thread.parent.fetch_message(thread.id)
        to_push = (await thread.fetch_message(ctx.message.reference.message_id)).content
        
        # result is [course_id, thread_id]
        ed_info = re.findall(num_pattern, starting_message.embeds[0].url)
        if push_answer(guild_info['token'], ed_info[1], to_push):
            await resolve_thread(ctx.guild, thread, guild_info, int(ed_info[1]), "Pushed to ed!")
        else:
            await send_message(ctx.channel, "Issue in pushing to Ed")
    except Exception as e:
        print(e)

async def resolve_thread(guild, thread, guild_info, ed_id, final_message):
    # Send final message
    await send_message(thread, final_message)
    # Archive thread
    await thread.archive()
    # Remove thread from guild_info
    guild_info['threads'].remove(ed_id)
    # Delete starting message
    channel = bot.get_channel(guild_info['channel'])
    await (await channel.fetch_message(thread.id)).delete()

# TODO: Fix the checkmark not appearing
def push_answer(token, thread_id, answer):
    try:
        payload =  {'comment': {'type': 'answer',
                                'content': f"<document version=\"2.0\"><paragraph>{answer}</paragraph></document>",
                                'is_private': False,
                                'is_anonymous': False}}

        r = post_payload(post_request.format(thread_id=thread_id), token, payload)

        # Don't wrap since ed doesn't give a response for accepting an answer
        requests.post(accept_request.format(comment_id=r['comment']['id']), headers={'x-token': token})
        return True
    except Exception as e:
        traceback.print_exc()
        print(e)
        return False

async def y_n_emoji(channel, content, admin, timeout):
    embed = discord.Embed(title="Yes or no?", description=content)
    message = await channel.send(embed=embed)
    
    await message.add_reaction(green_check)
    await message.add_reaction(red_x)
    
    def check_reaction(reaction, user):
        emoji = str(reaction.emoji)
        return (reaction.message.id == message.id and user.id == admin.id and
               (emoji == green_check or emoji == red_x))
    
    try:
        reaction, _ = await bot.wait_for(event='reaction_add', check=check_reaction, timeout=timeout)
        return str(reaction.emoji) == green_check
    except Exception as e:
        traceback.print_exc()
        return False

#-------------------------------------------------------------------#

@bot.command(name='br-pull', help="Pulls new threads from ed")
async def br_pull(ctx):
    # TODO: Double-check if they're sure if it's bad hours (will ping people)

    if await guild_threads(str(ctx.guild.id)):
        await send_message(ctx.channel, "Refreshed!")
    else:
        await send_message(ctx.channel, "Issue in refreshing")

async def guild_threads(guild_id):
    if guild_id not in guild_to_info:
        return False
    
    # jic it's needed: 'filter': 'unanswered'
    payload={'limit': thread_limit, 'sort': 'new'}
    today = datetime.datetime.now(datetime.timezone.utc)

    guild_info = guild_to_info[guild_id]
    guild = await bot.fetch_guild(int(guild_id))
    channel = await bot.fetch_channel(guild_info['channel'])
    
    delay_delta = datetime.timedelta(minutes=guild_info['delay'])
    
    response = get_response(url=thread_request.format(id=guild_info['course']),
                            token=guild_info['token'],
                            payload=payload)
    threads = response['threads']
    for thread in reversed(threads):
        # TODO: Maybe don't hardcode this part in
        if thread['category'] != "Assignments" or thread['type'] != "question":
            continue

        # If we've already posted about it, resolve if answered
        if thread['id'] in guild_info['threads'] and thread['is_answered']:
            # Find the starting message (let's hope it was < message_depth ago)
            link = thread_link.format(course_id=guild_info['course'], thread_id=thread['id'])
            message = discord.utils.find(lambda m: m.embeds[0].url == link, await channel.history(limit=message_depth).flatten())
            if message is not None:
                old_thread = bot.get_channel(message.id)
                await resolve_thread(guild, old_thread, guild_info, thread['id'], "Resolved on Ed")
            continue

        # Only care about the unanswered posts we haven't seen already
        if thread['is_answered'] or thread['id'] in guild_info['threads']:
            continue

        # For some reason, ed includes a : in the UTC offset
        splitted = thread['created_at'].rsplit(':', 1)
        time = datetime.datetime.strptime(splitted[0] + splitted[1], ed_datetime_format)
        
        # TODO: Uncomment this if wanted
        # if today - time < delay_delta:
        #     continue

        # Create a thread with appropriate title and message
        starting_message = discord.Embed(title=thread_name.format(author=thread['user']['name'], title=thread['title']),
                                         url=thread_link.format(course_id=guild_info['course'], thread_id=thread['id']))
        message = await channel.send(embed=starting_message)
        created_thread = await message.create_thread(name=thread['title'])

        # Create detailed message so starting message can be deleted after
        embed = discord.Embed(title=thread_name.format(author=thread['user']['name'], title=thread['title']),
                              url=thread_link.format(course_id=guild_info['course'], thread_id=thread['id']),
                              description=thread['document'],
                              timestamp=time)
        name = thread['category'] 
        if thread['subcategory'] != "":
            name += " - " + thread['subcategory']
        embed.set_author(name=name)
        await created_thread.send(embed=embed)

        # Ping so it appears on the left, but delete after
        ping = await created_thread.send(discord.utils.get(guild.roles, id=guild_info['role']).mention)
        await ping.delete()

        # Add thread id to guild_info
        guild_info['threads'].append(thread['id'])
        save()

        # TODO: Comment on ed that it was pulled into discord
    
    return True

#------------------#
# GRADING FINISHED #
#------------------#

# TODO: I think there are still some bugs here :(
@bot.command(name='gr-check', help="Checks to see if TAs are done grading. Call with submissions link")
async def gr_check(ctx, submission_link):
    try:
        if not assignment_pattern.fullmatch(submission_link):
            send_message(ctx.channel, "Provided link is invalid, try again")
        
        token = guild_to_info[str(ctx.guild.id)]['token']
        
        # [course, lessons, slides]
        ids = re.findall(num_pattern, submission_link)
        slide = get_response(slide_request.format(slide_id=ids[2]), token, {'view': 1})['slide']
        challenge_id = slide['challenge_id']
        users = get_response(challenge_request.format(challenge_id=challenge_id), token)['users']

        section_to_ungraded = {}
        total_ungraded = 0
        for user in users:
            section = user['tutorial']

            if section is None:
                continue
            
            if section not in section_to_ungraded:
                section_to_ungraded[section] = 0
            
            if user['completed'] and user['feedback_status'] != "complete":
                section_to_ungraded[section] += 1
                total_ungraded += 1
        
        embed = discord.Embed(title=slide['title'],
                              description="Report of students with uncomplete feedback")
        for section in section_to_ungraded:
            embed.add_field(name=section, value=section_to_ungraded[section])

        await ctx.channel.send(embed=embed)

        if total_ungraded == 0:
            await send_message(ctx.channel, "All clear!")
        else:
            await send_message(ctx.channel, f"{total_ungraded} students still ungraded")
    except Exception as e:
        await send_message(ctx.channel, "Issue accessing ed resources")
        print(e)

#-------#
# TASKS #
#-------#

@tasks.loop(seconds=min_delay*60)
async def pull_threads():
    now = datetime.datetime.now().time()
    
    # if (now < start_time or now > end_time):
    #     return
    
    try:
        for guild_id in guild_to_info.keys():
            await guild_threads(guild_id)
    except Exception as e:
        traceback.print_exc(e)

#-----------------#
# REQUEST HELPERS #
#-----------------#

def get_response(url, token, payload={}):
    return requests.get(url=url, params=payload, headers={'Authorization': 'Bearer ' + token}).json()

def post_payload(url, token, payload={}):
    return requests.post(url=url, json=payload, headers={'Authorization': 'Bearer ' + token}).json()

# Prints out when the bot is up and running!
@bot.event
async def on_connect():
    print("Bot finished loading external files!")
    pull_threads.start()

# Saves database with updated scores
@bot.event
async def close():
    save()

def save():
    with open(os.path.join(storage_dir, db_file), "w") as db:
        db.write(json.dumps(guild_to_info))

auth = json.load(open(os.path.join(storage_dir, auth_file)))
TOKEN = auth['token']
bot.run(TOKEN)