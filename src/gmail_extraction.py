""" Script to extract emails from Gmail using the Gmail API. """

import json
import os
import base64

from bs4 import BeautifulSoup as beautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service(token_path='token.json', credentials_path='credentials.json'):
    """Authenticate and return the Gmail API service.

    If the user has not authenticated before, it will prompt for authentication
    and save the credentials in the token file. If already authenticated,
    it will load the credentials from that file.

    Args:
        token_path: chemin vers le fichier token.json.
        credentials_path: chemin vers le fichier credentials.json.

    Returns:
        An authorized Gmail API service instance.
    """
    os.makedirs(os.path.dirname(token_path) or '.', exist_ok=True)

    creds = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds)
    return service


def list_messages_ids(service, start_date, end_date=None, user_id='me'):
    """List all message IDs from the user's mailbox within a specified date range.

    Args:
        service: Authorized Gmail API service instance.
        start_date: The start date for the search (in 'YYYY/MM/DD' format).
        end_date: The end date for the search (in 'YYYY/MM/DD' format). If None,
            it will search until the current date.
        user_id: User's email address. The special value "me" can be used to
            indicate the authenticated user.

    Returns:
        A list of message IDs.
    """
    messages_ids = []
    page_token = None

    try:
        while True:
            query = f"after:{start_date}"
            if end_date:
                query += f" before:{end_date}"

            results = service.users().messages().list(
                userId=user_id, q=query, pageToken=page_token
            ).execute()

            messages = results.get('messages', [])
            messages_ids.extend([message['id'] for message in messages])

            page_token = results.get('nextPageToken')
            if not page_token:
                break

    except HttpError as error:
        print(f'An error occurred: {error}')
        return []

    return messages_ids


def get_message_content(service, message_id, user_id='me'):
    """Retrieve the content of a specific email message by its ID.

    Args:
        service: Authorized Gmail API service instance.
        message_id: The ID of the email message to retrieve.
        user_id: User's email address. The special value "me" can be used to
            indicate the authenticated user.

    Returns:
        A dictionary containing the message_id, sender, subject, date, and
        body of the email message, or None if an error occurred.
    """
    try:
        message = service.users().messages().get(userId=user_id, id=message_id).execute()
        headers = message['payload']['headers']

        sender = next(header['value'] for header in headers if header['name'] == 'From')
        subject = next(header['value'] for header in headers if header['name'] == 'Subject')
        date = next(header['value'] for header in headers if header['name'] == 'Date')

        # get body content
        payload = message['payload']
        body_data = payload.get('body', {}).get('data', '')
        if not body_data and 'parts' in payload:
            for parts in payload['parts']:
                if parts['mimeType'] == 'text/plain':
                    body_data = parts.get('body', {}).get('data', '')
                    break

        if body_data:
            body_data = base64.urlsafe_b64decode(body_data).decode('utf-8')
            # Clean the body data using BeautifulSoup
            soup = beautifulSoup(body_data, 'html.parser')
            body_data = soup.get_text()

        return {
            'message_id': message_id,
            'sender': sender,
            'subject': subject,
            'date': date,
            'body': body_data
        }

    except HttpError as error:
        print(f'An error occurred: {error}')
        return None


def load_existings_messages_from_json(filename):
    """Load existing messages from a JSON file.

    Args:
        filename: The name of the JSON file to load the messages content from.

    Returns:
        A list of message IDs already saved in the file (empty if the file
        doesn't exist).
    """
    if not os.path.exists(filename):
        return []

    with open(filename, 'r', encoding='utf-8') as f:
        messages_data = json.load(f)

    return [message['message_id'] for message in messages_data]


def save_messages_content_to_json(service, messages, filename):
    """Save the content of multiple email messages to a JSON file, en évitant les doublons.

    Args:
        service: Authorized Gmail API service instance.
        messages: A list of message IDs to retrieve and save.
        filename: The name of the JSON file to save the messages content.
    """
    os.makedirs(os.path.dirname(filename) or '.', exist_ok=True)

    existing_ids = load_existings_messages_from_json(filename)

    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            messages_data = json.load(f)
    else:
        messages_data = []

    new_count = 0
    for message_id in messages:
        if message_id in existing_ids:
            continue

        message_content = get_message_content(service, message_id)
        if message_content:
            messages_data.append(message_content)
            new_count += 1

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(messages_data, f, indent=4, ensure_ascii=False)

    print(f"{new_count} nouveaux messages ajoutés, {len(messages) - new_count} déjà présents.")