import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import json
import os
from typing import Optional

# Disable voice features to avoid audioop dependency
import sys
if sys.version_info >= (3, 13):
    discord.voice_client = None

# Bot setup
intents = discord.Intents.default()
intents.voice_states = False
bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

# Config storage
CONFIG_FILE = 'bot_config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

async def fetch_token(session, uid, password):
    url = f"https://jwt-token-flame.vercel.app/token?uid={uid}&password={password}"
    try:
        async with session.get(url, timeout=10) as resp:
            data = await resp.json()
            if data.get('status') == 'success' and data.get('token'):
                return {"uid": str(uid), "token": data['token']}
    except:
        pass
    return None

@bot.event
async def on_ready():
    await tree.sync()
    print(f'Logged in as {bot.user}')

@tree.command(name="setup", description="Set the output channel for JWT results")
@app_commands.describe(channel="Text channel to post results")
async def setup(interaction: discord.Interaction, channel: discord.TextChannel):
    config = load_config()
    config[str(interaction.guild_id)] = {"channel_id": channel.id}
    save_config(config)
    await interaction.response.send_message(f"Setup complete. Output channel: {channel.mention}", ephemeral=True)

@tree.command(name="jwt", description="Upload accounts JSON to generate tokens")
@app_commands.describe(file="Accounts JSON file")
async def jwt(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer(ephemeral=True)
    
    try:
        content = await file.read()
        accounts = json.loads(content.decode('utf-8'))
        
        if not isinstance(accounts, list):
            await interaction.followup.send("Invalid JSON. Expected an array of accounts.")
            return
        
        results = []
        async with aiohttp.ClientSession() as session:
            for acc in accounts:
                uid = acc.get('uid')
                password = acc.get('password')
                if uid and password:
                    token_data = await fetch_token(session, uid, password)
                    if token_data:
                        results.append(token_data)
        
        output = json.dumps(results, indent=2)
        output_file = discord.File(
            fp=bytes(output, 'utf-8'),
            filename='tokens.json'
        )
        
        config = load_config()
        guild_config = config.get(str(interaction.guild_id))
        
        if guild_config and guild_config.get('channel_id'):
            channel = bot.get_channel(guild_config['channel_id'])
            if channel:
                await channel.send(f"Generated tokens: {len(results)}", file=output_file)
                await interaction.followup.send("Done. Posted tokens.json in the configured channel.")
            else:
                await interaction.followup.send("Channel not found. Sending here.", file=output_file)
        else:
            await interaction.followup.send(f"Generated tokens: {len(results)}", file=output_file)
            
    except json.JSONDecodeError:
        await interaction.followup.send("Invalid JSON file format.")
    except Exception as e:
        await interaction.followup.send(f"Error: {str(e)}")

bot.run(os.getenv('DISCORD_TOKEN'))
