import json

with open("data/output/startups.json", encoding="utf-8") as f:
    startups = json.load(f)
with open("data/output/products.json", encoding="utf-8") as f:
    products = json.load(f)

# Startup Audit
s_total = len(startups)
s_names = [s["content"]["entityName"] for s in startups]
s_unique = len(set(s_names))
s_with_src = sum(1 for s in startups if s.get("source", {}).get("url"))
s_with_perm = sum(1 for s in startups if s.get("content", {}).get("data", {}).get("company_url"))
s_null_emp = sum(1 for s in startups if s.get("content", {}).get("data", {}).get("employeeCount") is None)
s_suspicious = sum(1 for s in startups if not s.get("content", {}).get("entityName") or "test" in s["content"]["entityName"].lower())

# Product Audit
p_total = len(products)
p_keys = [(p["content"]["productName"], p["content"]["startupName"]) for p in products]
p_unique = len(set(p_keys))
p_with_src = sum(1 for p in products if p.get("source", {}).get("url"))
p_with_perm = sum(1 for p in products if p.get("content", {}).get("product_url"))
p_null_pricing = sum(1 for p in products if p.get("content", {}).get("pricingModel") is None)
p_unresolved_startup = sum(1 for p in products if not p.get("content", {}).get("startupName"))
p_suspicious = sum(1 for p in products if not p.get("content", {}).get("productName"))

print("=== DATA QUALITY AUDIT ===")
print("STARTUPS:")
print(f"  Total:                 {s_total}")
print(f"  Unique:                {s_unique}")
print(f"  Source URL coverage:   {(s_with_src / s_total) * 100:.1f}%")
print(f"  Company permalink cov: {(s_with_perm / s_total) * 100:.1f}%")
print(f"  Null employee count:   {s_null_emp} ({(s_null_emp / s_total) * 100:.1f}%)")
print(f"  Suspicious records:    {s_suspicious}")

print("\nPRODUCTS:")
print(f"  Total:                 {p_total}")
print(f"  Unique:                {p_unique}")
print(f"  Source URL coverage:   {(p_with_src / p_total) * 100:.1f}%")
print(f"  Product permalink cov: {(p_with_perm / p_total) * 100:.1f}%")
print(f"  Null pricing model:    {p_null_pricing} ({(p_null_pricing / p_total) * 100:.1f}%)")
print(f"  Unresolved startup:    {p_unresolved_startup} ({(p_unresolved_startup / p_total) * 100:.1f}%)")
print(f"  Suspicious records:    {p_suspicious}")
