import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

# Load secrets
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Setup bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# Simple test command
@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong!")

bot.run(TOKEN)
