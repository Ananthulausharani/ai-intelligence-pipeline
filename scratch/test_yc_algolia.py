import urllib.request
import json

app_id = "45BWZJ1SGC"
api_key = "ODdhZGJhNGQxMjkzNTJjMzM4MTUzNjcxMTY1M2VjYWY4YTI4YTY0NmIwZGQzYzU5ZmU1MTE1NDRiYmE3Y2I0MWFuYWx5dGljc1RhZ3M9eWNkYyZyZXN0cmljdEluZGljZXM9WUNDb21wYW55X3Byb2R1Y3Rpb24lMkNZQ0NvbXBhbnlfQnlfTGF1bmNoX0RhdGVfcHJvZHVjdGlvbiZ0YWdGaWx0ZXJzPSU1QiUyMnljZGNfcHVibGljJTIyJTVE"
url = f"https://{app_id}-dsn.algolia.net/1/indexes/*/queries?x-algolia-application-id={app_id}&x-algolia-api-key={api_key}"

payload = {
    "requests": [
        {
            "indexName": "YCCompany_production",
            "params": "query=&hitsPerPage=10&page=0&facetFilters=%5B%22industry%3AHealthcare%22%5D"
        },
        {
            "indexName": "YCCompany_production",
            "params": "query=&hitsPerPage=10&page=0"
        }
    ]
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

try:
    with urllib.request.urlopen(req, timeout=10) as r:
        res = json.loads(r.read())
        hits = res["results"][1]["hits"]
        print("Total hits in YC:", res["results"][1].get("nbHits"))
        print(f"Retrieved {len(hits)} sample hits:")
        for h in hits[:3]:
            print("---")
            print("Name:", h.get("name"))
            print("Slug:", h.get("slug"))
            print("One-liner:", h.get("one_liner"))
            print("Website:", h.get("website"))
            print("Team size:", h.get("team_size"))
            print("Industries:", h.get("industries"))
            print("Subindustries:", h.get("subindustries"))
            print("Batch:", h.get("batch"))
            print("URL:", f"https://www.ycombinator.com/companies/{h.get('slug')}")
except Exception as e:
    print("Error:", e)
