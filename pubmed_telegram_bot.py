import os
import time
import requests
from bs4 import BeautifulSoup

# ===================== НАСТРОЙКИ =====================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Русские медицинские журналы (страницы последних публикаций)
SOURCES = [
    {
        "name": "Пульмонология",
        "url": "https://journal.pulmonology.ru/pulm/issue/current",
        "article_selector": "div.title a",
        "content_selector": "div.article-summary, div.abstract, section.abstract",
    },
    {
        "name": "Russian Journal of Allergy",
        "url": "https://rusalljournal.ru/raj/issue/current",
        "article_selector": "div.title a",
        "content_selector": "div.article-summary, div.abstract, section.abstract",
    },
]

HEADERS = {"User-Agent": "Mozilla/5.0"}

# ======================================================


def send_to_telegram(text: str):
    """Отправка сообщения в Telegram"""

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    r = requests.post(url, json=payload, timeout=20)
    print("Telegram:", r.text)



def get_article_text(link: str, selector: str) -> str:
    """Получаем текст аннотации или статьи"""

    try:
        r = requests.get(link, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        blocks = soup.select(selector)

        if not blocks:
            return "Текст статьи не найден."

        text = "\n".join(b.get_text(" ", strip=True) for b in blocks)

        # ограничим длину для Telegram (до ~3500 символов)
        return text[:3500]

    except Exception as e:
        print("Ошибка получения текста статьи:", e)
        return "Не удалось загрузить текст статьи."



def get_latest_article_from_source(source):
    """Парсим страницу журнала и берём первую реальную статью"""

    try:
        r = requests.get(source["url"], headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        links = soup.select(source["article_selector"])

        if not links:
            return None

        article_link = links[0]

        title = article_link.get_text(strip=True)
        link = article_link.get("href")

        if not title or not link:
            return None

        # если ссылка относительная — делаем абсолютную
        if link.startswith("/"):
            base = source["url"].split("/", 3)[:3]
            base_url = "/".join(base)
            link = base_url + link

        # получаем текст статьи
        content = get_article_text(link, source["content_selector"])

        return title, link, source["name"], content

    except Exception as e:
        print("Ошибка парсинга", source["name"], e)
        return None



def main():
    """Получаем по одной статье из каждого журнала"""

    sent_any = False

    for source in SOURCES:
        article = get_latest_article_from_source(source)

        if not article:
            continue

        title, link, source_name, content = article

        text = (
            f"🩺 <b>Новая статья</b>\n\n"
            f"<b>{title}</b>\n\n"
            f"{content}\n\n"
            f"Источник: {source_name}\n"
            f"{link}"
        )

        send_to_telegram(text)
        sent_any = True

        time.sleep(2)

    if not sent_any:
        send_to_telegram("❌ Не удалось найти новые статьи в русских журналах")


if __name__ == "__main__":
    main()
