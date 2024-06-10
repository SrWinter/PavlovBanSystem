# Discord Bot for Pavlov RCON Management

This repository contains a Discord bot that interacts with Pavlov servers using RCON. It allows for the management of bans, player lists, and other server commands through Discord messages.

## Features

- Ban and unban users across multiple Pavlov servers
- Log ban information to a GitHub repository
- Retrieve and display the ban list from servers
- Display the list of players on a specific server

## Setup

### Prerequisites

- Python 3.8 or higher
- Discord account and bot token
- GitHub personal access token
- Pavlov server RCON details

### Installation

1. Clone this repository:
    ```bash
    git clone https://github.com/yourusername/your-repo.git
    cd your-repo
    ```

2. Install required packages:
    ```bash
    pip install discord.py requests pavlov-rcon
    ```

3. Create a `servers.json` file with your server details:
    ```json
    {
      "Plap1": {
        "ip": "your_server_ip",
        "port": 3414,
        "password": "your_password"
      },
      "Plap2": {
        "ip": "your_server_ip",
        "port": 2383,
        "password": "your_password"
      }
    }
    ```

4. Replace the placeholders in `bot.py` with your actual information:
    - `allowed_channel_id`: The ID of the Discord channel where the bot will listen for commands.
    - `github_username`: Your GitHub username.
    - `repo_name`: The name of your GitHub repository.
    - `file_path`: The path to the file in your repository where ban information will be stored.
    - `access_token`: Your GitHub personal access token.
    - `bot.run('bot token')`: Your Discord bot token.

### Changing bot.py

- `allowed_channel_id`: Replace this value with the ID of the Discord channel where the bot should listen for commands.
- `github_username`: Your GitHub username.
- `repo_name`: The name of your GitHub repository.
- `file_path`: The path to the file in your repository where ban information will be stored.
- `access_token`: Your GitHub personal access token.
- `bot.run('bot token')`: Replace `'bot token'` with your Discord bot token.

### Running the Bot

Run the bot using Python:
```bash
python bot.py
