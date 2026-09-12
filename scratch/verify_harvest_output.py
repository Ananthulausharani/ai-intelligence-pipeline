import json

with open("data/output/startups.json", encoding="utf-8") as f:
    startups = json.load(f)
with open("data/output/products.json", encoding="utf-8") as f:
    products = json.load(f)
with open("data/output/harvest_report.json", encoding="utf-8") as f:
    report = json.load(f)

print(f"Startups count: {len(startups)}")
print("Sample Startup 0:", json.dumps(startups[0], indent=2))
print("Sample Startup 500:", json.dumps(startups[500], indent=2))
print("---")
print(f"Products count: {len(products)}")
print("Sample Product 0:", json.dumps(products[0], indent=2))
print("Sample Product 500:", json.dumps(products[500], indent=2))
print("---")
print(f"Report status: {report['status']}")
print(f"Startup status: {report['startup_status']}")
print(f"Product status: {report['product_status']}")
