import os
import requests
from bs4 import BeautifulSoup
from telegram import Bot

# Environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Search URL for Russian-language articles on PubMed
PUBMED_URL = "https://pubmed.ncbi.nlm.nih.gov/?term=russian+language&filter=simsearch2.ffrft"


def get_latest_article():
    """Fetch the latest article title, abstract, and link from PubMed."""
    response = requests.get(PUBMED_URL, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    article = soup.select_one("article.full-docsum")
    if not article:
        return None

    title_tag = article.select_one("a.docsum-title")
    if not title_tag:
        return None

    title = title_tag.get_text(strip=True)
    link = "https://pubmed.ncbi.nlm.nih.gov" + title_tag["href"]

    # Open article page to get abstract
    article_page = requests.get(link, timeout=15)
    article_page.raise_for_status()

    article_soup = BeautifulSoup(article_page.text, "html.parser")

    abstract_block = article_soup.select_one("div.abstract-content")
    if abstract_block:
        abstract = abstract_block.get_text(" ", strip=True)
    else:
        abstract = "Аннотация отсутствует."

    return title, abstract, link


def send_to_telegram(text: str):
    """Send message to Telegram."""
    bot = Bot(token=TELEGRAM_TOKEN)
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)


def main():
    article = get_latest_article()

    if not article:
        send_to_telegram("Не удалось найти новые статьи в русских журналах.")
        return

    title, abstract, link = article

    message = f"📚 {title}\n\n{abstract}\n\nИсточник: {link}"
    send_to_telegram(message)


if __name__ == "__main__":
    main()
