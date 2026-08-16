import json
import os

from logging_config import get_logger

logger = get_logger(__name__)

STREAMERS_FILE = os.path.join(os.path.dirname(__file__), "../streamers.json")


# =========================
# JSONロード
# =========================
def load_streamers() -> list:
    """streamers.json から配信者一覧を読み込む。

    ファイルが存在しない・JSONが壊れている・形式が不正な場合は
    空リストを返し、エラー内容をログに出力する（Botをクラッシュさせない）。
    """
    try:
        with open(STREAMERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error("streamers.json が見つかりません: %s", STREAMERS_FILE)
        return []
    except json.JSONDecodeError as e:
        logger.error("streamers.json の解析に失敗しました: %s", e)
        return []

    streamers = data.get("streamers")

    if not isinstance(streamers, list):
        logger.error("streamers.json の形式が不正です（'streamers' キーがリストではありません）")
        return []

    valid_streamers = []
    for i, s in enumerate(streamers):
        if not isinstance(s, dict) or not s.get("label") or not s.get("role_id"):
            logger.warning(
                "streamers.json の%d番目の要素が不正なためスキップします: %s", i, s
            )
            continue
        valid_streamers.append(s)

    return valid_streamers


def save_streamers(streamers: list) -> None:
    """配信者一覧を streamers.json に保存する。"""
    data = {"streamers": streamers}
    try:
        with open(STREAMERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error("streamers.json の保存に失敗しました: %s", e)
        raise


def add_streamer(label: str, role_id: str, tiktok_id: str) -> None:
    """配信者を1件追加して streamers.json に保存する。"""
    streamers = load_streamers()
    streamers.append({"label": label, "role_id": role_id, "tiktok_id": tiktok_id})
    save_streamers(streamers)


def remove_streamer(tiktok_id: str) -> bool:
    """tiktok_id（大文字小文字区別なし）が一致する配信者を削除する。

    Returns:
        削除できた場合は True、該当が見つからなかった場合は False。
    """
    streamers = load_streamers()
    tiktok_id_lower = tiktok_id.lower()
    new_streamers = [s for s in streamers if s.get("tiktok_id", "").lower() != tiktok_id_lower]

    if len(new_streamers) == len(streamers):
        return False

    save_streamers(new_streamers)
    return True


def update_streamer(
    tiktok_id: str,
    label: "str | None" = None,
    role_id: "str | None" = None,
    new_tiktok_id: "str | None" = None,
) -> bool:
    """tiktok_id（大文字小文字区別なし）が一致する配信者の情報を更新する。

    指定しなかった項目（None）は変更しない。

    Returns:
        更新できた場合は True、該当が見つからなかった場合は False。
    """
    streamers = load_streamers()
    tiktok_id_lower = tiktok_id.lower()

    found = False
    for s in streamers:
        if s.get("tiktok_id", "").lower() == tiktok_id_lower:
            if label is not None:
                s["label"] = label
            if role_id is not None:
                s["role_id"] = role_id
            if new_tiktok_id is not None:
                s["tiktok_id"] = new_tiktok_id
            found = True
            break

    if not found:
        return False

    save_streamers(streamers)
    return True
