import asyncio
import time
import json
import os
import requests
import feedparser
from bs4 import BeautifulSoup
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MEMORY_FILE = "memory.json"
MAX_ARTICLES_PER_DAY = 5
CYBERLENINKA_LIMIT = 3

TOPICS = {
    "🫁 Пульмонология": "pulmonology",
    "🌿 Аллергология": "allergy",
    "🩺 Терапия": "internal medicine",
}

CYBERLENINKA_RSS = {
    "🫁 Пульмонология": "https://cyberleninka.ru/rss/category/medicina/pulmonologiya",
    "🌿 Аллергология": "https://cyberleninka.ru/rss/category/medicina/allergologiya",
    "🩺 Терапия": "https://cyberleninka.ru/rss/category/medicina/terapiya",
}


# ================= MEMORY =================

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return set()
    with open(MEMORY_FILE, "r") as f:
        return set(json.load(f))


def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(list(memory), f)


# ================= PUBMED =================

def search_pubmed(query):
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        f"?db=pubmed&retmode=json&retmax=5&term={query}"
    )
    data = requests.get(url).json()
    return data.get("esearchresult", {}).get("idlist", [])


def fetch_pubmed_details(pmid):
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        f"?db=pubmed&id={pmid}&retmode=xml"
    )
    xml = requests.get(url).text

    soup = BeautifulSoup(xml, "xml")

    title = soup.find("ArticleTitle")
    abstract = soup.find("AbstractText")

    title = title.text if title else "Без названия"
    abstract = abstract.text if abstract else "Нет аннотации"

    link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

    return title, abstract, link


# ================= CYBERLENINKA =================

def parse_cyberleninka(category, rss_url):
    feed = feedparser.parse(rss_url)
    articles = []

    for entry in feed.entries[:3]:
        title = entry.title
        summary = BeautifulSoup(entry.summary, "html.parser").text
        link = entry.link
        articles.append((category, title, summary, link))

    return articles


# ================= TELEGRAM =================

def build_message(category, title, abstract, link):
    message = f"{category}\n\n<b>{title}</b>\n\n{abstract[:500]}..."

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Читать статью", url=link)]]
    )

    return message, keyboard

def parse_cyberleninka(query: str, limit: int = 3):
    print(f"Поиск КиберЛенинка: {query}")

    url = f"https://cyberleninka.ru/search?q={query}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        articles = []

        for item in soup.select(".search-item")[:limit]:
            title_tag = item.select_one(".title")
            link_tag = item.select_one("a")

            if not title_tag or not link_tag:
                continue

            title = title_tag.get_text(strip=True)
            link = "https://cyberleninka.ru" + link_tag["href"]

            summary = "Русскоязычная статья из КиберЛенинки"

            articles.append((title, summary, link))

        print(f"Найдено в КиберЛенинке: {len(articles)}")
        return articles

    except Exception as e:
        print("Ошибка КиберЛенинки:", e)
        return []


# ================= MAIN =================

def main():
    print("=== СТАРТ БОТА ===")

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Не заданы TELEGRAM_TOKEN или TELEGRAM_CHAT_ID")
        return

    bot = Bot(token=TELEGRAM_TOKEN)
    memory = load_memory()

    sent_pubmed = 0
    sent_cyber = 0

    # -------- PUBMED --------
    print("=== PUBMED ===")

    for category, query in TOPICS.items():
        pmids = search_pubmed(query)

        for pmid in pmids:
            if sent_pubmed >= MAX_ARTICLES_PER_DAY:
                break

            if pmid in memory:
                continue

            title, abstract, link = fetch_pubmed_details(pmid)

            title = translate_to_russian(title)
            abstract = translate_to_russian(abstract)

            message, keyboard = build_message(category, title, abstract, link)

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

            memory.add(pmid)
            sent_pubmed += 1
            time.sleep(2)

        if sent_pubmed >= MAX_ARTICLES_PER_DAY:
            break

    # -------- CYBERLENINKA --------
    print("=== КИБЕРЛЕНИНКА ===")

    if sent_pubmed < MAX_ARTICLES_PER_DAY:
        for category in TOPICS.keys():
            articles = parse_cyberleninka(category, limit=3)

            for title, summary, link in articles:
                if sent_pubmed + sent_cyber >= MAX_ARTICLES_PER_DAY:
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
                sent_cyber += 1
                time.sleep(2)

            if sent_pubmed + sent_cyber >= MAX_ARTICLES_PER_DAY:
                break

    save_memory(memory)

    print(f"✅ PubMed отправлено: {sent_pubmed}")
    print(f"✅ КиберЛенинка отправлено: {sent_cyber}")


# ================= RUN =================

if __name__ == "__main__":
    asyncio.run(main())
