# MED‑PRO Telegram Bot — стабильная версия через PubMed API + русские источники

import os
import json
import time
import requests
from datetime import datetime
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

# ================= НАСТРОЙКИ =================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MAX_ARTICLES_PER_DAY = 5
MEMORY_FILE = "sent_articles.json"

# Поисковые запросы PubMed (стабильные, не RSS)
PUBMED_QUERIES = {
    "🫁 Пульмонология": "pulmonary OR lung OR COPD OR asthma",
    "🌿 Аллергология": "allergy OR allergic OR rhinitis",
    "🩺 Терапия": "clinical treatment OR internal medicine",
}

# PubMed API
PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# ==============================================


def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(memory), f, ensure_ascii=False, indent=2)


def pubmed_search(query):
    """Получаем список ID статей за последние 7 дней"""
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": 10,
        "retmode": "json",
        "reldate": 7,
        "datetype": "pdat",
    }

    r = requests.get(PUBMED_SEARCH_URL, params=params, timeout=20)
    data = r.json()

    return data.get("esearchresult", {}).get("idlist", [])


def pubmed_fetch(pmid):
    """Получаем заголовок, аннотацию и ссылку"""
    params = {
        "db": "pubmed",
        "id": pmid,
        "retmode": "xml",
    }

    r = requests.get(PUBMED_FETCH_URL, params=params, timeout=20)
    text = r.text

    # очень простой парсинг без внешних библиотек
    def extract(tag):
        start = text.find(f"<{tag}>")
        end = text.find(f"</{tag}>")
        if start == -1 or end == -1:
            return ""
        return text[start + len(tag) + 2 : end]

    title = extract("ArticleTitle") or "Без заголовка"
    abstract = extract("AbstractText") or "Аннотация отсутствует."

    link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

    return title, abstract, link


def translate_to_russian(text: str) -> str:
    """Бесплатный перевод"""
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": "ru",
            "dt": "t",
            "q": text[:4000],
        }

        r = requests.get(url, params=params, timeout=20)
        data = r.json()

        return "".join(part[0] for part in data[0])

    except Exception:
        return text


def build_message(category: str, title: str, text: str, link: str):
    short_text = text[:1200] + "..." if len(text) > 1200 else text

    message = f"{category}\n\n<b>{title}</b>\n\n{short_text}"

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Читать полностью", url=link)]]
    )

    return message, keyboard


def main():
    print("=== MED‑PRO БОТ ЗАПУЩЕН ===")

    bot = Bot(token=TELEGRAM_TOKEN)
    memory = load_memory()

    sent_today = 0

    for category, query in PUBMED_QUERIES.items():
        pmids = pubmed_search(query)

        for pmid in pmids:
            if sent_today >= MAX_ARTICLES_PER_DAY:
                break

            if pmid in memory:
                continue

            title, abstract, link = pubmed_fetch(pmid)

            translated_title = translate_to_russian(title)
            translated_abstract = translate_to_russian(abstract)

            message, keyboard = build_message(category, translated_title, translated_abst

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
