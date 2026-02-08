print("ФАЙЛ ЗАГРУЖЕН ВЕРНЫЙ")

import os
import json
import time
import requests
from bs4 import BeautifulSoup
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MAX_ARTICLES_PER_DAY = 8
MEMORY_FILE = "sent_articles.json"

PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

TOPICS = {
    "🫁 Пульмонология": "(asthma OR COPD OR pulmonary OR lung)",
    "🌿 Аллергология": "(allergy OR allergic OR rhinitis)",
    "🩺 Терапия": "(therapy OR treatment OR clinical)",
}

CYBERLENINKA_URLS = {
    "🫁 Пульмонология": "https://cyberleninka.ru/search?q=пульмонология",
    "🌿 Аллергология": "https://cyberleninka.ru/search?q=аллергология",
    "🩺 Терапия": "https://cyberleninka.ru/search?q=терапия",
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


def fetch_details(pmid: str):
    params = {"db": "pubmed", "id": pmid, "retmode": "xml"}
    r = requests.get(PUBMED_FETCH, params=params, timeout=20)
    text = r.text

    def extract(tag):
        start = text.find(f"<{tag}>")
        end = text.find(f"</{tag}>")
        if start != -1 and end != -1:
            return text[start + len(tag) + 2 : end]
        return ""

    title = extract("ArticleTitle") or "Без заголовка"
    abstract = extract("AbstractText") or "Нет аннотации"
    link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

    return title, abstract, link


# ================= CYBERLENINKA =================

def parse_cyberleninka(category, url):
    print(f"Проверяем КиберЛенинку: {category}")

    articles = []

    try:
        r = requests.get(url, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        items = soup.select(".article-item")

        for item in items[:5]:
            title_tag = item.select_one(".title")
            link_tag = item.select_one("a")

            if not title_tag or not link_tag:
                continue

            title = title_tag.get_text(strip=True)
            link = "https://cyberleninka.ru" + link_tag["href"]

            articles.append((title, "Русскоязычная статья из КиберЛенинки.", link))

    except Exception as e:
        print("Ошибка парсинга КиберЛенинки:", e)

    return articles


# ================= TELEGRAM MESSAGE =================

def html_escape(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
        [[InlineKeyboardButton("📖 Читать полностью", url=link)]]
    )

    return message, keyboard


# ================= MAIN =================

def main():
    print("=== СТАРТ БОТА ===")

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Не заданы TELEGRAM_TOKEN или TELEGRAM_CHAT_ID")
        return

    bot = Bot(token=TELEGRAM_TOKEN)
    memory = load_memory()
    sent_today = 0

    # -------- СНАЧАЛА КИБЕРЛЕНИНКА --------
    print("=== КИБЕРЛЕНИНКА ===")

    for category, url in CYBERLENINKA_URLS.items():
        if sent_today >= MAX_ARTICLES_PER_DAY:
            break

        articles = parse_cyberleninka(category, url)

        for title, abstract, link in articles:
            if sent_today >= MAX_ARTICLES_PER_DAY:
                break

            if link in memory:
                continue

            message, keyboard = build_message(category, title, abstract, link)

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

    # -------- ПОТОМ PUBMED (если не хватило статей) --------
    print("=== PUBMED ===")

    for category, query in TOPICS.items():
        if sent_today >= MAX_ARTICLES_PER_DAY:
            break

        pmids = search_pubmed(query)

        for pmid in pmids:
            if sent_today >= MAX_ARTICLES_PER_DAY:
                break

            if pmid in memory:
                continue

            title, abstract, link = fetch_details(pmid)

            title = translate_to_russian(title)
            abstract = translate_to_russian(abstract)

            message, keyboard = build_message(category, title, abstract, link)

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

    save_memory(memory)
    print(f"✅ Отправлено статей: {sent_today}")


if __name__ == "__main__":
    main()
