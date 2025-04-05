import discord
from discord.ext import commands, tasks
import requests
import json
from base64 import b64decode, b64encode
from datetime import datetime, date
import asyncio
from commands import setup_commands, get_server_details, send_pavlov_command
from leaderboardcmd import setup_leaderboard_commands, update_player_stats

# Load configuration
with open('config.json') as config_file:
    config = json.load(config_file)

# Discord bot setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Constants
allowed_channel_id = config["allowed_channel_id"]
github_username = config["github_username"]
repo_name = config["repo_name"]
file_path = config["file_path"]
access_token = config["access_token"]
api_url = f'https://api.github.com/repos/{github_username}/{repo_name}/contents/{file_path}'
bot_status = config.get("bot_status", "Online")
bot_version = config.get("bot_version", "1.0.0")
log_channel_id = config["log_channel_id"]

# Load server details from JSON file
with open('servers.json') as f:
    servers = json.load(f)

# Functions
async def update_github_file(api_url, content, commit_message):
    response = requests.get(api_url, headers={'Authorization': f'token {access_token}'})
    data = response.json()

    if 'sha' not in data or 'url' not in data:
        print("Failed to fetch file details from GitHub.")
        return

    update_url = data['url']
    sha = data['sha']

    data = {
        'message': commit_message,
        'content': b64encode(json.dumps(content, indent=4).encode('utf-8')).decode('utf-8'),
        'sha': sha,
    }

    response = requests.put(update_url, headers={'Authorization': f'token {access_token}'}, json=data)
    print(response.text)

async def log_to_console(message):
    print(message)

async def log_command(interaction, command_name, args):
    log_channel = interaction.guild.get_channel(log_channel_id)
    if log_channel:
        embed = discord.Embed(title="Command Used", color=discord.Color.blue())
        embed.add_field(name="User", value=interaction.user.mention, inline=True)
        embed.add_field(name="Command", value=command_name, inline=True)
        embed.add_field(name="Arguments", value=str(args), inline=True)
        embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
        embed.add_field(name="Timestamp", value=interaction.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        await log_channel.send(embed=embed)

@tasks.loop(minutes=1)
async def check_bans():
    response = requests.get(api_url, headers={'Authorization': f'token {access_token}'})
    if response.status_code != 200:
        return

    data = response.json()
    if 'content' not in data:
        return

    try:
        raw_content = b64decode(data['content']).decode('utf-8')
        banned_users = json.loads(raw_content)
    except Exception:
        return

    current_date = date.today()
    users_to_unban = []

    for user, details in banned_users.items():
        banned_until = parse_date(details.get('banneduntil'))
        if banned_until and current_date >= banned_until:
            for server_name in servers:
                server_details = get_server_details(server_name, servers)
                if server_details:
                    await send_pavlov_command(
                        server_details['ip'],
                        server_details['port'],
                        server_details['password'],
                        f"unban {user}"
                    )
            users_to_unban.append(user)

    if users_to_unban:
        for user in users_to_unban:
            banned_users.pop(user, None)

        commit_message = f"Unbanned: {', '.join(users_to_unban)}"
        await update_github_file(api_url, banned_users, commit_message)

def parse_date(date_str):
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None

@bot.event
async def on_ready():
    await log_to_console(f'{len(bot.tree.get_commands())} Commands Synced with Discord')
    await log_to_console('Ban Manager Watching')
    await log_to_console('Bot is Online')

    check_bans.start()
    asyncio.create_task(update_player_stats())

    await bot.change_presence(activity=discord.Game(name=f"{bot_status} v{bot_version}"))

    try:
        synced = await bot.tree.sync()
        print(f'Successfully synced {len(synced)} commands with Discord.')
    except Exception as e:
        print(f'Failed to sync commands: {e}')
        await log_to_console('Warning: Syncing commands failed. Use /debug for more information.')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id == allowed_channel_id:
        if message.content.count('\n') == 2:
            author_name, current_date, ban_reason = map(str.strip, message.content.split('\n'))
            await log_message_to_github(author_name, current_date, ban_reason, message.channel)
            await ban_user_on_all_servers(author_name)
        else:
            await message.channel.send("Invalid format. Please use:\nName\nDate\nReason")

    await bot.process_commands(message)

async def log_message_to_github(author_name, current_date, ban_reason, message_channel):
    response = requests.get(api_url, headers={'Authorization': f'token {access_token}'})
    data = response.json()

    if 'content' in data:
        try:
            raw_content = b64decode(data['content']).decode('utf-8')
            messages = json.loads(raw_content)
        except json.JSONDecodeError:
            messages = {}
    else:
        messages = {}

    messages[author_name] = {
        'banneduntil': current_date,
        'BanReason': ban_reason
    }

    commit_message = f"Ban: {author_name} until {current_date} - {ban_reason}"
    await update_github_file(api_url, messages, commit_message)

    await message_channel.send(f"Banned:\nName: {author_name}\nDate: {current_date}\nReason: {ban_reason}")

async def ban_user_on_all_servers(username):
    ban_command = f"ban {username}"
    for server_name, server_details in servers.items():
        await send_pavlov_command(server_details['ip'], server_details['port'], server_details['password'], ban_command)

async def setup(bot):
    await setup_commands(bot, servers, api_url, access_token)
    await setup_leaderboard_commands(bot)

async def main():
    await setup(bot)
    await bot.start(config['discord_bot_token'])

asyncio.run(main())
