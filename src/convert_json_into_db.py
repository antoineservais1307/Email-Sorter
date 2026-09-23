import json
import os
import sqlite3


def convert_json_to_db(
    json_file: str = "data/raw_messages.json",
    db_path: str = "data/emails.db",
    table_name: str = "messages",
):
    """Importe les emails JSON dans SQLite sans créer de doublons."""

    if not os.path.exists(json_file):
        print(
            f"Erreur : Le fichier {json_file} n'existe pas."
        )
        return

    with open(json_file, "r", encoding="utf-8") as f:
        messages_data = json.load(f)

    if isinstance(messages_data, dict):
        messages_data = [messages_data]

    if not messages_data:
        print("Aucun message trouvé dans le fichier JSON.")
        return

    # ---------------------------------------------------------
    # Vérification du message_id
    # ---------------------------------------------------------

    for message in messages_data:
        if not message.get("message_id"):
            print(
                "Erreur : un message ne possède pas de message_id."
            )
            return

    conn = sqlite3.connect(db_path)

    try:
        cursor = conn.cursor()

        # -----------------------------------------------------
        # Création de la table
        # -----------------------------------------------------

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                message_id TEXT PRIMARY KEY,
                sender TEXT,
                subject TEXT,
                date TEXT,
                body TEXT,
                classification TEXT
            )
            """
        )

        # -----------------------------------------------------
        # Préparation des données
        # -----------------------------------------------------

        rows = []

        for message in messages_data:

            rows.append(
                (
                    message.get("message_id"),
                    message.get("sender"),
                    message.get("subject"),
                    message.get("date"),
                    message.get("body"),
                )
            )

        # -----------------------------------------------------
        # INSERT uniquement pour les nouveaux emails
        # -----------------------------------------------------

        cursor.executemany(
            f"""
            INSERT OR IGNORE INTO "{table_name}"
            (
                message_id,
                sender,
                subject,
                date,
                body
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )

        inserted_count = cursor.rowcount

        conn.commit()

        ignored_count = len(rows) - inserted_count

        print(
            f"✅ {inserted_count} nouveau(x) message(s) ajouté(s)."
        )

        print(
            f"⏭️ {ignored_count} message(s) déjà présent(s) ignoré(s)."
        )

    finally:
        conn.close()
