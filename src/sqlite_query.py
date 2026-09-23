import sqlite3
import json


def query_database():
    # Connexion explicite au fichier situé dans le dossier data
    conn = sqlite3.connect("data/emails.db")
    cursor = conn.cursor()

    # Remplacer 'messages' par 'emails' si la table a été créée avec src/database.py
    table_name = "messages"

    query = f"SELECT classification, COUNT(*) FROM {table_name} GROUP BY classification"

    cursor.execute(query)
    results = cursor.fetchall()

    for row in results:
        print(f"Classification: {row[0]}, Count: {row[1]}")


    conn.close()


if __name__ == "__main__":
    query_database()