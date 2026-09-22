""" main file for the email sorter project """

import os
from src.gmail_classifier import (
    classify_messages,
    load_messages,
    save_classified_messages,
)
from src.gmail_extraction import (
    get_gmail_service,
    list_messages_ids,
    save_messages_content_to_json,
)

TOKEN_DIR = "config"
TOKEN_PATH = os.path.join(TOKEN_DIR, "token.json")
CREDENTIALS_PATH = os.path.join(TOKEN_DIR, "credentials.json")

os.makedirs(TOKEN_DIR, exist_ok=True)
os.makedirs("data", exist_ok=True)
OUTPUT_FILENAME = "data/raw_messages.json"
CLASSIFIED_FILENAME = "data/classified_messages.json"


def main():
    """Main function to extract, save, and classify email messages content."""
    print("get gmail service")
    service = get_gmail_service(
        token_path=TOKEN_PATH, credentials_path=CREDENTIALS_PATH
    )
    start_date = "2026/08/20"
    end_date = ""

    # 1. Extraction des IDs
    messages = list_messages_ids(service, start_date, end_date)
    print(
        f"Found {len(messages)} messages between {start_date} and {end_date}."
    )

    # 2. Récupération et sauvegarde du contenu brut
    save_messages_content_to_json(service, messages, OUTPUT_FILENAME)
    print(f"Messages saved to {OUTPUT_FILENAME}.")

    # 3. Classification via le LLM local
    print("\nDébut de la classification des messages...")
    raw_messages = load_messages(OUTPUT_FILENAME)
    classified_messages = classify_messages(raw_messages)

    # 4. Sauvegarde des résultats classifiés
    save_classified_messages(classified_messages, CLASSIFIED_FILENAME)


if __name__ == "__main__":
    main()