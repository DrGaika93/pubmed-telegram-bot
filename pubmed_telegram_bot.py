import os
import json
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

# ================= CONFIG =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

ARTICLES_PER_DAY = 5
MEMORY_FILE = "sent_articles.json"

TOPICS = [
    "pulmonology",
    "allergology",
    "internal medicine",
]

# Open‑access RSS sources
RSS_FEEDS = [
    "https://www.ncbi.nlm.nih.gov/pmc/articles/rss/",
    "https://doaj.org/feed?subject=Medicine",
]

# ==========================================

bot = Bot(token=TELEGRAM_TOKEN)


def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return set()
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return set(json.load(f))


def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(memory), f, ensure_ascii=False, indent=2)


def fetch_rss_articles():
    articles = []

    for feed in RSS_FEEDS:
        try:
            r = requests.get(feed, timeout=15)
            soup = BeautifulSoup(r.text, "xml")

            for item in soup.find_all("item"):
                title = item.title.text if item.title else ""
                link = item.link.text if item.link else ""
                description = item.description.text if item.description else ""

                text_blob = f"{title} {description}".lower()

                if any(topic in text_blob for topic in TOPICS):
                    articles.append({
                        "title": title,
                        "link": link,
                        "description": description,
                    })
        except Exception:
            continue

    return articles


def extract_full_text(url):
    try:
        r = requests.get(url, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        paragraphs = soup.find_all("p")
        text = "\n".join(p.get_text() for p in paragraphs[:20])

        return text.strip()
    except Exception:
        return "Не удалось получить полный текст статьи."


def translate_to_russian(text):
    try:
        api_url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": "ru",
            "dt": "t",
            "q": text,
        }
        r = requests.get(api_url, params=params, timeout=15)
        data = r.json()

        return "".join(part[0] for part in data[0])
    except Exception:
        return text


def send_article(article):
    full_text = extract_full_text(article["link"])
    translated = translate_to_russian(full_text[:3000])

    message = f"<b>{article['title']}</b>\n\n{translated}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Читать полностью", url=article["link"])],
    ])

    bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=message,
        parse_mode="HTML",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


def main():
    memory = load_memory()
    articles = fetch_rss_articles()

    sent_today = 0

    for article in articles:
        if article["link"] in memory:
            continue

        send_article(article)

        memory.add(article["link"])
        sent_today += 1

        if sent_today >= ARTICLES_PER_DAY:
            break

    save_memory(memory)


if __name__ == "__main__":
    main()
