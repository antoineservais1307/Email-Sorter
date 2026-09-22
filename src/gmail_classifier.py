""" gmail_classifier.py - Classifies Gmail messages using Local LLM API (Instruct Model) """

import json
import os
import re
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio",
)

MODEL_NAME = "qwen2.5-7b-instruct"


def load_messages(input_file: str) -> list[dict]:
    with open(input_file, "r", encoding="utf-8") as f:
        return json.load(f)


def classify_one_message(subject: str, body: str) -> str:
    truncated_body = body[:1000] if body else "Pas de contenu"

    full_prompt = f"""Tu es un assistant expert en tri d'e-mails de recherche d'emploi.

Classifie l'e-mail ci-dessous dans EXACTEMENT une des 4 catégories :

- candidature : UNIQUEMENT les accusés de réception confirmant que TU AS DÉPOSÉ ou ENVOYÉ une candidature pour un poste précis (ex: "Nous avons bien reçu votre candidature", "Confirmation de dépôt de CV").
- autre : TOUTES les suggestions de postes, alertes d'emploi, "ce poste pourrait vous correspondre", opportunités LinkedIn/Indeed/Hellowork, newsletters, spams, notifications automatiques sans candidature préalable de ta part.
- entretien : invitation, proposition de rendez-vous, visio, entretien téléphonique.
- refus : réponse négative suite à une candidature, profil non retenu, poste pourvu.

RÈGLE D'OR : Si l'e-mail propose une offre d'emploi ou suggère un poste sans que l'utilisateur n'ait postulé, c'est IMPÉRATIVEMENT "autre".

Email à analyser :
Objet : {subject}
Corps : {truncated_body}

Réponds UNIQUEMENT sous la forme : <category>NOM_DE_LA_CATEGORIE</category>"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.0,
            max_tokens=50,
        )

        raw_content = response.choices[0].message.content or ""

        # 1. Extraction par la balise <category>...</category>
        match = re.search(
            r"<category>\s*(entretien|refus|candidature|autre)\s*</category>",
            raw_content,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).lower()

        # 2. Fallback si la balise est absente
        for category in ["entretien", "refus", "candidature", "autre"]:
            if category in raw_content.lower():
                return category

        return "autre"

    except Exception as e:
        print(f"\n[ERREUR API] : {e}")
        return "autre"

def classify_messages(messages: list[dict]) -> list[dict]:
    total = len(messages)
    for index, message in enumerate(messages, 1):
        subject = message.get("subject", "")
        body = message.get("body", "")

        print(
            f"\n[{index}/{total}] Objet: {subject[:35]}...", end="", flush=True
        )
        cat = classify_one_message(subject, body)
        message["classification"] = cat
        print(f" => FIN : {cat}")

    return messages


def save_classified_messages(messages: list[dict], output_file: str):
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=4, ensure_ascii=False)
    print(
        f"\n{len(messages)} messages classifiés sauvegardés dans {output_file}."
    )