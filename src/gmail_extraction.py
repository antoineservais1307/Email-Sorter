""" Script to extract emails from Gmail using the Gmail API. """

import base64
import json
import os

from bs4 import BeautifulSoup as beautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service(token_path="token.json", credentials_path="credentials.json"):
    """Authenticate and return the Gmail API service."""
    os.makedirs(os.path.dirname(token_path) or ".", exist_ok=True)

    creds = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as token:
            token.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds)
    return service


def list_messages_ids(service, start_date, end_date=None, user_id="me"):
    """List all message IDs from the user's mailbox within a specified date range."""
    messages_ids = []
    page_token = None

    try:
        while True:
            query = f"after:{start_date}"
            if end_date:
                query += f" before:{end_date}"

            results = (
                service.users()
                .messages()
                .list(userId=user_id, q=query, pageToken=page_token)
                .execute()
            )

            messages = results.get("messages", [])
            messages_ids.extend([message["id"] for message in messages])

            page_token = results.get("nextPageToken")
            if not page_token:
                break

    except HttpError as error:
        print(f"An error occurred: {error}")
        return []

    return messages_ids


def get_message_content(service, message_id, user_id="me"):
    """Retrieve the content of a specific email message by its ID safely."""
    try:
        message = (
            service.users()
            .messages()
            .get(userId=user_id, id=message_id)
            .execute()
        )
        headers = message.get("payload", {}).get("headers", [])

        # Extraction sécurisée des en-têtes (insensible à la casse + valeur par défaut)
        sender = next(
            (h["value"] for h in headers if h["name"].lower() == "from"),
            "Inconnu",
        )
        subject = next(
            (h["value"] for h in headers if h["name"].lower() == "subject"),
            "Sans objet",
        )
        date = next(
            (h["value"] for h in headers if h["name"].lower() == "date"),
            "",
        )

        # Extraction récursive du contenu du corps de l'email
        payload = message.get("payload", {})
        body_raw = ""

        def extract_text_plain(part):
            mime_type = part.get("mimeType", "")
            if mime_type == "text/plain" and "data" in part.get("body", {}):
                return part["body"]["data"]
            if "parts" in part:
                for sub_part in part["parts"]:
                    data = extract_text_plain(sub_part)
                    if data:
                        return data
            return ""

        if "data" in payload.get("body", {}):
            body_raw = payload["body"]["data"]
        elif "parts" in payload:
            body_raw = extract_text_plain(payload)

        body_clean = ""
        if body_raw:
            # Correction éventuelle du padding base64
            padded_body = body_raw + "=" * (-len(body_raw) % 4)
            decoded_bytes = base64.urlsafe_b64decode(padded_body)
            decoded_text = decoded_bytes.decode("utf-8", errors="ignore")

            # Nettoyage HTML avec BeautifulSoup
            soup = beautifulSoup(decoded_text, "html.parser")
            body_clean = soup.get_text(separator=" ", strip=True)

        return {
            "message_id": message_id,
            "sender": sender,
            "subject": subject,
            "date": date,
            "body": body_clean,
        }

    except HttpError as error:
        print(f"HttpError occurred for message {message_id}: {error}")
        return None
    except Exception as error:
        print(f"Unexpected error processing message {message_id}: {error}")
        return None


def load_existings_messages_from_json(filename):
    """Load existing messages from a JSON file."""
    if not os.path.exists(filename):
        return []

    try:
        with open(filename, "r", encoding="utf-8") as f:
            messages_data = json.load(f)
        return [message["message_id"] for message in messages_data]
    except Exception:
        return []


def save_messages_content_to_json(service, messages, filename):
    """Save the content of multiple email messages to a JSON file without duplicates."""
    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)

    existing_ids = load_existings_messages_from_json(filename)

    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                messages_data = json.load(f)
        except Exception:
            messages_data = []
    else:
        messages_data = []

    new_count = 0
    total = len(messages)

    for index, message_id in enumerate(messages, 1):
        if message_id in existing_ids:
            continue

        print(f"[{index}/{total}] Extraction du message {message_id}...")
        message_content = get_message_content(service, message_id)
        if message_content:
            messages_data.append(message_content)
            new_count += 1

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(messages_data, f, indent=4, ensure_ascii=False)

    print(
        f"\n{new_count} nouveaux messages ajoutés, {total - new_count} déjà présents."
    )