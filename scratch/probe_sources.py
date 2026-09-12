import urllib.request
import re
import json

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

# 1. Probe YC Companies HTML
try:
    req = urllib.request.Request("https://www.ycombinator.com/companies", headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read().decode("utf-8", errors="replace")
    
    urls = re.findall(r'https?://[^\s"\'<>]+', html)
    print("Found total URLs in YC page:", len(urls))
    for u in set(urls):
        if any(k in u.lower() for k in ["algolia", "api", "json", "company", "companies", "rails"]):
            print("  Candidate endpoint:", u)
            
    # Check for Algolia App ID or Api Key in page scripts
    algolia_app = re.findall(r'([A-Z0-9]{10})', html)
    algolia_keys = re.findall(r'([a-f0-9]{32})', html)
    print("Potential Algolia keys:", len(algolia_keys))
except Exception as e:
    print("YC Error:", e)

# 2. Check Hugging Face public models & orgs
try:
    req = urllib.request.Request("https://huggingface.co/api/models?limit=100&full=false", headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
        print("HF models (first 100): count =", len(data))
        authors = set(m.get("author") for m in data if m.get("author"))
        print("HF unique authors/startups in 100 models:", len(authors), list(authors)[:10])
except Exception as e:
    print("HF Models Error:", e)

# 3. Check Hugging Face Spaces API (AI applications & products)
try:
    req = urllib.request.Request("https://huggingface.co/api/spaces?limit=100&full=false", headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
        print("HF spaces (first 100): count =", len(data))
        if data:
            print("HF sample space:", data[0].get("id"), "author:", data[0].get("author"))
except Exception as e:
    print("HF Spaces Error:", e)
