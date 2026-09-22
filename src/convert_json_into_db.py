import json
import os
import sqlite3


def convert_json_to_db(
    json_file: str = "data/classified_messages.json",
    db_path: str = "data/emails.db",
    table_name: str = "messages",
):
    """Convertit le fichier JSON des e-mails classifiés en table SQLite."""
    if not os.path.exists(json_file):
        print(f"Erreur : Le fichier {json_file} n'existe pas.")
        return

    with open(json_file, "r", encoding="utf-8") as f:
        messages_data = json.load(f)

    if isinstance(messages_data, dict):
        messages_data = [messages_data]

    if not messages_data:
        print("Aucun message trouvé dans le fichier JSON.")
        return

    # Extraire toutes les clés présentes dans le JSON (message_id, sender, subject, date, body, classification)
    columns = list(
        dict.fromkeys(key for item in messages_data for key in item)
    )

    quoted_table = f'"{table_name}"'
    quoted_cols = [f'"{col}"' for col in columns]

    columns_def = ", ".join(f"{col} TEXT" for col in quoted_cols)
    columns_list = ", ".join(quoted_cols)
    placeholders = ", ".join("?" for _ in columns)

    # Préparation des valeurs avec conversion JSON pour les objets complexes
    rows = [
        tuple(
            (
                json.dumps(item.get(col), ensure_ascii=False)
                if isinstance(item.get(col), (dict, list))
                else item.get(col)
            )
            for col in columns
        )
        for item in messages_data
    ]

    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {quoted_table} ({columns_def})"
            )
            conn.executemany(
                f"INSERT INTO {quoted_table} ({columns_list}) VALUES ({placeholders})",
                rows,
            )
        print(
            f"Succès : {len(rows)} messages convertis et insérés dans '{db_path}' (table: {table_name})."
        )
    finally:
        conn.close()


if __name__ == "__main__":
    convert_json_to_db()