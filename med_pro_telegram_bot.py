print("ФАЙЛ ЗАГРУЖЕН ВЕРНЫЙ")

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

CYBERLENINKA_TOPICS = {
    "🫁 Пульмонология": "пульмонология",
    "🌿 Аллергология": "аллергия",
    "🩺 Терапия": "терапия",
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

def main():
    print("=== СТАРТ БОТА ===")

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Нет TELEGRAM_TOKEN или TELEGRAM_CHAT_ID")
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
            if sent_pubmed >= 3:
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
                print("Ошибка Telegram PubMed:", e)
                continue

            memory.add(pmid)
            sent_pubmed += 1
            time.sleep(2)

    # -------- CYBERLENINKA --------
    print("=== КИБЕРЛЕНИНКА ===")

    for category, query in CYBERLENINKA_TOPICS.items():
        articles = parse_cyberleninka(query)

        for title, summary, link in articles:
            if sent_cyber >= 2:
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
                print("Ошибка Telegram КиберЛенинка:", e)
                continue

            memory.add(link)
            sent_cyber += 1
            time.sleep(2)

    save_memory(memory)

    print(f"✅ PubMed отправлено: {sent_pubmed}")
    print(f"✅ КиберЛенинка отправлено: {sent_cyber}")


if __name__ == "__main__":
    main()
