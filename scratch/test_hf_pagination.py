import urllib.request
import json

headers = {"User-Agent": "Mozilla/5.0"}
url = "https://huggingface.co/api/models?limit=50&full=false"

req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req) as r:
    link_header = r.headers.get("Link")
    print("Link header:", link_header)
    data = json.loads(r.read())
    print("Fetched items:", len(data))
    if data:
        print("Sample 0:", data[0].get("id"), "Author:", data[0].get("author"), "Tags:", data[0].get("tags")[:5] if data[0].get("tags") else None)
        print("Sample -1:", data[-1].get("id"), "Author:", data[-1].get("author"))
