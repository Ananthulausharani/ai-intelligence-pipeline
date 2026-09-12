import urllib.request
from bs4 import BeautifulSoup
import re

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

req = urllib.request.Request("https://theresanaiforthat.com/", headers=headers)
with urllib.request.urlopen(req, timeout=10) as r:
    html = r.read().decode("utf-8", errors="replace")

soup = BeautifulSoup(html, "html.parser")
items = soup.select("li.ai_item, .ai_card, div[data-name]")
print("TAAFT items found:", len(items))
for it in items[:5]:
    name = it.get("data-name") or it.find("h3") or it.find("span")
    text = it.get_text(separator=" | ").strip()
    # Check for pricing keywords
    pricing = None
    for p in ["Free", "Freemium", "Paid", "Free Trial", "Contact for Pricing"]:
        if p.lower() in text.lower():
            pricing = p
            break
    links = [a.get("href") for a in it.find_all("a", href=True) if "/ai/" in a.get("href")]
    print(f"Name: {name} | Pricing: {pricing} | Link: {links[:1]}")
