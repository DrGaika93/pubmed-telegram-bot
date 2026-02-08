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
    "https://pubmed.ncbi.nlm.nih.gov/rss/search/1k3Jf7.xml",
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
    """Проверка всех RSS и отправка новых статей"""

    for rss_url in PUBMED_RSS_URLS:
        try:
            items = get_rss_items(rss_url)

            for item in items:
                link = item.get("link")

                if link in sent_links:
                    continue

                title = item.get("title", "Без заголовка")
                summary = item.get("summary", "")

                text = translate_and_summarize(title, summary, link)

                send_to_telegram(text)

                sent_links.add(link)

                # чтобы Telegram не заблокировал за частые сообщения
                time.sleep(2)

        except Exception as e:
            print("Ошибка обработки RSS:", e)

if __name__ == "__main__":
    process_feeds()
