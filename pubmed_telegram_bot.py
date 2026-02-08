import os
import requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def translate_to_russian(text: str) -> str:
    """Бесплатный перевод через LibreTranslate"""

    url = "https://libretranslate.de/translate"

    payload = {
        "q": text,
        "source": "en",
        "target": "ru",
        "format": "text",
    }

    try:
        r = requests.post(url, data=payload, timeout=20)
        return r.json()["translatedText"]
    except Exception:
        return text  # если перевод не сработал — отправим оригинал


def get_latest_pubmed():
    """Получаем последнюю статью PubMed"""

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

    title_en = article.get("title", "No title")
    link = f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/"

    title_ru = translate_to_russian(title_en)

    return title_ru, link


def send_to_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": False,
    }

    requests.post(url, json=payload, timeout=20)


def main():
    article = get_latest_pubmed()

    if not article:
        send_to_telegram("❌ Не удалось получить статью PubMed")
        return

    title, link = article

    text = f"🩺 Новая статья PubMed\n\n{title}\n\nИсточник: {link}"

    send_to_telegram(text)


if __name__ == "__main__":
    main()
