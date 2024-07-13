import asyncio
import json
import requests
from base64 import b64decode
import discord
from discord import app_commands
from pavlov import PavlovRCON

# Load configuration
with open('config.json') as config_file:
    config = json.load(config_file)

api_url = f'https://api.github.com/repos/{config["github_username"]}/{config["repo_name"]}/contents/{config["file_path"]}'
access_token = config["access_token"]
log_channel_id = config["log_channel_id"]

# Load server details from JSON file
with open('servers.json') as f:
    servers = json.load(f)

player_stats = {}

def get_server_details(server_name):
    return servers.get(server_name)

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

async def update_player_stats():
    global player_stats
    while True:
        for server_name, server_details in servers.items():
            response = await send_pavlov_command(server_details['ip'], server_details['port'], server_details['password'], "RefreshList")
            if response:
                try:
                    player_list_data = json.loads(response)
                    player_list = player_list_data.get('PlayerList', [])
                    for player in player_list:
                        username = player['Username']
                        if username not in player_stats:
                            player_stats[username] = {
                                "Kills": 0,
                                "Deaths": 0,
                                "KD": 0.0
                            }
                        player_stats[username]["Kills"] += player.get("Kills", 0)
                        player_stats[username]["Deaths"] += player.get("Deaths", 0)
                        if player_stats[username]["Deaths"] > 0:
                            player_stats[username]["KD"] = player_stats[username]["Kills"] / player_stats[username]["Deaths"]
                        else:
                            player_stats[username]["KD"] = player_stats[username]["Kills"]
                except json.JSONDecodeError:
                    print("Failed to parse player list response.")
        await asyncio.sleep(60)

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

async def setup_leaderboard_commands(bot):
    @bot.tree.command(name="leaderboard", description="Get the leaderboard for a specific category")
    @app_commands.describe(category="The category for the leaderboard (Kills, KD)")
    async def leaderboard(interaction: discord.Interaction, category: str):
        await log_command(interaction, "leaderboard", {"category": category})

        if category not in ["Kills", "KD"]:
            await interaction.response.send_message("Invalid category. Please choose either 'Kills' or 'KD'.", ephemeral=True)
            return

        sorted_stats = sorted(player_stats.items(), key=lambda x: x[1][category], reverse=True)[:10]

        embed = discord.Embed(title=f"Leaderboard - {category}", color=discord.Color.gold())
        for i, (username, stats) in enumerate(sorted_stats, start=1):
            embed.add_field(name=f"{i}. {username}", value=f"{category}: {stats[category]}", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
