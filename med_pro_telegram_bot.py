print("ФАЙЛ ЗАГРУЖЕН ВЕРНЫЙ")

import os
import json
import time
import requests
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from bs4 import BeautifulSoup

# === КИБЕРЛЕНИНКА ===
CYBERLENINKA_TOPICS = {
    "🫁 Пульмонология": "https://cyberleninka.ru/search?q=пульмонология",
    "🌿 Аллергология": "https://cyberleninka.ru/search?q=аллергология",
    "🩺 Терапия": "https://cyberleninka.ru/search?q=терапия",
}


def parse_cyberleninka(search_url: str, limit: int = 5):
    try:
        r = requests.get(search_url, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        articles = []

        for item in soup.select(".article-list-item")[:limit]:
            title_tag = item.select_one(".article-title")
            link_tag = item.select_one("a")

            if not title_tag or not link_tag:
                continue

            title = title_tag.get_text(strip=True)
            link = "https://cyberleninka.ru" + link_tag["href"]

            articles.append((title, link))

        return articles

    except Exception as e:
        print("Ошибка парсинга КиберЛенинки:", e)
        return []


def fetch_cyberleninka_text(url: str):
    try:
        r = requests.get(url, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        abstract = soup.select_one(".full.abstract")
        if abstract:
            return abstract.get_text(strip=True)

        paragraphs = soup.select(".ocr p")
        text = "\n".join(p.get_text(strip=True) for p in paragraphs[:5])

        return text if text else "Нет аннотации."

    except Exception:
        return "Не удалось получить текст статьи."


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MAX_ARTICLES_PER_DAY = 7
MEMORY_FILE = "sent_articles.json"

PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


TOPICS = {
    "🫁 Пульмонология": "(asthma OR COPD OR pulmonary OR lung)",
    "🌿 Аллергология": "(allergy OR allergic OR rhinitis)",
    "🩺 Терапия": "(therapy OR treatment OR clinical)",
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


# ================= FORMAT =================

def html_escape(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_telegram_post(category, title, abstract, link):
    title = html_escape(title)
    abstract = html_escape(abstract)

    short_text = abstract[:1200] + "..." if len(abstract) > 1200 else abstract

    message = (
        f"{category}\n\n"
        f"🧠 <b>{title}</b>\n\n"
        f"{short_text}\n\n"
        f"🔗 <a href='{link}'>Читать полностью на PubMed</a>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Открыть статью", url=link)]
    ])

    return message, keyboard


# ================= MAIN =================
from bs4 import BeautifulSoup


CYBERLENINKA_URLS = {
    "🫁 Пульмонология": "https://cyberleninka.ru/search?q=пульмонология",
    "🌿 Аллергология": "https://cyberleninka.ru/search?q=аллергология",
    "🩺 Терапия": "https://cyberleninka.ru/search?q=терапия",
}


def parse_cyberleninka(category: str):
    """
    Возвращает список статей:
    [(title, abstract, link), ...]
    """

    try:
        url = CYBERLENINKA_URLS.get(category)
        if not url:
            return []

        r = requests.get(url, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        articles = []

        items = soup.select(".article-item")

        for item in items[:5]:

            title_tag = item.select_one(".title")
            link_tag = item.select_one("a")

            if not title_tag or not link_tag:
                continue

            title = title_tag.get_text(strip=True)
            link = "https://cyberleninka.ru" + link_tag.get("href")

            # Пытаемся открыть страницу статьи и взять аннотацию
            abstract = "Аннотация не найдена"

            try:
                art_page = requests.get(link, timeout=20)
                art_soup = BeautifulSoup(art_page.text, "html.parser")

                abs_tag = art_soup.select_one(".full.abstract")
                if abs_tag:
                    abstract = abs_tag.get_text(strip=True)

            except Exception:
                pass

            articles.append((title, abstract, link))

        return articles

    except Exception as e:
        print("Ошибка парсинга КиберЛенинки:", e)
        return []

def main():
    print("=== СТАРТ БОТА ===")

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Не заданы TELEGRAM_TOKEN или TELEGRAM_CHAT_ID")
        return

    bot = Bot(token=TELEGRAM_TOKEN)
    memory = load_memory()
    sent_today = 0

    for category, query in TOPICS.items():
        pmids = search_pubmed(query)

        for pmid in pmids:

            if sent_today >= MAX_ARTICLES_PER_DAY:
                break

            if pmid in memory:
                continue

            title, abstract, link = fetch_details(pmid)

            translated_title = translate_to_russian(title)
            translated_abstract = translate_to_russian(abstract)

            message, keyboard = format_telegram_post(
                category,
                translated_title,
                translated_abstract,
                link,
            )

            try:
                bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=message,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
            except Exception as e:
                print("Ошибка отправки в Telegram:", e)
                continue

            memory.add(pmid)
            sent_today += 1
            time.sleep(2)

        if sent_today >= MAX_ARTICLES_PER_DAY:
            break
    # === КИБЕРЛЕНИНКА ===
    for category, url in CYBERLENINKA_TOPICS.items():
        articles = parse_cyberleninka(url)

        for title, link in articles:
            if sent_today >= MAX_ARTICLES_PER_DAY:
                break

            if link in memory:
                continue

            abstract = fetch_cyberleninka_text(link)

            message, keyboard = build_message(
                category,
                title,
                abstract,
                link
            )

            try:
                bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=message,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
            except Exception as e:
                print("Ошибка отправки КиберЛенинки:", e)
                continue

            memory.add(link)
            sent_today += 1
            time.sleep(2)
# ===== КИБЕРЛЕНИНКА =====
    print("=== КИБЕРЛЕНИНКА ===")

    for category in TOPICS.keys():

        articles = parse_cyberleninka(category)

        for title, abstract, link in articles:

            if sent_today >= MAX_ARTICLES_PER_DAY:
                break

            uid = link

            if uid in memory:
                continue

            translated_title = translate_to_russian(title)
            translated_abstract = translate_to_russian(abstract)

            message, keyboard = build_message(
                category,
                translated_title,
                translated_abstract,
                link
            )

            try:
                bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=message,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
            except Exception as e:
                print("Ошибка отправки КиберЛенинки:", e)
                continue

            memory.add(uid)
            sent_today += 1
            time.sleep(2)
            
    save_memory(memory)
    print(f"✅ Отправлено статей: {sent_today}")


# ================= RUN =================

if __name__ == "__main__":
    main()
