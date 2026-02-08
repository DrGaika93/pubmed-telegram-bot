import os
import requests
from datetime import datetime, timedelta
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

# --- CONFIG ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# PubMed search: last 1 day, Russian language
PUBMED_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

SENT_FILE = "sent_articles.txt"
ARTICLES_PER_DAY = 5

bot = Bot(token=TELEGRAM_TOKEN)


def load_sent():
    if not os.path.exists(SENT_FILE):
        return set()
    with open(SENT_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)


def save_sent(pmid):
    with open(SENT_FILE, "a", encoding="utf-8") as f:
        f.write(pmid + "\n")


def search_pubmed():
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y/%m/%d")

    params = {
        "db": "pubmed",
        "term": "english[lang]",
        "reldate": 1,
        "datetype": "pdat",
        "retmax": 20,
        "retmode": "json",
    }

    r = requests.get(PUBMED_URL, params=params)
    r.raise_for_status()

    return r.json()["esearchresult"]["idlist"]


def get_summary(pmids):
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
    }

    r = requests.get(SUMMARY_URL, params=params)
    r.raise_for_status()

    return r.json()["result"]


def get_full_abstract(pmid):
    params = {
        "db": "pubmed",
        "id": pmid,
        "retmode": "xml",
    }

    r = requests.get(FETCH_URL, params=params)
    r.raise_for_status()

    return r.text


def format_message(title, abstract, url):
    text = f"*{title}*\n\n{abstract[:900]}..."

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Читать полностью", url=url)]]
    )

    return text, keyboard


def main():
    sent = load_sent()

    pmids = search_pubmed()
    new_pmids = [p for p in pmids if p not in sent][:ARTICLES_PER_DAY]

    if not new_pmids:
        print("No new articles")
        return

    summaries = get_summary(new_pmids)

    for pmid in new_pmids:
        article = summaries[pmid]

        title = article.get("title", "Без названия")
        abstract = article.get("elocationid", "Описание отсутствует")

        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

        text, keyboard = format_message(title, abstract, url)

        bot.send_message(
            chat_id=CHAT_ID,
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

        save_sent(pmid)


if __name__ == "__main__":
    main()
