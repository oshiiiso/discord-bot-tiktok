import discord
from discord import app_commands
from discord.ext import commands

from config import GUILD_ID
from logging_config import get_logger
from services.streamers import add_streamer, load_streamers, remove_streamer, update_streamer
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

        # スラッシュコマンドをDiscordに登録する。
        # GUILD_ID が設定されていればそのサーバーに限定して即時反映し、
        # 未設定の場合はグローバル同期する（反映まで最大1時間程度かかることがある）。
        if GUILD_ID is not None:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("スラッシュコマンドをサーバー(ID: %s)に%d件同期しました", GUILD_ID, len(synced))
        else:
            synced = await self.tree.sync()
            logger.info("スラッシュコマンドをグローバルに%d件同期しました", len(synced))


# discord.pyのBotはcommand_prefixが必須引数のため設定するが、
# 本Botはスラッシュコマンドのみを提供し、テキストコマンドは使用しない。
bot = TikTokBot(command_prefix=commands.when_mentioned, intents=intents)

# =========================
# コマンド
# =========================
@bot.tree.command(name="panel", description="配信通知設定の常設パネルをこのチャンネルに設置します")
@app_commands.checks.has_permissions(manage_roles=True)
async def panel(interaction: discord.Interaction):
    """配信通知設定の常設パネルをこのチャンネルに設置する（ロール管理権限が必要）。

    設置されたパネルのボタンは全員が押せて、押した本人だけに見える
    配信者選択メニューが開く。
    """
    if interaction.guild is None:
        await interaction.response.send_message(
            "このコマンドはサーバー内でのみ使用できます。", ephemeral=True
        )
        return

    embed = discord.Embed(
        title="📊 配信者通知設定",
        description=(
            "下のボタンを押すと、あなただけに表示される設定パネルが開きます。\n"
            "通知したい配信者を選択・解除できます。"
        ),
        color=discord.Color.from_rgb(254, 44, 85),
    )

    await interaction.response.send_message(embed=embed, view=OpenSettingsView(interaction.client))


@panel.error
async def panel_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "⚠️ このコマンドを実行するには「ロールの管理」権限が必要です。", ephemeral=True
        )
    else:
        raise error


@bot.tree.command(name="ping", description="Botの応答速度を確認します")
async def ping(interaction: discord.Interaction):
    """Botの応答速度を確認する。"""
    await interaction.response.send_message(f"🏓 Pong! ({round(bot.latency * 1000)}ms)", ephemeral=True)


streamers_group = app_commands.Group(
    name="streamers", description="登録配信者の管理", default_permissions=discord.Permissions(manage_roles=True)
)


@streamers_group.command(name="list", description="登録されている配信者一覧を表示します")
@app_commands.checks.has_permissions(manage_roles=True)
async def streamers_list(interaction: discord.Interaction):
    """streamers.json に登録されている配信者一覧を表示する。"""
    streamers = load_streamers()
    if not streamers:
        await interaction.response.send_message("登録されている配信者がいません。", ephemeral=True)
        return

    lines = [f"・{s['label']}（@{s['tiktok_id']}、ロール: <@&{s['role_id']}>）" for s in streamers]
    await interaction.response.send_message("📋 登録配信者一覧\n" + "\n".join(lines), ephemeral=True)


@streamers_group.command(name="add", description="配信者を追加します")
@app_commands.describe(
    label="表示名（例: ばしばし）",
    role_id="通知に使うDiscordロールのID",
    tiktok_id="TikTokのユニーク ID（@なし）",
)
@app_commands.checks.has_permissions(manage_roles=True)
async def streamers_add(interaction: discord.Interaction, label: str, role_id: str, tiktok_id: str):
    """配信者をstreamers.jsonに追加する。"""
    if any(s.get("tiktok_id", "").lower() == tiktok_id.lower() for s in load_streamers()):
        await interaction.response.send_message(
            f"⚠️ `{tiktok_id}` はすでに登録されています。", ephemeral=True
        )
        return

    add_streamer(label, role_id, tiktok_id)
    await interaction.response.send_message(
        f"✅ `{label}`（@{tiktok_id}）を追加しました。", ephemeral=True
    )


@streamers_group.command(name="del", description="配信者を削除します")
@app_commands.describe(tiktok_id="削除するTikTokのユニーク ID")
@app_commands.checks.has_permissions(manage_roles=True)
async def streamers_del(interaction: discord.Interaction, tiktok_id: str):
    """配信者をstreamers.jsonから削除する。"""
    if remove_streamer(tiktok_id):
        await interaction.response.send_message(f"✅ `{tiktok_id}` を削除しました。", ephemeral=True)
    else:
        await interaction.response.send_message(
            f"⚠️ `{tiktok_id}` は streamers.json に登録されていません。", ephemeral=True
        )


@streamers_group.command(name="edit", description="登録済みの配信者情報を編集します")
@app_commands.describe(
    tiktok_id="編集対象のTikTokのユニーク ID",
    label="新しい表示名（変更しない場合は空白）",
    role_id="新しいロールID（変更しない場合は空白）",
    new_tiktok_id="新しいTikTokユニーク ID（変更しない場合は空白）",
)
@app_commands.checks.has_permissions(manage_roles=True)
async def streamers_edit(
    interaction: discord.Interaction,
    tiktok_id: str,
    label: str = None,
    role_id: str = None,
    new_tiktok_id: str = None,
):
    """登録済みの配信者情報を更新する。"""
    if label is None and role_id is None and new_tiktok_id is None:
        await interaction.response.send_message(
            "⚠️ label / role_id / new_tiktok_id のいずれかを指定してください。", ephemeral=True
        )
        return

    if update_streamer(tiktok_id, label=label, role_id=role_id, new_tiktok_id=new_tiktok_id):
        await interaction.response.send_message(f"✅ `{tiktok_id}` の情報を更新しました。", ephemeral=True)
    else:
        await interaction.response.send_message(
            f"⚠️ `{tiktok_id}` は streamers.json に登録されていません。", ephemeral=True
        )


async def _on_streamers_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "⚠️ このコマンドを実行するには「ロールの管理」権限が必要です。", ephemeral=True
        )
    else:
        raise error


streamers_list.error(_on_streamers_error)
streamers_add.error(_on_streamers_error)
streamers_del.error(_on_streamers_error)
streamers_edit.error(_on_streamers_error)

bot.tree.add_command(streamers_group)


@bot.tree.command(name="reload", description="TikTokWatcher Cogを再読み込みします（Bot所有者のみ）")
async def reload(interaction: discord.Interaction):
    """TikTokWatcher Cogを再読み込みする（Bot所有者のみ）。"""
    if not await bot.is_owner(interaction.user):
        await interaction.response.send_message(
            "⚠️ このコマンドを実行するにはBot所有者権限が必要です。", ephemeral=True
        )
        return

    try:
        await bot.reload_extension("cogs.tiktok_watcher")
    except commands.ExtensionError as e:
        await interaction.response.send_message(f"⚠️ 再読み込みに失敗しました: {e}", ephemeral=True)
        return
    await interaction.response.send_message("✅ TikTokWatcher Cog を再読み込みしました。", ephemeral=True)


@bot.event
async def on_ready():
    logger.info("Logged in as %s", bot.user)
