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
