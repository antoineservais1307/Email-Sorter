"""Main file for the email sorter project."""

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

from src.convert_json_into_db import convert_json_to_db


TOKEN_DIR = "config"
TOKEN_PATH = os.path.join(TOKEN_DIR, "token.json")
CREDENTIALS_PATH = os.path.join(TOKEN_DIR, "credentials.json")

os.makedirs(TOKEN_DIR, exist_ok=True)
os.makedirs("data", exist_ok=True)

RAW_MESSAGES_FILENAME = "data/raw_messages.json"
DB_PATH = "data/emails.db"
TABLE_NAME = "messages"


def main():
    """Extract, store and classify Gmail messages."""

    # ---------------------------------------------------------
    # 1. Connexion à Gmail
    # ---------------------------------------------------------

    print("\n=== Connexion à Gmail ===")

    service = get_gmail_service(
        token_path=TOKEN_PATH,
        credentials_path=CREDENTIALS_PATH,
    )

    # ---------------------------------------------------------
    # 2. Recherche des messages
    # ---------------------------------------------------------

    start_date = "2026/08/19"
    end_date = ""

    messages = list_messages_ids(
        service,
        start_date,
        end_date,
    )

    print(
        f"Found {len(messages)} messages "
        f"between {start_date} and {end_date or 'now'}."
    )

    # ---------------------------------------------------------
    # 3. Extraction du contenu vers le JSON
    # ---------------------------------------------------------

    print("\n=== Extraction des emails ===")

    save_messages_content_to_json(
        service,
        messages,
        RAW_MESSAGES_FILENAME,
    )

    print(
        f"Messages saved to {RAW_MESSAGES_FILENAME}."
    )

    # ---------------------------------------------------------
    # 4. Import du JSON vers SQLite
    # ---------------------------------------------------------

    print("\n=== Import vers SQLite ===")

    convert_json_to_db(
        json_file=RAW_MESSAGES_FILENAME,
        db_path=DB_PATH,
        table_name=TABLE_NAME,
    )

    # ---------------------------------------------------------
    # 5. Chargement des emails NON CLASSIFIÉS depuis SQLite
    # ---------------------------------------------------------

    print("\n=== Chargement des emails à classifier ===")

    messages_to_classify = load_messages(
        DB_PATH,
        TABLE_NAME,
    )

    if not messages_to_classify:
        print("\n✅ Aucun nouveau message à classifier.")
        return

    print(
        f"\n📧 {len(messages_to_classify)} "
        f"message(s) à classifier."
    )

    # ---------------------------------------------------------
    # 6. Classification avec le LLM local
    # ---------------------------------------------------------

    print("\n=== Classification avec le LLM local ===")

    classified_messages = classify_messages(
        messages_to_classify
    )

    # ---------------------------------------------------------
    # 7. Mise à jour de SQLite
    # ---------------------------------------------------------

    print("\n=== Sauvegarde des classifications ===")

    save_classified_messages(
        classified_messages,
        DB_PATH,
    )

    print("\n✅ Traitement terminé.")


if __name__ == "__main__":
    main()
