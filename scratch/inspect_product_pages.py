import urllib.request
from bs4 import BeautifulSoup
import re
import json

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

# Inspect FutureTools
try:
    req = urllib.request.Request("https://www.futuretools.io/", headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    # Look for product cards / links
    tool_cards = soup.select(".tool-card, .tool-item, .w-dyn-item, a[href*='/tool/'], a[href*='/tools/']")
    print("FutureTools cards found:", len(tool_cards))
    if tool_cards:
        first = tool_cards[0]
        print("  Sample FutureTools:", first.get_text(separator=" | ").strip()[:200])
except Exception as e:
    print("FutureTools Error:", e)

# Inspect TAAFT
try:
    req = urllib.request.Request("https://theresanaiforthat.com/", headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    ai_cards = soup.select(".ai_card, .listing-item, a[href*='/ai/']")
    print("TAAFT cards found:", len(ai_cards))
    if ai_cards:
        for c in ai_cards[:3]:
            print("  Sample TAAFT link:", c.get("href"), "|", c.get_text(separator=" | ").strip()[:150])
except Exception as e:
    print("TAAFT Error:", e)

# Inspect Hugging Face Spaces
try:
    req = urllib.request.Request("https://huggingface.co/api/spaces?limit=5&full=false", headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        spaces = json.loads(r.read())
    print("HF Spaces sample:", len(spaces))
    for s in spaces[:3]:
        print("  Space ID:", s.get("id"), "Author/Company:", s.get("author"), "URL:", f"https://huggingface.co/spaces/{s.get('id')}")
except Exception as e:
    print("HF Spaces Error:", e)
