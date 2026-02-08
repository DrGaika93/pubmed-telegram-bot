print("ФАЙЛ ЗАГРУЖЕН ВЕРНЫЙ")
# med_pro_telegram_bot.py — FINAL ABSOLUTE STABLE VERSION

import os
import json
import time
import requests
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

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


def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(memory), f, ensure_ascii=False, indent=2)


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

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Читать полностью", url=link)]
    ])

    return message, keyboard


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

            message, keyboard = build_message(category, translated_title, translated_abstract, link)

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

    save_memory(memory)
    print(f"✅ Отправлено статей: {sent_today}")


if __name__ == "__main__":
    main()

# === DAILY AUTORUN SETUP ===

## Option 1: Cron (Linux / Railway)
# Run the bot every day at 09:00:

```bash
0 9 * * * python med_pro_telegram_bot.py
```

## Option 2: GitHub Actions
Create file `.github/workflows/daily.yml`:

```yaml
name: Daily PubMed Post

on:
  schedule:
    - cron: '0 9 * * *'
  workflow_dispatch:

jobs:
  run-bot:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run bot
        env:
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          CHAT_ID: ${{ secrets.CHAT_ID }}
        run: python med_pro_telegram_bot.py
```

---

# === BEAUTIFUL TELEGRAM POST FORMAT ===

def format_telegram_post(title, journal, date, summary, link):
    return f"""
🧠 <b>{title}</b>

📚 <i>{journal}</i>
📅 {date}

📝 <b>Summary:</b>
{summary}

🔗 <a href='{link}'>Read full article</a>

#PubMed #EvidenceBasedMedicine
""".strip()


# Example usage:
# message = format_telegram_post(title, journal, date, summary, link)
# bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="HTML", disable_web_page_preview=False)

---

# === OPTIONAL: EMOJI BY STUDY TYPE ===

def emoji_by_study_type(study_type: str) -> str:
    mapping = {
        "randomized controlled trial": "💊",
        "meta-analysis": "📊",
        "systematic review": "📚",
        "clinical guideline": "📜",
        "cohort study": "👥",
    }

    study_type = study_type.lower()

    for key, emoji in mapping.items():
        if key in study_type:
            return emoji

    return "🔬"

---

# Next possible upgrades:
# - OpenAI auto-summary
# - Filtering only RCT / Meta-analysis
# - Multi-post daily digest

