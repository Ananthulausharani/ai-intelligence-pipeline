import urllib.request
import json

app_id = "45BWZJ1SGC"
api_key = "ODdhZGJhNGQxMjkzNTJjMzM4MTUzNjcxMTY1M2VjYWY4YTI4YTY0NmIwZGQzYzU5ZmU1MTE1NDRiYmE3Y2I0MWFuYWx5dGljc1RhZ3M9eWNkYyZyZXN0cmljdEluZGljZXM9WUNDb21wYW55X3Byb2R1Y3Rpb24lMkNZQ0NvbXBhbnlfQnlfTGF1bmNoX0RhdGVfcHJvZHVjdGlvbiZ0YWdGaWx0ZXJzPSU1QiUyMnljZGNfcHVibGljJTIyJTVE"
url = f"https://{app_id}-dsn.algolia.net/1/indexes/*/queries?x-algolia-application-id={app_id}&x-algolia-api-key={api_key}"

for q in ["AI", "machine learning", "artificial intelligence", "robotics", "computer vision"]:
    payload = {
        "requests": [
            {
                "indexName": "YCCompany_production",
                "params": f"query={q}&hitsPerPage=10&page=0",
            }
        ]
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        res = json.loads(r.read())
        nb = res["results"][0].get("nbHits")
        print(f"Query: {q} -> nbHits: {nb}")
