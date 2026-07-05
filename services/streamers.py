import json
import os

# =========================
# JSONロード
# =========================
def load_streamers():
    path = os.path.join(os.path.dirname(__file__), "../streamers.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["streamers"]
