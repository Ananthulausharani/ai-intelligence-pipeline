import asyncio
from playwright.async_api import async_playwright

async def probe_yc_responses():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        async def handle_response(response):
            url = response.url
            if any(k in url.lower() for k in ["company", "companies", "algolia", "query", "search", "rails"]):
                print("Response URL:", url, "Status:", response.status)
                try:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct:
                        data = await response.json()
                        print("  JSON response keys:", list(data.keys()) if isinstance(data, dict) else f"list of {len(data)}")
                except Exception as e:
                    pass
                    
        page.on("response", handle_response)
        await page.goto("https://www.ycombinator.com/companies", wait_until="networkidle")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(probe_yc_responses())
