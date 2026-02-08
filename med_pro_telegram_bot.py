print("ФАЙЛ ЗАГРУЖЕН ВЕРНЫЙ")
import feedparser
import os
import json
import time
import requests
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MAX_ARTICLES_PER_DAY = 5
MEMORY_FILE = "sent_articles.json"

PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

TOPICS = {
    "🫁 Пульмонология": "(asthma OR COPD OR pulmonary OR lung)",
    "🌿 Аллергология": "(allergy OR allergic OR rhinitis)",
    "🩺 Терапия": "(therapy OR treatment OR clinical)",
}

CYBERLENINKA_RSS = {
    "🫁 Пульмонология": "https://cyberleninka.ru/rss/pulmonologiya",
    "🌿 Аллергология": "https://cyberleninka.ru/rss/allergologiya",
    "🩺 Терапия": "https://cyberleninka.ru/rss/terapiya",
}

CYBERLENINKA_LIMIT = 2



# ================= MEMORY =================

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(memory), f, ensure_ascii=False, indent=2)


# ================= TRANSLATE =================

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


# ================= PUBMED =================

def search_pubmed(query: str):
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": 10,
        "sort": "pub date",
        "retmode": "json",
    }
    r = requests.get(PUBMED_API, params=params, timeout=20)
    return r.json().get("esearchresult", {}).get("idlist", [])


def fetch_pubmed_details(pmid: str):
    params = {"db": "pubmed", "id": pmid, "retmode": "xml"}
    r = requests.get(PUBMED_FETCH, params=params, timeout=20)

    soup = BeautifulSoup(r.text, "html.parser")

    title = soup.find("articletitle")
    abstract = soup.find("abstracttext")

    title = title.get_text(strip=True) if title else "Без заголовка"
    abstract = abstract.get_text(strip=True) if abstract else "Нет аннотации"

    link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

    return title, abstract, link


# ================= CYBERLENINKA =================

def parse_cyberleninka_rss(category: str, url: str):
    print(f"RSS КиберЛенинка: {category}")

    try:
        feed = feedparser.parse(url)
        articles = []

        for entry in feed.entries[:CYBERLENINKA_LIMIT]:
            title = entry.title
            link = entry.link
            summary = entry.summary if "summary" in entry else "Русскоязычная статья"

            articles.append((title, summary, link))

        print(f"Найдено RSS-статей: {len(articles)}")
        return articles

    except Exception as e:
        print("Ошибка RSS КиберЛенинки:", e)
        return []


# ================= TELEGRAM MESSAGE =================

def html_escape(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_message(category: str, title: str, text: str, link: str):
    title = html_escape(title)
    text = html_escape(text)

    short_text = text[:1000] + "..." if len(text) > 1000 else text

    message = (
        f"{category}\n\n"
        f"<b>{title}</b>\n\n"
        f"{short_text}"
    )

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Читать полностью", url=link)]]
    )

    return message, keyboard


# ================= MAIN =================

async def main():
    print("=== СТАРТ БОТА ===")

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Не заданы TELEGRAM_TOKEN или TELEGRAM_CHAT_ID")
        return

    bot = Bot(token=TELEGRAM_TOKEN)

    memory = load_memory()
    sent_today = 0
    sent_cyber = 0

    # ========= PUBMED =========
    print("=== PUBMED ===")

    for category, query in TOPICS.items():
        pmids = search_pubmed(query)

        for pmid in pmids:
            if sent_today >= MAX_ARTICLES_PER_DAY:
                break

            if pmid in memory:
                continue

            title, abstract, link = fetch_pubmed_details(pmid)

            title = translate_to_russian(title)
            abstract = translate_to_russian(abstract)

            message, keyboard = build_message(category, title, abstract, link)

            try:
                await bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=message,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
            except Exception as e:
                print("Ошибка Telegram:", e)
                continue

            memory.add(pmid)
            sent_today += 1
            time.sleep(2)

        if sent_today >= MAX_ARTICLES_PER_DAY:
            break

    # ========= CYBERLENINKA =========
   print("=== КИБЕРЛЕНИНКА ===")

sent_cyber = 0

if sent_today < MAX_ARTICLES_PER_DAY:
    for category, rss_url in CYBERLENINKA_RSS.items():

        articles = parse_cyberleninka_rss(category, rss_url)

        for title, summary, link in articles:

            if sent_today >= MAX_ARTICLES_PER_DAY:
                break

            if link in memory:
                continue

            message, keyboard = build_message(category, title, summary, link)

            try:
                bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=message,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
            except Exception as e:
                print("Ошибка Telegram:", e)
                continue

            memory.add(link)
            sent_today += 1
            sent_cyber += 1
            time.sleep(2)

        if sent_today >= MAX_ARTICLES_PER_DAY:
            break

print(f"✅ КиберЛенинка отправлено: {sent_cyber}")



if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
