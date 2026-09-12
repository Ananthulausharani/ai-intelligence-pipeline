import urllib.request
from bs4 import BeautifulSoup

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

req = urllib.request.Request("https://theresanaiforthat.com/", headers=headers)
with urllib.request.urlopen(req, timeout=10) as r:
    html = r.read().decode("utf-8", errors="replace")

soup = BeautifulSoup(html, "html.parser")
ai_links = soup.select("a[href*='/ai/']")
print("Total ai links:", len(ai_links))
for a in ai_links[:8]:
    parent = a.parent
    print("Href:", a.get("href"), "| Text:", a.get_text().strip(), "| Parent tag:", parent.name, "| Parent text:", parent.get_text(separator=' ').strip()[:100])
