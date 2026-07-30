from enum import Enum
from typing import Optional

from TikTokLive import TikTokLiveClient
from TikTokLive.client.errors import TikTokLiveError, UserNotFoundError

from logging_config import get_logger

logger = get_logger(__name__)


class LiveStatus(Enum):
    """TikTokユーザーの配信状態判定結果"""

    LIVE = "live"            # 配信中
    OFFLINE = "offline"      # オフライン（存在するが配信していない）
    NOT_FOUND = "not_found"  # ユーザーが存在しない（TikTok LIVE未対応・存在しないアカウント等）
    UNKNOWN = "unknown"      # 一時的な通信エラー等で判定できない


async def check_live_status(tiktok_id: str) -> LiveStatus:
    """指定したTikTokユーザーの配信状態を判定する。

    Args:
        tiktok_id: TikTokのユニークID（@なし）。

    Returns:
        LiveStatus: 判定結果。UNKNOWN の場合、呼び出し側は直前の状態を維持すること。
    """
    client = TikTokLiveClient(unique_id=tiktok_id)

    try:
        is_live = await client.is_live()
        return LiveStatus.LIVE if is_live else LiveStatus.OFFLINE
    except UserNotFoundError:
        logger.warning("TikTokユーザーが見つかりません(@%s)", tiktok_id)
        return LiveStatus.NOT_FOUND
    except TikTokLiveError as e:
        logger.warning("TikTok配信状態の確認に失敗しました(@%s): %s", tiktok_id, e)
        return LiveStatus.UNKNOWN
    except Exception:
        logger.exception("TikTok配信状態確認中に予期しないエラーが発生しました(@%s)", tiktok_id)
        return LiveStatus.UNKNOWN


async def fetch_room_details(tiktok_id: str) -> tuple[Optional[str], Optional[str]]:
    """配信中のTikTokユーザーの配信タイトル・サムネイル画像を取得する。

    年齢制限などで取得できない場合や値が空の場合は None を返す
    （呼び出し側は通知自体を継続し、該当欄を省略すること）。

    Args:
        tiktok_id: TikTokのユニークID（@なし）。

    Returns:
        (title, cover_url) のタプル。取得できない項目はそれぞれ None。
        cover_url: 配信サムネイル画像のURL。
    """
    client = TikTokLiveClient(unique_id=tiktok_id)

    try:
        room_info = await client.web.fetch_room_info(unique_id=tiktok_id)
    except TikTokLiveError as e:
        # AgeRestrictedError（年齢制限）等もここで捕捉される（TikTokLiveErrorのサブクラスのため）
        logger.warning("配信情報の取得に失敗しました(@%s): %s", tiktok_id, e)
        return None, None
    except Exception:
        logger.exception("配信情報取得中に予期しないエラーが発生しました(@%s)", tiktok_id)
        return None, None

    title = room_info.get("title") or None

    # 配信サムネイル画像のURL（あればEmbedに表示する）
    cover = room_info.get("cover") or {}
    url_list = cover.get("url_list") or []
    cover_url = url_list[0] if url_list else None

    return title, cover_url
