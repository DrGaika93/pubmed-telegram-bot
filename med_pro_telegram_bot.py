print("ФАЙЛ ЗАГРУЖЕН ВЕРНЫЙ")
# med_pro_telegram_bot.py — FINAL FIXED VERSION

import os
import json
import time
import requests
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

# ================== НАСТРОЙКИ ==================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MAX_ARTICLES_PER_DAY = 5
MEMORY_FILE = "sent_articles.json"

PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

TOPICS = {
    "🫁 Пульмонология": "(asthma OR COPD OR pulmonary OR lung)",
    "🌿 Аллергология": "(allergy OR allergic OR rhinitis)",
    "🩺 Терапия": "(therapy OR treatment OR clinical)"
}

# =================================================


def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(memory), f, ensure_ascii=False, indent=2)


def translate_to_russian(text: str) -> str:
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": "ru",
            "dt": "t",
            "q": text,
        }
        r = requests.get(url, params=params, timeout=20)
        data = r.json()
        return "".join(part[0] for part in data[0])
    except Exception:
        return text


def search_pubmed(query: str):
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": 10,
        "sort": "pub date",
        "retmode": "json",
    }
    r = requests.get(PUBMED_API, params=params, timeout=20)
    return r.json()["esearchresult"]["idlist"]


def fetch_details(pmid: str):
    params = {
        "db": "pubmed",
        "id": pmid,
        "retmode": "xml",
    }
    r = requests.get(PUBMED_FETCH, params=params, timeout=20)
    text = r.text

    title_start = text.find("<ArticleTitle>")
    title_end = text.find("</ArticleTitle>")
    abstract_start = text.find("<AbstractText>")
    abstract_end = text.find("</AbstractText>")

    title = text[title_start + 14:title_end] if title_start != -1 else "Без заголовка"
    abstract = text[abstract_start + 14:abstract_end] if abstract_start != -1 else "Нет аннотации"

    link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

    return title, abstract, link


def build_message(category: str, title: str, text: str, link: str):
    short_text = text[:1200] + "..." if len(text) > 1200 else text

    message = (
        f"{category}\n\n"
        f"<b>{title}</b>\n\n"
        f"{short_text}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Читать полностью", url=link)]
    ])

    return message, keyboard


def main():
    print("=== СТАРТ БОТА ===")

    bot = Bot(token=TELEGRAM_TOKEN)
    memory = load_memory()
    sent_today = 0

    for category, query in TOPICS.items():
        pmids = search_pubmed(query)

        for pmid in pmids:
            if sent_today >= MAX_ARTICLES_PER_DAY:
                break

            if pmid in memory:
                continue

            title, abstract, link = fetch_details(pmid)

            translated_title = translate_to_russian(title)
            translated_abstract = translate_to_russian(abstract)

            message, keyboard = build_message(
                category,
                translated_title,
                translated_abstract,
                link,
            )

            bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )

            memory.add(pmid)
            sent_today += 1
            time.sleep(2)

        if sent_today >= MAX_ARTICLES_PER_DAY:
            break

    save_memory(memory)

    print(f"✅ Отправлено статей: {sent_today}")


if __name__ == "__main__":
    main()
