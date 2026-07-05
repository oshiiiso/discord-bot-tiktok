import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional

from logging_config import get_logger

logger = get_logger(__name__)

STATE_FILE = Path(__file__).resolve().parent.parent / "storage" / "state.json"


@dataclass
class StreamState:
    """配信者1人分の状態。

    start_message_id は配信開始通知メッセージのIDを保持し、
    配信終了通知をその開始通知への返信として送るために使う。
    """

    is_live: bool = False
    start_message_id: Optional[int] = None


def load_state() -> Dict[str, StreamState]:
    """配信中フラグの状態（role_id -> StreamState）を読み込む。

    ファイルが存在しない・壊れている場合は空の辞書を返す。
    旧形式（role_id -> bool）のファイルにも後方互換対応する。
    """
    if not STATE_FILE.exists():
        return {}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error("state.json の解析に失敗しました: %s", e)
        return {}

    if not isinstance(data, dict):
        logger.error("state.json の形式が不正です（辞書ではありません）")
        return {}

    result: Dict[str, StreamState] = {}
    for role_id, value in data.items():
        if isinstance(value, bool):
            # 旧形式（role_id -> bool）
            result[str(role_id)] = StreamState(is_live=value)
        elif isinstance(value, dict):
            result[str(role_id)] = StreamState(
                is_live=bool(value.get("is_live", False)),
                start_message_id=value.get("start_message_id"),
            )
        else:
            logger.warning("state.json の値の形式が不正なためスキップします: %s -> %s", role_id, value)

    return result


def save_state(state: Dict[str, StreamState]) -> None:
    """配信中フラグの状態を storage/state.json に保存する。"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    serializable = {role_id: asdict(s) for role_id, s in state.items()}

    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error("state.json の保存に失敗しました: %s", e)
