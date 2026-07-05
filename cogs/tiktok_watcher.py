import discord
from discord.ext import commands, tasks

from config import NOTIFY_CHANNEL_ID, POLL_INTERVAL_SECONDS
from logging_config import get_logger
from services.state import StreamState, load_state, save_state
from services.streamers import load_streamers
from services.tiktok_monitor import LiveStatus, check_live_status, fetch_room_details

logger = get_logger(__name__)


class TikTokWatcher(commands.Cog):
    """TikTokの配信状態を定期的に確認し、配信開始をDiscordに通知するCog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.state: dict[str, StreamState] = load_state()
        # role_id -> LiveStatus。パネル表示時に「存在しないユーザー」等を示すためのキャッシュ
        # （メモリ上のみ。Bot再起動時はリセットされ、次回ポーリングで再構築される）
        self.status_cache: dict[str, LiveStatus] = {}
        self.check_streams.start()

    def cog_unload(self) -> None:
        self.check_streams.cancel()

    def is_user_not_found(self, role_id: str) -> bool:
        """指定ロールIDに紐づくTikTokユーザーが存在しないと判明しているかどうか。

        まだ判定情報がない場合（Bot起動直後で未ポーリング等）は False を返す。
        """
        return self.status_cache.get(role_id) == LiveStatus.NOT_FOUND

    @tasks.loop(seconds=POLL_INTERVAL_SECONDS)
    async def check_streams(self) -> None:
        streamers = [s for s in load_streamers() if s.get("tiktok_id")]

        if not streamers:
            return

        channel = self.bot.get_channel(NOTIFY_CHANNEL_ID)
        if channel is None:
            logger.warning(
                "通知チャンネル(ID: %s)が見つかりません。config の NOTIFY_CHANNEL_ID を確認してください。",
                NOTIFY_CHANNEL_ID,
            )

        state_changed = False

        for s in streamers:
            role_id = s["role_id"]
            tiktok_id = s["tiktok_id"]
            label = s["label"]

            status = await check_live_status(tiktok_id)
            self.status_cache[role_id] = status

            # 判定不能・ユーザー不存在の場合は状態を変えずスキップ
            # （誤検知による重複/欠落通知を防ぐ）
            if status in (LiveStatus.UNKNOWN, LiveStatus.NOT_FOUND):
                continue

            is_live = status == LiveStatus.LIVE
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

        title, summary, cover_url = await fetch_room_details(tiktok_id)

        embed = discord.Embed(
            title=f"🔴 {label} が配信を開始しました！",
            url=url,
            description=f"[配信を見る]({url})",
            color=discord.Color.from_rgb(254, 44, 85),  # TikTokブランドカラー
        )
        if title:
            embed.add_field(name="📝 タイトル", value=title[:1024], inline=False)
        if summary:
            embed.add_field(name="📋 概要", value=summary[:1024], inline=False)
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
        url = f"https://www.tiktok.com/@{tiktok_id}"

        embed = discord.Embed(
            title=f"⚫ {label} の配信が終了しました",
            url=url,
            color=discord.Color.from_rgb(128, 128, 128),
        )

        # 開始通知のメッセージIDが分かっていれば、それへの返信として送る
        if reply_to_message_id is not None and hasattr(channel, "get_partial_message"):
            try:
                partial_message = channel.get_partial_message(reply_to_message_id)
                # 終了通知はロールメンションなし（メンション通知で騒がしくなるのを防ぐ）
                await partial_message.reply(embed=embed, mention_author=False)
                return
            except discord.NotFound:
                logger.warning("返信先の開始通知メッセージが見つかりませんでした。通常の通知として送信します。")
            except discord.Forbidden:
                logger.error("チャンネル(ID: %s)へのメッセージ送信権限がありません。", NOTIFY_CHANNEL_ID)
                return
            except discord.HTTPException as e:
                logger.warning("開始通知への返信に失敗しました。通常の通知として送信します: %s", e)

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logger.error("チャンネル(ID: %s)へのメッセージ送信権限がありません。", NOTIFY_CHANNEL_ID)
        except discord.HTTPException as e:
            logger.error("通知メッセージの送信に失敗しました: %s", e)

    @check_streams.before_loop
    async def before_check_streams(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TikTokWatcher(bot))
