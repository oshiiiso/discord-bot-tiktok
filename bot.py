import discord
from discord.ext import commands

from logging_config import get_logger
from ui.panel import OpenSettingsView

logger = get_logger(__name__)

# =========================
# BOT設定
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class TikTokBot(commands.Bot):
    """TikTok配信通知Botの本体。

    setup_hook でTikTok監視Cogをロードし、Discord接続確立後に
    ポーリングループが自動的に開始される。
    """

    async def setup_hook(self) -> None:
        await self.load_extension("cogs.tiktok_watcher")
        logger.info("TikTokWatcher Cog をロードしました")

        # 常設の「配信通知設定」ボタン（persistent view）を登録する。
        # timeout=None かつ固定 custom_id のため、Bot再起動後もメッセージが
        # 残っている限りボタンが機能し続ける。
        self.add_view(OpenSettingsView(self))
        logger.info("常設設定ボタンのViewを登録しました")


bot = TikTokBot(command_prefix="!", intents=intents)

# =========================
# コマンド
# =========================
@bot.command()
@commands.has_permissions(manage_roles=True)
async def panel(ctx: commands.Context):
    """配信通知設定の常設パネルをこのチャンネルに設置する（ロール管理権限が必要）。

    設置されたパネルのボタンは全員が押せて、押した本人だけに見える
    配信者選択メニューが開く。
    """
    if ctx.guild is None:
        await ctx.send("このコマンドはサーバー内でのみ使用できます。")
        return

    embed = discord.Embed(
        title="📊 配信者通知設定",
        description=(
            "下のボタンを押すと、あなただけに表示される設定パネルが開きます。\n"
            "通知したい配信者を選択・解除できます。"
        ),
        color=discord.Color.from_rgb(254, 44, 85),
    )

    await ctx.send(embed=embed, view=OpenSettingsView(ctx.bot))


@panel.error
async def panel_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("このコマンドを実行するには「ロールの管理」権限が必要です。")
    else:
        raise error


@bot.event
async def on_ready():
    logger.info("Logged in as %s", bot.user)
