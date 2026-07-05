import discord

from services.streamers import load_streamers

# Discordの仕様上、Select 1個につき最大25選択肢、View 1個につき最大5コンポーネント
MAX_OPTIONS_PER_SELECT = 25
MAX_SELECTS_PER_VIEW = 5

NOT_FOUND_SUFFIX = "（存在しないユーザー）"


def get_role(guild: discord.Guild, role_id: str):
    return guild.get_role(int(role_id))


def _chunk(items: list, size: int) -> list:
    """items を size 件ずつのリストに分割する"""
    return [items[i:i + size] for i in range(0, len(items), size)]


def _get_watcher_cog(bot):
    """TikTokWatcher Cog を取得する（未ロード・bot未指定時は None）"""
    if bot is None:
        return None
    return bot.get_cog("TikTokWatcher")


def _build_label(bot, s: dict) -> str:
    """配信者ラベルを作成する。TikTokユーザーが存在しないと判明している場合は注記を付ける。"""
    label = s["label"]
    watcher = _get_watcher_cog(bot)

    if watcher is not None and watcher.is_user_not_found(s["role_id"]):
        label = f"{label}{NOT_FOUND_SUFFIX}"

    return label


def build_status_message(bot, guild: discord.Guild, user: discord.Member) -> str:
    """現在のON/OFF状況を一覧表示するメッセージ本文を作成する"""
    streamers = load_streamers()

    if not streamers:
        return "📊 配信者通知設定\n登録されている配信者がいません。streamers.json を確認してください。"

    lines = [
        "📊 配信者通知設定",
        "下のメニューから通知したい配信者を選択してください（複数選択・複数解除可）",
        "",
    ]

    for s in streamers:
        role = get_role(guild, s["role_id"])
        is_on = role in user.roles if role else False
        mark = "🟢" if is_on else "⚪"
        lines.append(f"{mark} {_build_label(bot, s)}")

    limit = MAX_OPTIONS_PER_SELECT * MAX_SELECTS_PER_VIEW
    if len(streamers) > limit:
        lines.append("")
        lines.append(f"⚠ 配信者数が上限（{limit}件）を超えているため、一部のみ表示しています。")

    return "\n".join(lines)


class StreamerSelect(discord.ui.Select):
    def __init__(
        self,
        bot,
        guild: discord.Guild,
        user: discord.Member,
        streamers: list,
        index: int,
    ):
        self.bot = bot
        self.streamers = streamers

        options = []
        for s in streamers:
            role = get_role(guild, s["role_id"])
            is_on = role in user.roles if role else False

            options.append(
                discord.SelectOption(
                    label=_build_label(bot, s)[:100],
                    value=s["role_id"],
                    default=is_on,
                )
            )

        super().__init__(
            placeholder=f"通知する配信者を選択（{index + 1}）",
            min_values=0,
            max_values=len(options),
            options=options,
            custom_id=f"streamer_select_{index}",
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user

        selected_ids = set(self.values)
        target_role_ids = {s["role_id"] for s in self.streamers}
        current_role_ids = {str(r.id) for r in member.roles}

        # このSelectが管理する範囲内で、追加すべき/解除すべきロールIDを算出
        to_add_ids = selected_ids - current_role_ids
        to_remove_ids = (target_role_ids - selected_ids) & current_role_ids

        to_add = []
        for role_id in to_add_ids:
            role = get_role(guild, role_id)
            if role is not None:
                to_add.append(role)

        to_remove = []
        for role_id in to_remove_ids:
            role = get_role(guild, role_id)
            if role is not None:
                to_remove.append(role)

        try:
            if to_add:
                await member.add_roles(*to_add, reason="TikTok通知設定")
            if to_remove:
                await member.remove_roles(*to_remove, reason="TikTok通知設定")
        except discord.Forbidden:
            await interaction.response.send_message(
                "ロールを付与/削除する権限がありません。Botの権限とロールの順序を管理者に確認してください。",
                ephemeral=True,
            )
            return

        # 最新状態を取り直す
        fresh_member = await guild.fetch_member(member.id)

        await interaction.response.edit_message(
            content=build_status_message(self.bot, guild, fresh_member),
            view=create_view(self.bot, guild, fresh_member),
        )


class StreamerView(discord.ui.View):
    def __init__(self, bot, guild: discord.Guild, user: discord.Member):
        super().__init__(timeout=120)

        streamers = load_streamers()
        chunks = _chunk(streamers, MAX_OPTIONS_PER_SELECT)[:MAX_SELECTS_PER_VIEW]

        for index, chunk in enumerate(chunks):
            self.add_item(StreamerSelect(bot, guild, user, chunk, index))


def create_view(bot, guild, user):
    return StreamerView(bot, guild, user)


class OpenSettingsView(discord.ui.View):
    """「配信通知設定」チャンネルなどに常設しておくためのボタン付きView。

    timeout=None かつボタンに固定 custom_id を設定しているため、
    Bot起動時に bot.add_view(OpenSettingsView(bot)) で登録しておけば、
    Bot再起動を挟んでもメッセージが残っている限りボタンが機能し続ける
    （discord.py の persistent view）。

    ボタンを押したユーザー本人にだけ見えるエフェメラル応答として、
    既存の配信者選択パネル（StreamerView）を表示する。
    """

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="⚙️ 通知設定を開く",
        style=discord.ButtonStyle.primary,
        custom_id="tiktok_notify:open_settings",
    )
    async def open_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "このボタンはサーバー内でのみ使用できます。",
                ephemeral=True,
            )
            return

        # interaction.user はキャッシュ由来の場合があるため、最新のロール情報を取得し直す
        member = await guild.fetch_member(interaction.user.id)

        await interaction.response.send_message(
            build_status_message(self.bot, guild, member),
            view=create_view(self.bot, guild, member),
            ephemeral=True,
        )
