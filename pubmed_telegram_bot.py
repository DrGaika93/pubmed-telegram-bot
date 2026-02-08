import os
import requests
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def get_latest_pubmed():
    """Берём последнюю статью по пульмонологии из PubMed API"""

    search_url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        "esearch.fcgi?db=pubmed&term=pulmonary+OR+asthma+OR+COPD+OR+allergy"
        "&sort=pub+date&retmax=1&retmode=json"
    )

    data = requests.get(search_url, timeout=20).json()
    ids = data["esearchresult"]["idlist"]

    if not ids:
        return None

    pubmed_id = ids[0]

    fetch_url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        f"esummary.fcgi?db=pubmed&id={pubmed_id}&retmode=json"
    )

    summary = requests.get(fetch_url, timeout=20).json()
    article = summary["result"][pubmed_id]

    title = article.get("title", "Без заголовка")
    link = f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/"

    return title, link


def send_to_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": False,
    }

    r = requests.post(url, json=payload, timeout=20)
    print("Telegram:", r.text)


def main():
    article = get_latest_pubmed()

    if not article:
        send_to_telegram("❌ Не удалось получить статью из PubMed")
        return

    title, link = article

    text = f"🩺 Новая статья PubMed\n\n{title}\n\nИсточник: {link}"

    send_to_telegram(text)


if __name__ == "__main__":
    main()
