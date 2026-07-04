from discord_notifier import send_message

from config import DEBUG_MODE

def main() -> None:
    success = send_message("Bot起動テスト")

    if DEBUG_MODE:
        if success:
            print("成功")
        else:
            print("失敗")

if __name__ == "__main__":
    main()
