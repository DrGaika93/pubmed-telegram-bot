import requests
import time
import feedparser
from datetime import datetime

# ===================== НАСТРОЙКИ =====================

import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# PubMed RSS по пульмонологии / аллергологии / терапии
PUBMED_RSS_URLS = [
    # Астма
    "https://pubmed.ncbi.nlm.nih.gov/rss/search/?term=asthma&filter=simsearch1.fha&filter=pubt.meta-analysis&size=50",

    # ХОБЛ
    "https://pubmed.ncbi.nlm.nih.gov/rss/search/?term=COPD&filter=simsearch1.fha&size=50",

    # Интерстициальные заболевания лёгких
    "https://pubmed.ncbi.nlm.nih.gov/rss/search/?term=interstitial+lung+disease&size=50",

    # Аллергия
    "https://pubmed.ncbi.nlm.nih.gov/rss/search/?term=allergy&size=50",

    # Общая пульмонология
    "https://pubmed.ncbi.nlm.nih.gov/rss/search/?term=pulmonary&size=50",
]

CHECK_INTERVAL_MINUTES = 60  # как часто проверять новые статьи

# ======================================================

sent_links = set()


def get_rss_items(url: str):
    """Получаем статьи из RSS"""
    feed = feedparser.parse(url)
    return feed.entries


def translate_and_summarize(title: str, summary: str, link: str) -> str:
    """
    ПРОСТОЕ текстовое саммари БЕЗ ИИ (полностью бесплатно)
    """

    text = f"""
🩺 Новая медицинская статья

<b>{title}</b>

{summary[:800]}...

Источник: {link}
"""

    return text.strip()


def send_to_telegram(text: str):
    """Отправка сообщения в Telegram"""

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    response = requests.post(url, json=payload, timeout=20)

    print("TELEGRAM STATUS:", response.status_code)
    print("TELEGRAM RESPONSE:", response.text)


def process_feeds():
    """Диагностика RSS PubMed"""

    for rss_url in PUBMED_RSS_URLS:
        print("Проверяем RSS:", rss_url)

        items = get_rss_items(rss_url)

        print("Найдено статей:", len(items))

        if not items:
            send_to_telegram("❌ RSS пустой. Статей не найдено.")
            return

        item = items[0]

        title = item.get("title", "Без заголовка")
        summary = item.get("summary", "")
        link = item.get("link", "")

        text = translate_and_summarize(title, summary, link)

        send_to_telegram("✅ RSS работает. Отправляю статью:\n\n" + text)



if __name__ == "__main__":
    process_feeds()


