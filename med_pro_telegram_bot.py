print("ФАЙЛ ЗАГРУЖЕН ВЕРНЫЙ")
# FINAL STABLE PRO VERSION

import os
import json
import time
import requests
from bs4 import BeautifulSoup
import feedparser
from bs4 import BeautifulSoup
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

# ================= CONFIG =================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MAX_ARTICLES_PER_DAY = 8

# --- новые лимиты ---
PUBMED_LIMIT = 4
CYBERLENINKA_LIMIT = 4

MEMORY_FILE = "sent_articles.json"

PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Topics
TOPICS = {
    "🫁 Пульмонология": "(asthma OR COPD OR pulmonary OR lung)",
    "🌿 Аллергология": "(allergy OR allergic OR rhinitis)",
    "🩺 Терапия": "(therapy OR treatment OR clinical)",
}

# CyberLeninka RSS (RU full‑text source)
CYBERLENINKA_RSS = {
    "🫁 Пульмонология": "https://cyberleninka.ru/rss/category/pulmonologiya",
    "🌿 Аллергология": "https://cyberleninka.ru/rss/category/allergologiya",
    "🩺 Терапия": "https://cyberleninka.ru/rss/category/terapiya",
}

# ================= MEMORY =================

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(memory), f, ensure_ascii=False, indent=2)

# ================= HELPERS =================

def html_escape(t: str) -> str:
    return (
        t.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def translate_to_russian(text: str) -> str:
    """Free Google unofficial translate"""
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


# ================= TELEGRAM =================

def build_message(category: str, title: str, text: str, link: str):
    title = html_escape(title)
    text = html_escape(text)

    short_text = text[:1200] + "..." if len(text) > 1200 else text

    message = (
        f"{category}\n\n"
        f"<b>{title}</b>\n\n"
        f"{short_text}"
    )

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Читать полностью", url=link)]]
    )

    return message, keyboard


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
    xml = r.text

    def extract(tag):
        start = xml.find(f"<{tag}>")
        end = xml.find(f"</{tag}>")
        if start != -1 and end != -1:
            return xml[start + len(tag) + 2 : end]
        return ""

    title = extract("ArticleTitle") or "Без заголовка"
    abstract = extract("AbstractText") or "Нет аннотации"
    link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

    return title, abstract, link


# ================= CYBERLENINKA =================

def parse_cyberleninka_html(category, url, limit=4):
    articles = []

    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        items = soup.select(".article-item")

        for item in items[:limit]:
            title_tag = item.select_one(".article-item__title")
            link_tag = item.select_one("a")

            if not title_tag or not link_tag:
                continue

            title = title_tag.get_text(strip=True)
            link = "https://cyberleninka.ru" + link_tag.get("href")

            summary_tag = item.select_one(".article-item__annotation")
            summary = summary_tag.get_text(strip=True) if summary_tag else "Аннотация отсутствует"

            articles.append((category, title, summary, link))

    except Exception as e:
        print("Ошибка HTML-парсинга КиберЛенинки:", e)

    return articles



# ================= MAIN =================

import asyncio
import time
from telegram import Bot

async def main():
    print("=== СТАРТ БОТА ===")

    bot = Bot(token=TELEGRAM_TOKEN)

    memory = load_memory()
    sent_today = 0

    # -------- PUBMED --------
    print("=== PUBMED ===")

    for category, query in TOPICS.items():
        if sent_pubmed >= PUBMED_LIMIT:
            break

        pmids = search_pubmed(query)

        for pmid in pmids:
            if sent_pubmed >= PUBMED_LIMIT:
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
                print("Ошибка Telegram (PubMed):", e)
                continue

            memory.add(pmid)
            sent_pubmed += 1
            await asyncio.sleep(2)

    # -------- CYBERLENINKA --------
print("=== КИБЕРЛЕНИНКА ===")

sent_cyber = 0

if sent_today < MAX_ARTICLES_PER_DAY:
    for category, url in CYBERLENINKA_URLS.items():

        articles = parse_cyberleninka_html(category, url, limit=3)

        for _, title, summary, link in articles:
            if sent_today >= MAX_ARTICLES_PER_DAY:
                break

            if link in memory:
                continue

            message, keyboard = build_message(category, title, summary, link)

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


