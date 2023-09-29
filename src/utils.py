import discord
import asyncio
import csv
from exceptions import (
    TimeoutError, InvalidResponse
)
from constants import (
    GREEN_CHECK, RED_X, EMPTY_SQUARE, FULL_SQUARE, BAR_SIZE
)
from html_constants import (
    HTML_ROW, HTML_HREF, HTML_TABLE, HTML_HEADER, HTML_STYLE
)

def correct_user_check(message, ctx):
    """
    Checks if the sender of the 'message' matches that of the original 'ctx' creator
    (aka if this is the correct person to be responding to the bot)
    """
    return (message.author == ctx.author and
            message.channel == ctx.channel)

def dm_check(message, ctx):
    """
    Checks if the sender of 'message' matches that of the original 'ctx' creator and
    that the response was given in a DM
    """
    return (message.author == ctx.author and
            isinstance(message.channel, discord.DMChannel))

def reaction_check(message, admin, reaction, user):
    """
    """
    emoji = str(reaction.emoji)
    return (reaction.message.id == message.id and user.id == admin.id and
           (emoji == GREEN_CHECK or emoji == RED_X))

async def send_message(channel, message, embed=None):
    """
    Sends the 'message' to 'channel' using embed format
    """
    return await channel.send(
        embed=embed if embed else discord.Embed(description=message)
    )

async def repeat_request(bot, auth_check, valid_check, timeout, send_invalid_message):
    """
    Repeats the same request multiple times using 'bot' until a valid response is achieved determined
    by 'check' or the 'timeout' time is reached. 'send_message' should be a functions preloaded with
    the appropriate error message to send on a bad response
    """
    try:
        result = (await bot.wait_for('message', check=auth_check, timeout=timeout)).content
        parsed_result = valid_check(result)
        return result, parsed_result
    except asyncio.TimeoutError:
        raise TimeoutError
    except InvalidResponse:
        await send_invalid_message()
        return await repeat_request(bot, auth_check, valid_check, timeout, send_invalid_message)

async def y_n_emoji(bot, respond_function, respond_message, admin, timeout):
    """
    """
    embed = discord.Embed(title="Yes or no?", description=respond_message)
    message = await respond_function(embed=embed)

    await message.add_reaction(GREEN_CHECK)
    await message.add_reaction(RED_X)

    def reaction_check(reaction, user):
        emoji = str(reaction.emoji)
        return (reaction.message.id == message.id and user.id == admin.id and
               (emoji == GREEN_CHECK or emoji == RED_X))

    try:
        reaction, _ = await bot.wait_for(event='reaction_add', check=reaction_check, timeout=timeout)
        return str(reaction.emoji) == GREEN_CHECK
    except asyncio.TimeoutError:
        raise TimeoutError

def invert_csv(csv_file):
    id_to_ta = {}
    for line in csv_file.splitlines():
        values = line.split(',')
        id_to_ta[values[1]] = values[0]
    return id_to_ta

def write_csv(file_path, header, data):
    with open(file_path, 'w') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(header)
        csvwriter.writerows(data)

def convert_csv_to_html(csv_file, html_file):
    with open('output.csv', newline='\n') as csv_file:
        rows = []
        one = False
        last_ta = ""
        for row in csv.DictReader(csv_file):
            if last_ta != "" and row['TA'] != last_ta:
                one = not one

            last_ta = row['TA']
            rows.append(HTML_ROW.format(row['TA'], HTML_HREF.format(row['Link']), row['Issue'],
                        "one" if one else "two"))
        
        output = HTML_TABLE % (HTML_HEADER.format('TA', 'Link', 'Issue'),"".join(rows))
        with open(html_file, 'w') as output_file:
            output_file.write(HTML_STYLE + output)

def progress_bar(current, total):
    empty = int(BAR_SIZE * (current / total))
    return (FULL_SQUARE * (empty)) + (EMPTY_SQUARE * (BAR_SIZE - empty))