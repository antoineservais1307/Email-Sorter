"""Classifies Gmail messages using deterministic rules and a local LLM."""

import re
import sqlite3

from openai import OpenAI


# ============================================================
# CONFIGURATION
# ============================================================

client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio",
)

MODEL_NAME = "qwen2.5-7b-instruct"

DB_PATH = "data/emails.db"
TABLE_NAME = "messages"


# ============================================================
# DATABASE
# ============================================================

def load_messages(
    db_path: str,
    table_name: str,
) -> list[dict]:
    """Charge uniquement les emails non classifiés."""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = f"""
        SELECT *
        FROM "{table_name}"
        WHERE classification IS NULL
           OR classification = ''
    """

    cursor.execute(query)

    rows = cursor.fetchall()

    columns = [
        description[0]
        for description in cursor.description
    ]

    messages = [
        dict(zip(columns, row))
        for row in rows
    ]

    conn.close()

    return messages


# ============================================================
# TEXT HELPERS
# ============================================================

def normalize_text(text: str) -> str:
    """Normalise légèrement le texte."""

    if not text:
        return ""

    text = text.lower()

    # Apostrophe typographique → apostrophe classique
    text = text.replace("’", "'")

    # Réduction des espaces multiples
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# DETERMINISTIC RULES
# ============================================================

def apply_rules(
    subject: str,
    body: str,
) -> str | None:
    """
    Classe les cas évidents sans utiliser le LLM.

    Retourne :
        candidature
        entretien
        refus
        autre
        None si le cas est ambigu.
    """

    subject_text = normalize_text(subject)
    body_text = normalize_text(body)

    text = f"{subject_text} {body_text}"

    # ========================================================
    # 1. AUTRE
    # ========================================================

    # Ces formulations indiquent généralement que l'email
    # concerne une offre, une suggestion ou une candidature
    # qui n'est pas encore confirmée.

    other_phrases = [
        "avez-vous postulé",
        "avez vous postulé",
        "avez-vous finalisé votre candidature",
        "avez vous finalisé votre candidature",
        "complétez votre candidature",
        "complétez votre candidature sur le site du recruteur",
        "postulez maintenant",
        "envoyez votre candidature rapidement",
        "votre parcours pourrait correspondre",
        "pourrait correspondre à l'offre",
        "pourrait correspondre à cette offre",
    ]

    for phrase in other_phrases:
        if phrase in text:
            return "autre"

    # ========================================================
    # 2. REFUS EXPLICITE
    # ========================================================

    # IMPORTANT :
    # Cette section est évaluée AVANT "candidature reçue".
    #
    # Exemple :
    #
    # "Nous avons bien reçu votre candidature.
    #  Nous avons décidé de ne pas y donner suite."
    #
    # → refus

    refusal_phrases = [
    "nous avons décidé de ne pas y donner suite",
    "nous avons décidé de ne pas donner suite",
    "nous ne donnerons pas suite",
    "nous avons décidé de ne pas retenir votre candidature",
    "nous avons décidé de ne pas retenir votre profil",
    "nous ne pouvons malheureusement pas donner suite",
    "nous ne pouvons pas donner suite à votre candidature",
    "nous ne donnerons malheureusement pas suite",

    "we've decided to move forward with candidates",
    "we have decided to move forward with candidates",
    "we've decided not to move forward",
    "we have decided not to move forward",
    "we will not be moving forward with your application",
    "we decided not to move forward with your application",
    "we have decided to move forward with other candidates",
    ]

    for phrase in refusal_phrases:
        if phrase in text:
            return "refus"

    # ========================================================
    # 3. REFUS CONDITIONNEL
    # ========================================================

    # Exemple :
    #
    # "Si vous ne recevez pas de réponse sous 45 jours,
    #  veuillez considérer que votre candidature n'a pas
    #  été retenue."
    #
    # Ce n'est PAS encore un refus.
    #
    # → candidature

    conditional_refusal = [
        "si vous ne recevez pas de réponse",
        "si vous ne recevez aucune réponse",
        "if you do not receive a response",
        "if you don't receive a response",
    ]

    for phrase in conditional_refusal:
        if phrase in text:
            return "candidature"

    # ========================================================
    # 4. ENTRETIEN REELLEMENT PROPOSE OU CONFIRME
    # ========================================================

    interview_phrases = [
        # Français
        "nous souhaitons vous rencontrer",
        "nous aimerions vous rencontrer",
        "nous vous proposons un entretien",
        "nous vous proposons un échange",
        "nous souhaitons organiser un entretien",
        "nous souhaitons organiser un échange",
        "votre entretien est prévu",
        "votre entretien aura lieu",
        "entretien confirmé",
        "invitation à un entretien",
        "invitation pour un entretien",
        "invitation à un échange",
        "nous vous invitons à un entretien",

        # Anglais
        "we would like to invite you to an interview",
        "we would like to schedule an interview",
        "we would like to meet with you",
        "your interview is scheduled",
    ]

    for phrase in interview_phrases:
        if phrase in text:
            return "entretien"

    # ========================================================
    # 5. CANDIDATURE REELLEMENT RECUE
    # ========================================================

    candidature_phrases = [
        # Français
        "nous avons bien reçu votre candidature",
        "nous avons reçu votre candidature",
        "nous accusons réception de votre candidature",
        "votre candidature a bien été reçue",
        "votre candidature est bien enregistrée",
        "nous avons bien enregistré votre candidature",
        "nous confirmons la réception de votre candidature",

        # Hellowork
        "le recruteur prendra contact avec vous après étude de votre candidature",

        # Anglais
        "we have received your application",
        "we received your application",
        "thank you for your application",
        "thank you for sending us your application",
        "thank you for submitting your application",
        "your application has been received",
        "we confirm receipt of your application",
    ]

    for phrase in candidature_phrases:
        if phrase in text:
            return "candidature"

    # ========================================================
    # 6. CAS AMBIGU
    # ========================================================

    return None


# ============================================================
# LLM
# ============================================================

def classify_with_llm(
    subject: str,
    body: str,
) -> str:
    """Utilise Qwen uniquement pour les cas ambigus."""

    full_body = body if body else "Pas de contenu"

    prompt = f"""Classe cet e-mail de recherche d'emploi dans UNE seule catégorie.

candidature :
La candidature a réellement été envoyée et l'entreprise confirme
qu'elle l'a reçue ou qu'elle va l'étudier.

entretien :
Un entretien est réellement proposé, organisé ou confirmé.

refus :
La candidature actuelle est explicitement refusée.

autre :
Tout le reste : offres d'emploi, alertes, suggestions,
questionnaires, "avez-vous postulé ?", candidatures non finalisées,
newsletters et notifications.

IMPORTANT :
- Une possibilité future d'entretien ne signifie PAS "entretien".
- "Avez-vous postulé ?" signifie "autre".
- Une candidature non finalisée signifie "autre".
- Une condition future de refus ne signifie PAS "refus".
- Si l'entreprise confirme avoir reçu la candidature, c'est "candidature".

Objet :
{subject}

Corps :
{full_body}

Réponds uniquement avec :
<category>candidature</category>
ou
<category>entretien</category>
ou
<category>refus</category>
ou
<category>autre</category>
"""

    try:

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.0,
            max_tokens=50,
        )

        raw_content = (
            response.choices[0].message.content
            or ""
        ).strip()

        # ====================================================
        # Extraction de la catégorie
        # ====================================================

        # Accepte :
        #
        # <category>candidature</category>
        #
        # mais également une réponse incomplète comme :
        #
        # <candidature>
        #
        # que Qwen a déjà produite pendant les tests.

        match = re.search(
            r"(?:<category>)?\s*"
            r"(candidature|entretien|refus|autre)"
            r"\s*(?:</category>)?",
            raw_content,
            re.IGNORECASE,
        )

        if match:
            return match.group(1).lower()

        print(
            f"\n⚠️ Réponse LLM invalide : "
            f"{raw_content}"
        )

        return "autre"

    except Exception as error:

        print(
            f"\n[ERREUR API] : {error}"
        )

        return "autre"


# ============================================================
# CLASSIFICATION D'UN EMAIL
# ============================================================

def classify_one_message(
    subject: str,
    body: str,
) -> str:
    """
    Classe un email.

    1. Règles déterministes
    2. LLM uniquement si aucune règle ne permet de trancher
    """

    rule_result = apply_rules(
        subject,
        body,
    )

    if rule_result is not None:
        return rule_result

    return classify_with_llm(
        subject,
        body,
    )


# ============================================================
# CLASSIFICATION DE PLUSIEURS EMAILS
# ============================================================

def classify_messages(
    messages: list[dict],
) -> list[dict]:
    """Classifie les emails un par un."""

    total = len(messages)

    for index, message in enumerate(
        messages,
        1,
    ):

        subject = message.get(
            "subject",
            "",
        )

        body = message.get(
            "body",
            "",
        )

        print(
            f"\n[{index}/{total}] "
            f"Objet: {subject[:50]}...",
            end="",
            flush=True,
        )

        category = classify_one_message(
            subject,
            body,
        )

        message["classification"] = category

        print(
            f" => {category}"
        )

    return messages


# ============================================================
# SAVE CLASSIFICATIONS
# ============================================================

def save_classified_messages(
    messages: list[dict],
    db_path: str,
):
    """Met à jour les classifications dans SQLite."""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    updated_count = 0

    for message in messages:

        message_id = message.get(
            "message_id"
        )

        classification = message.get(
            "classification"
        )

        if not message_id:
            print(
                "\n⚠️ Message sans message_id "
                "ignoré."
            )
            continue

        cursor.execute(
            f"""
            UPDATE "{TABLE_NAME}"
            SET classification = ?
            WHERE message_id = ?
            AND (
                classification IS NULL
                OR classification = ''
            )
            """,
            (
                classification,
                message_id,
            ),
        )

        updated_count += cursor.rowcount

    conn.commit()
    conn.close()

    print(
        f"\n✅ {updated_count} message(s) "
        f"classifié(s) dans {db_path}."
    )


# ============================================================
# MAIN
# ============================================================

def main():
    """Point d'entrée du classifier."""

    print(
        f"\n=== Chargement depuis {DB_PATH} ==="
    )

    messages = load_messages(
        DB_PATH,
        TABLE_NAME,
    )

    if not messages:
        print(
            "\n✅ Tous les messages sont "
            "déjà classifiés !"
        )
        return

    print(
        f"\n📧 {len(messages)} message(s) "
        "à classifier..."
    )

    classified_messages = classify_messages(
        messages
    )

    save_classified_messages(
        classified_messages,
        DB_PATH,
    )


if __name__ == "__main__":
    main()