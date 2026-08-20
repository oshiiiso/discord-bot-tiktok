import asyncio
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import (
    LIVE_POLL_INTERVAL_SECONDS,
    MAX_BACKOFF_SECONDS,
    MAX_REQUEST_GAP_SECONDS,
    MIN_REQUEST_GAP_SECONDS,
    NOTIFY_CHANNEL_ID,
    POLL_INTERVAL_SECONDS,
    POLL_JITTER_RATIO,
    SCHEDULER_TICK_SECONDS,
)
from logging_config import get_logger
from services.state import StreamState, load_state, save_state
from services.streamers import load_streamers
from services.tiktok_monitor import LiveStatus, check_live_status, fetch_room_details

logger = get_logger(__name__)


@dataclass
class _StreamSchedule:
    """配信者ごとのポーリングスケジュール（メモリ上のみで管理、永続化しない）。

    Bot再起動時はリセットされ、全配信者が次回チェック対象になる
    （起動直後に現在の配信状態を素早く把握するため、これは意図した動作）。
    """

    next_check_at: float = 0.0   # time.monotonic() 基準の次回チェック予定時刻
    consecutive_errors: int = 0  # 連続エラー回数（指数バックオフの計算に使用）


class TikTokWatcher(commands.Cog):
    """TikTokの配信状態を定期的に確認し、配信開始をDiscordに通知するCog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.state: dict[str, StreamState] = load_state()
        # role_id -> LiveStatus。パネル表示時に「存在しないユーザー」等を示すためのキャッシュ
        # （メモリ上のみ。Bot再起動時はリセットされ、次回ポーリングで再構築される）
        self.status_cache: dict[str, LiveStatus] = {}
        # role_id -> _StreamSchedule。配信者ごとの次回チェック時刻・連続エラー数
        # （メモリ上のみ。レート制限回避のためのスケジューリング状態）
        self._schedules: dict[str, _StreamSchedule] = {}
        # role_id -> 開始通知メッセージID（/test start の送信結果を一時的に記憶する）。
        # /test end 実行時にこれを使って編集し、実際の監視ループと同じ「編集して
        # 終了扱いにする」挙動をテストできるようにする（state.jsonには影響しない）。
        self._test_start_message_ids: dict[str, int] = {}

    async def cog_load(self) -> None:
        """Cogがロードされた際にポーリングループを開始する。

        __init__ ではなくここで start() を呼ぶことで、イベントループが
        確実に稼働しているタイミングで安全にループを開始できる。
        """
        if not self.check_streams.is_running():
            self.check_streams.start()
            logger.info("TikTok監視ループを開始しました")

    async def cog_unload(self) -> None:
        self.check_streams.cancel()
        logger.info("TikTok監視ループを停止しました")

    def is_user_not_found(self, role_id: str) -> bool:
        """指定ロールIDに紐づくTikTokユーザーが存在しないと判明しているかどうか。

        まだ判定情報がない場合（Bot起動直後で未ポーリング等）は False を返す。
        """
        return self.status_cache.get(role_id) == LiveStatus.NOT_FOUND

    @staticmethod
    def _calc_next_interval(is_live: bool) -> float:
        """正常判定できた場合の、次回チェックまでの間隔を計算する（jitter込み）。

        配信中は LIVE_POLL_INTERVAL_SECONDS、オフライン中は POLL_INTERVAL_SECONDS を
        基準とし、それぞれ ±POLL_JITTER_RATIO の範囲でランダムに揺らす。
        （例: 基準60秒・比率0.1 → 54〜66秒の範囲でランダム）
        """
        base = LIVE_POLL_INTERVAL_SECONDS if is_live else POLL_INTERVAL_SECONDS
        jitter = base * POLL_JITTER_RATIO
        return random.uniform(base - jitter, base + jitter)

    @staticmethod
    def _calc_backoff_interval(consecutive_errors: int) -> float:
        """通信エラー発生時の、次回チェックまでの待機時間を指数バックオフで計算する。

        1回目: 約 POLL_INTERVAL_SECONDS 秒、以降エラーが連続するたびに倍々に増え、
        MAX_BACKOFF_SECONDS を上限とする。
        """
        backoff = POLL_INTERVAL_SECONDS * (2 ** (consecutive_errors - 1))
        return min(backoff, MAX_BACKOFF_SECONDS)

    @tasks.loop(seconds=SCHEDULER_TICK_SECONDS)
    async def check_streams(self) -> None:
        """配信者ごとの次回チェック時刻を確認し、到来している配信者だけを直列に処理する。

        ループ自体は SCHEDULER_TICK_SECONDS（デフォルト5秒）という短い間隔で回るが、
        実際にTikTokへ問い合わせるのは各配信者の next_check_at を過ぎた場合のみ。
        これにより配信者ごとに異なるタイミングでチェックが分散される。
        """
        streamers = [s for s in load_streamers() if s.get("tiktok_id")]

        if not streamers:
            logger.debug("チェック対象の配信者が0件のため、今回はスキップします。")
            return

        now = time.monotonic()

        due_streamers = []
        for s in streamers:
            schedule = self._schedules.setdefault(s["role_id"], _StreamSchedule())
            if schedule.next_check_at <= now:
                due_streamers.append(s)

        if not due_streamers:
            return

        logger.debug(
            "配信状態チェックを開始します（対象: %d/%d件、周回数: %d）",
            len(due_streamers), len(streamers), self.check_streams.current_loop,
        )

        channel = self.bot.get_channel(NOTIFY_CHANNEL_ID)
        if channel is None:
            logger.warning(
                "通知チャンネル(ID: %s)が見つかりません。config の NOTIFY_CHANNEL_ID を確認してください。",
                NOTIFY_CHANNEL_ID,
            )
        else:
            logger.debug("通知チャンネル: #%s (ID: %s)", getattr(channel, "name", "?"), NOTIFY_CHANNEL_ID)

        state_changed = False

        for i, s in enumerate(due_streamers):
            # 1人目は待機不要。2人目以降は前のリクエストとの間に
            # ランダムな間隔を空けて直列に処理する（同時アクセスを避ける）。
            if i > 0:
                await asyncio.sleep(random.uniform(MIN_REQUEST_GAP_SECONDS, MAX_REQUEST_GAP_SECONDS))

            role_id = s["role_id"]
            tiktok_id = s["tiktok_id"]
            label = s["label"]
            schedule = self._schedules[role_id]

            status = await check_live_status(tiktok_id)
            self.status_cache[role_id] = status
            logger.debug("  - %s (@%s): %s", label, tiktok_id, status.value)

            if status == LiveStatus.UNKNOWN:
                # 通信エラー等: 状態は変更せず、指数バックオフで次回チェックを遅らせる
                schedule.consecutive_errors += 1
                backoff = self._calc_backoff_interval(schedule.consecutive_errors)
                schedule.next_check_at = now + backoff
                logger.debug(
                    "  -> 判定エラーのため次回チェックまで%.1f秒待機します（連続%d回目）",
                    backoff, schedule.consecutive_errors,
                )
                continue

            if status == LiveStatus.NOT_FOUND:
                # ユーザー不存在: 状態は変更せず、通常間隔で次回チェックする
                schedule.consecutive_errors = 0
                schedule.next_check_at = now + self._calc_next_interval(is_live=False)
                continue

            # 正常に判定できたので連続エラーカウントをリセットし、通常間隔を設定
            schedule.consecutive_errors = 0
            is_live = status == LiveStatus.LIVE
            schedule.next_check_at = now + self._calc_next_interval(is_live=is_live)

            current = self.state.get(role_id, StreamState())

            if is_live != current.is_live:
                state_changed = True

                if is_live:
                    logger.info("配信開始を検知しました: %s (@%s)", label, tiktok_id)
                    message_id = None
                    if channel is not None:
                        message_id = await self._notify_live_start(channel, label, tiktok_id, role_id)
                    self.state[role_id] = StreamState(is_live=True, start_message_id=message_id)
                else:
                    logger.info("配信終了を検知しました: %s (@%s)", label, tiktok_id)
                    if channel is not None:
                        await self._notify_live_end(
                            channel, label, tiktok_id,
                            reply_to_message_id=current.start_message_id,
                        )
                    self.state[role_id] = StreamState(is_live=False, start_message_id=None)

        if state_changed:
            save_state(self.state)

    async def _notify_live_start(
        self,
        channel: discord.abc.Messageable,
        label: str,
        tiktok_id: str,
        role_id: str,
    ) -> "int | None":
        """配信開始を通知する。送信したメッセージのIDを返す（失敗時は None）。"""
        url = f"https://www.tiktok.com/@{tiktok_id}/live"
        mention = f"<@&{role_id}>"

        title, cover_url = await fetch_room_details(tiktok_id)

        embed = discord.Embed(
            title=f"🔴 {label} が配信を開始しました！",
            url=url,
            color=discord.Color.from_rgb(254, 44, 85),  # TikTokブランドカラー
            timestamp=datetime.now(timezone.utc),
        )
        if title:
            embed.add_field(name="📝 タイトル", value=title[:1024], inline=False)
        if cover_url:
            embed.set_image(url=cover_url)

        try:
            sent_message = await channel.send(content=mention, embed=embed)
            return sent_message.id
        except discord.Forbidden:
            logger.error("チャンネル(ID: %s)へのメッセージ送信権限がありません。", NOTIFY_CHANNEL_ID)
        except discord.HTTPException as e:
            logger.error("通知メッセージの送信に失敗しました: %s", e)

        return None

    async def _notify_live_end(
        self,
        channel: discord.abc.Messageable,
        label: str,
        tiktok_id: str,
        reply_to_message_id: "int | None" = None,
    ) -> None:
        end_title = f"⚫ {label} の配信が終了しました"
        end_color = discord.Color.from_rgb(128, 128, 128)

        def build_end_embed(start_embed: "discord.Embed | None" = None) -> discord.Embed:
            # 開始通知があればタイトル・サムネ等はそのまま残し、文言と色だけ差し替える
            if start_embed is not None:
                embed = start_embed.copy()
                embed.title = end_title
                embed.color = end_color
                return embed
            return discord.Embed(
                title=end_title,
                url=f"https://www.tiktok.com/@{tiktok_id}",
                color=end_color,
                timestamp=datetime.now(timezone.utc),
            )

        # 開始通知のメッセージが分かっていれば、それを編集して終了扱いにする
        # （返信で新規メッセージを増やさず、1メッセージに開始〜終了をまとめる）
        if reply_to_message_id is not None and hasattr(channel, "fetch_message"):
            try:
                start_message = await channel.fetch_message(reply_to_message_id)
                start_embed = start_message.embeds[0] if start_message.embeds else None
                await start_message.edit(embed=build_end_embed(start_embed))
                return
            except discord.NotFound:
                logger.warning("編集対象の開始通知メッセージが見つかりませんでした。通常の通知として送信します。")
            except discord.Forbidden:
                logger.error("チャンネル(ID: %s)のメッセージ編集権限がありません。", NOTIFY_CHANNEL_ID)
                return
            except discord.HTTPException as e:
                logger.warning("開始通知の編集に失敗しました。通常の通知として送信します: %s", e)

        try:
            await channel.send(embed=build_end_embed())
        except discord.Forbidden:
            logger.error("チャンネル(ID: %s)へのメッセージ送信権限がありません。", NOTIFY_CHANNEL_ID)
        except discord.HTTPException as e:
            logger.error("通知メッセージの送信に失敗しました: %s", e)

    def _find_streamer(self, tiktok_id: str) -> "dict | None":
        """streamers.json から tiktok_id（大文字小文字区別なし）に一致する配信者を探す。"""
        tiktok_id_lower = tiktok_id.lower()
        for s in load_streamers():
            if s.get("tiktok_id", "").lower() == tiktok_id_lower:
                return s
        return None

    test_group = app_commands.Group(name="test", description="通知テスト用コマンドグループ")

    @test_group.command(name="start", description="配信開始通知のテスト送信（実際の状態は変更しない）")
    @app_commands.describe(tiktok_id="streamers.jsonに登録されているTikTokのユニークID")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def test_start(self, interaction: discord.Interaction, tiktok_id: str) -> None:
        """配信開始通知のテスト送信（実際の状態は変更しない）。"""
        streamer = self._find_streamer(tiktok_id)
        if streamer is None:
            await interaction.response.send_message(
                f"⚠️ `{tiktok_id}` は streamers.json に登録されていません。", ephemeral=True
            )
            return

        channel = self.bot.get_channel(NOTIFY_CHANNEL_ID)
        if channel is None:
            await interaction.response.send_message(
                "⚠️ 通知チャンネルが見つかりません。config の NOTIFY_CHANNEL_ID を確認してください。",
                ephemeral=True,
            )
            return

        message_id = await self._notify_live_start(channel, streamer["label"], streamer["tiktok_id"], streamer["role_id"])
        if message_id is not None:
            self._test_start_message_ids[streamer["role_id"]] = message_id
        await interaction.response.send_message(
            f"✅ `{streamer['label']}` の配信開始通知テストを送信しました。", ephemeral=True
        )

    @test_group.command(name="end", description="配信終了通知のテスト送信（実際の状態は変更しない）")
    @app_commands.describe(tiktok_id="streamers.jsonに登録されているTikTokのユニークID")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def test_end(self, interaction: discord.Interaction, tiktok_id: str) -> None:
        """配信終了通知のテスト送信（実際の状態は変更しない）。"""
        streamer = self._find_streamer(tiktok_id)
        if streamer is None:
            await interaction.response.send_message(
                f"⚠️ `{tiktok_id}` は streamers.json に登録されていません。", ephemeral=True
            )
            return

        channel = self.bot.get_channel(NOTIFY_CHANNEL_ID)
        if channel is None:
            await interaction.response.send_message(
                "⚠️ 通知チャンネルが見つかりません。config の NOTIFY_CHANNEL_ID を確認してください。",
                ephemeral=True,
            )
            return

        message_id = self._test_start_message_ids.pop(streamer["role_id"], None)
        await self._notify_live_end(channel, streamer["label"], streamer["tiktok_id"], reply_to_message_id=message_id)
        await interaction.response.send_message(
            f"✅ `{streamer['label']}` の配信終了通知テストを送信しました。", ephemeral=True
        )

    async def _on_test_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "⚠️ このコマンドを実行するには「ロールの管理」権限が必要です。", ephemeral=True
            )
        else:
            raise error

    test_start.error(_on_test_error)
    test_end.error(_on_test_error)

    @check_streams.before_loop
    async def before_check_streams(self) -> None:
        await self.bot.wait_until_ready()

    @check_streams.error
    async def on_check_streams_error(self, error: Exception) -> None:
        """check_streams ループ内で捕捉されなかった例外のハンドラ。

        discord.ext.tasks は素の例外が発生するとループ自体を完全に停止させる
        （自動リトライされるのは接続系の一部例外のみ）。ここで確実にログへ
        記録した上で、ループを再起動して監視を継続させる。
        """
        logger.exception("check_streams ループで予期しないエラーが発生しました。", exc_info=error)

        if not self.check_streams.is_running():
            logger.warning("check_streams ループを再起動します。")
            self.check_streams.restart()


async def setup(bot: commands.Bot) -> None:
    # test_group は app_commands.Group をクラス属性として持つため、
    # add_cog() 時に自動的にコマンドツリーへ登録される。
    # ここで改めて bot.tree.add_command() を呼ぶと二重登録エラーになるため呼ばない。
    await bot.add_cog(TikTokWatcher(bot))
