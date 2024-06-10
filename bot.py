import discord
from discord.ext import commands, tasks
import requests
import json
from base64 import b64decode, b64encode
from datetime import datetime, date
import asyncio
from pavlov import PavlovRCON

# Discord bot setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Constants
allowed_channel_id = 124006248132309867  # channel id
github_username = 'UserName'  # github username
repo_name = 'RepoName'  # repo name
file_path = 'FileName'  # file to store bans
access_token = 'Token'  # access token
api_url = f'https://api.github.com/repos/{github_username}/{repo_name}/contents/{file_path}'  # DO NOT TOUCH

# Load server details from JSON file
with open('servers.json') as f:
    servers = json.load(f)

# Functions
async def update_github_file(api_url, content, commit_message):
    response = requests.get(api_url)
    data = json.loads(response.content.decode('utf-8'))

    url = data.get('url', '')
    sha = data.get('sha', '')

    update_url = f'{url}?access_token={access_token}'

    data = {
        'message': commit_message,
        'content': b64encode(json.dumps(content, indent=4).encode('utf-8')).decode('utf-8'),
        'sha': sha,
    }

    response = requests.put(update_url, headers={'Authorization': f'token {access_token}'}, json=data)
    print(response.text)

# Check bans every minute
@tasks.loop(minutes=1)
async def check_bans():
    response = requests.get(api_url)

    if response.status_code == 200:
        data = json.loads(response.content.decode('utf-8'))

        if 'content' in data:
            raw_content = b64decode(data['content']).decode('utf-8')
            print("Raw Content:", raw_content)

            try:
                banned_users = json.loads(raw_content)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON content: {e}")
                return
        else:
            print("No 'content' field found in data:", data)
            return
    else:
        print("Failed to retrieve data from GitHub API. Status code:", response.status_code)
        return

    current_date = date.today()

    if not banned_users:
        print("No banned users found.")
        return

    users_to_unban = []
    for user, details in banned_users.items():
        banned_until = parse_date(details.get('banneduntil'))
        if banned_until and current_date >= banned_until:
            # Unban the player via PavlovRCON for all servers
            for server_name in servers:
                server_details = get_server_details(server_name)
                if server_details:
                    unban_command = f"unban {user}"
                    await send_pavlov_command(server_details['ip'], server_details['port'], server_details['password'], unban_command)
            users_to_unban.append(user)

    if users_to_unban:
        # Remove users from the JSON data
        for user in users_to_unban:
            del banned_users[user]

        # Update ban.json on GitHub
        commit_message = f"Users unbanned as their ban time expired: {', '.join(users_to_unban)}"
        await update_github_file(api_url, banned_users, commit_message)

async def send_pavlov_command(host, port, password, command):
    try:
        pavlov = PavlovRCON(host, port, password)
        task = asyncio.create_task(pavlov.send(command))
        response = await task
        print(f"Pavlov response: {response}")
        return response if isinstance(response, str) else json.dumps(response)
    except Exception as e:
        print(f"Failed to send Pavlov command: {e}")
        return None

def get_server_details(server_name):
    return servers.get(server_name)

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        try:
            return datetime.strptime(date_str, '%d-%m-%Y').date()
        except ValueError:
            try:
                return datetime.strptime(date_str, '%Y/%m/%d').date()
            except ValueError:
                print(f"Failed to parse date: {date_str}")
                return None

# Events
@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user.name}')
    check_bans.start()  # Start the check_bans task when the bot is ready

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.channel.id == allowed_channel_id:
        if message.content.count('\n') == 2:
            author_name, current_date, ban_reason = map(str.strip, message.content.split('\n'))
            await log_message_to_github(author_name, current_date, ban_reason, message.channel)
            await ban_user_on_all_servers(author_name)
        else:
            await message.channel.send("Invalid format. Please use the format:\nName\nDate\nReason")

    await bot.process_commands(message)

# Bot commands
async def log_message_to_github(author_name, current_date, ban_reason, message_channel):
    response = requests.get(api_url)
    data = json.loads(response.content.decode('utf-8'))

    if 'content' in data:
        try:
            raw_content = b64decode(data['content']).decode('utf-8')
            messages = json.loads(raw_content)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from GitHub: {e}")
            messages = {}
    else:
        messages = {}

    messages[author_name] = {'banneduntil': current_date, 'BanReason': ban_reason}

    commit_message = f"User {author_name} banned until {current_date} for reason: {ban_reason}"
    await update_github_file(api_url, messages, commit_message)

    await message_channel.send(f"Message received and processed:\nName: {author_name}\nDate: {current_date}\nReason: {ban_reason}")

async def ban_user_on_all_servers(username):
    ban_command = f"ban {username}"
    for server_name, server_details in servers.items():
        print(f"Sending ban command to {server_name}: {ban_command}")
        await send_pavlov_command(server_details['ip'], server_details['port'], server_details['password'], ban_command)

# New command to get the ban list
@bot.command(name='banlist')
async def banlist(ctx, server_name: str):
    server_details = get_server_details(server_name)
    if not server_details:
        await ctx.send(f"Server '{server_name}' not found.")
        return

    response = await send_pavlov_command(server_details['ip'], server_details['port'], server_details['password'], 'banlist')
    if response:
        try:
            # Parse the JSON response
            ban_data = json.loads(response)

            # Extract the list of banned players
            banned_players = ban_data.get('BanList', [])

            # Create a formatted text block for the banned players
            ban_list_text = "```"
            ban_list_text += "\n".join(banned_players)
            ban_list_text += "```"

            await ctx.send(ban_list_text)
        except json.JSONDecodeError:
            await ctx.send("Failed to parse ban list response.")
    else:
        await ctx.send(f"Failed to retrieve ban list for {server_name}.")

# New command to list players on a specific map
@bot.command(name='players')
async def players(ctx, server_name: str):
    # Call the function to get the list of players on the specified map
    player_list_response = await get_players_on_server(server_name)

    print("Player list response:", player_list_response)  # Debug print

    if player_list_response:
        try:
            # Parse the response from Pavlov server
            player_list_data = json.loads(player_list_response)

            # Extract the list of players
            player_list = player_list_data.get('PlayerList', [])

            if player_list:
                # Calculate the number of players
                num_players = len(player_list)

                # Format the response for Discord
                formatted_player_list = ""
                for player in player_list:
                    formatted_player_list += f"{player['Username']}\n"

                response_message = f"Current Players on {server_name} ({num_players} out of 24):\n```{formatted_player_list}```"
                await ctx.send(response_message)
            else:
                await ctx.send(f"No players currently on server '{server_name}'.")
        except json.JSONDecodeError:
            await ctx.send("Failed to parse player list response.")
    else:
        await ctx.send(f"Failed to retrieve player list for server '{server_name}'.")

# Function to get the list of players on a specific server
async def get_players_on_server(server_name):
    # Your code to retrieve the list of players on the specified server goes here
    # For example, you might send a command to the game server using PavlovRCON
    players_command = f"RefreshList {server_name}"
    server_details = get_server_details(server_name)
    if server_details:
        print(f"Sending player list command to {server_name}: {players_command}")
        response = await send_pavlov_command(server_details['ip'], server_details['port'], server_details['password'], players_command)
        return response
    else:
        print(f"Server '{server_name}' not found.")
        return None

    kick_command = f"kick {player_name}"
    response = await send_pavlov_command(server_details['ip'], server_details['port'], server_details['password'], kick_command)
    if response:
        await ctx.send(f"Player {player_name} kicked from {server_name}.\nResponse: {response}")
    else:
        await ctx.send(f"Failed to kick player {player_name} from {server_name}.")

bot.run('bot token')
