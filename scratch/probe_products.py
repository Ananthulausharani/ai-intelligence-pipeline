import urllib.request
import json
from bs4 import BeautifulSoup

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

def probe(url):
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read()
            print(f"[SUCCESS] {url} -> Status: {r.status}, Length: {len(body)}")
            return body
    except Exception as e:
        print(f"[FAILED] {url} -> {e}")
        return None

# Test candidate AI product directories
probe("https://www.futuretools.io/")
probe("https://futurepedia.io/")
probe("https://theresanaiforthat.com/")
probe("https://huggingface.co/api/spaces?limit=10&full=false")
probe("https://huggingface.co/api/models?limit=10&full=false")
