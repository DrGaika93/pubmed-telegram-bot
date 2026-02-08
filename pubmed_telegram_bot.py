print("=== СТАРТ БОТА ===")

import os
import json
import time
import requests
import feedparser
from bs4 import BeautifulSoup
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MAX_ARTICLES_PER_DAY = 5
MEMORY_FILE = "sent_articles.json"

SOURCES = {
    "🫁 Пульмонология": [
        "https://pubmed.ncbi.nlm.nih.gov/rss/search/1k3Jf7.xml",
    ],
    "🌿 Аллергология": [
        "https://pubmed.ncbi.nlm.nih.gov/rss/search/1k3Jf8.xml",
    ],
    "🩺 Терапия": [
        "https://pubmed.ncbi.nlm.nih.gov/rss/search/1k3Jf9.xml",
    ],
}

TOPIC_KEYWORDS = [
    "lung", "pulmonary", "asthma", "copd",
    "allergy", "allergic", "rhinitis",
    "therapy", "treatment", "clinical",
]


def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(memory), f, ensure_ascii=False, indent=2)


def get_full_text(url: str) -> str:
    try:
        r = requests.get(url, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        paragraphs = soup.find_all("p")
        text = "\n".join(p.get_text(strip=True) for p in paragraphs)
        return text[:4000] if text else "Полный текст недоступен."
    except Exception:
        return "Не удалось получить полный текст статьи."


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


def is_relevant(title: str, summary: str) -> bool:
    text = f"{title} {summary}".lower()
    return any(word in text for word in TOPIC_KEYWORDS)


def parse_rss(url: str):
    return feedparser.parse(url).entries


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
    print("=== ВНУТРИ MAIN ===")

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ TELEGRAM_TOKEN или TELEGRAM_CHAT_ID пустые")
        return

    bot = Bot(token=TELEGRAM_TOKEN)
    memory = load_memory()
    sent_today = 0

    for category, urls in SOURCES.items():
        for rss in urls:
            entries = parse_rss(rss)

            for e in entries:
                if sent_today >= MAX_ARTICLES_PER_DAY:
                    break

                link = e.get("link")
                title = e.get("title", "Без заголовка")
                summary = e.get("summary", "")

                if not link or link in memory:
                    continue

                if not is_relevant(title, summary):
                    continue

                print("Отправляем статью:", title)

                full_text = get_full_text(link)
                translated = translate_to_russian(full_text)

                message, keyboard = build_message(category, title, translated, link)

                bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=message,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )

                memory.add(link)
                sent_today += 1
                time.sleep(2)

            if sent_today >= MAX_ARTICLES_PER_DAY:
                break

    save_memory(memory)
    print(f"✅ Отправлено статей: {sent_today}")


if __name__ == "__main__":
    main()
