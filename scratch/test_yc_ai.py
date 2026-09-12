import urllib.request
import json

app_id = "45BWZJ1SGC"
api_key = "ODdhZGJhNGQxMjkzNTJjMzM4MTUzNjcxMTY1M2VjYWY4YTI4YTY0NmIwZGQzYzU5ZmU1MTE1NDRiYmE3Y2I0MWFuYWx5dGljc1RhZ3M9eWNkYyZyZXN0cmljdEluZGljZXM9WUNDb21wYW55X3Byb2R1Y3Rpb24lMkNZQ0NvbXBhbnlfQnlfTGF1bmNoX0RhdGVfcHJvZHVjdGlvbiZ0YWdGaWx0ZXJzPSU1QiUyMnljZGNfcHVibGljJTIyJTVE"
url = f"https://{app_id}-dsn.algolia.net/1/indexes/*/queries?x-algolia-application-id={app_id}&x-algolia-api-key={api_key}"

payload = {
    "requests": [
        {
            "indexName": "YCCompany_production",
            "params": "query=AI&hitsPerPage=100&page=0"
        }
    ]
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

try:
    with urllib.request.urlopen(req, timeout=10) as r:
        res = json.loads(r.read())
        nbHits = res["results"][0].get("nbHits")
        print("Total AI-related hits in YC:", nbHits)
        hits = res["results"][0]["hits"]
        print(f"Sample hits (first 5 of {len(hits)}):")
        for h in hits[:5]:
            print(f"  {h.get('name')} | Team: {h.get('team_size')} | {h.get('one_liner')} | https://www.ycombinator.com/companies/{h.get('slug')}")
except Exception as e:
    print("Error:", e)
