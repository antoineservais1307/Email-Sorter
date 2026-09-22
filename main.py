""" main file for the email sorter project """
import os
from src.gmail_extraction import get_gmail_service, list_messages_ids, save_messages_content_to_json

TOKEN_DIR = "config"
TOKEN_PATH = os.path.join(TOKEN_DIR, "token.json")
CREDENTIALS_PATH = os.path.join(TOKEN_DIR, "credentials.json")

os.makedirs(TOKEN_DIR, exist_ok=True)
os.makedirs("data", exist_ok=True)
OUTPUT_FILENAME = "data/raw_messages.json"

def main():
    """Main function to extract and save email messages content."""
    print('get gmail service')
    service = get_gmail_service(token_path=TOKEN_PATH, credentials_path=CREDENTIALS_PATH)
    start_date = "2026/08/20"
    end_date = "2026/08/31"

    messages = list_messages_ids(service, start_date, end_date)
    print(f"Found {len(messages)} messages between {start_date} and {end_date}.")
    save_messages_content_to_json(service, messages, OUTPUT_FILENAME)
    print(f"Messages saved to {OUTPUT_FILENAME}.")

if __name__ == "__main__":
    main()