import discord
from discord.ext import commands
from config import DISCORD_TOKEN
from ui.panel import create_view

# =========================
# BOT設定
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# コマンド
# =========================
@bot.command()
async def panel(ctx):

    view = create_view(ctx.guild, ctx.author)

    await ctx.send(
        "📊 配信者通知設定\n🟢 ON / 🔴 OFF（ボタンで切替）",
        view=view
    )


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


bot.run(DISCORD_TOKEN)
