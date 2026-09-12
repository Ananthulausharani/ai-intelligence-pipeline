import asyncio
from playwright.async_api import async_playwright

async def probe_yc_content():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating to YC companies...")
        await page.goto("https://www.ycombinator.com/companies", wait_until="networkidle")
        
        # Look for company card links
        cards = await page.eval_on_selector_all(
            'a[href*="/companies/"]',
            'elements => elements.map(e => ({href: e.href, text: e.innerText.trim()}))'
        )
        print(f"Rendered company links count: {len(cards)}")
        for c in cards[:10]:
            print("  ", c)
            
        # Check if there is a search or filter for AI
        await page.goto("https://www.ycombinator.com/companies?industry=Artificial%20Intelligence", wait_until="networkidle")
        ai_cards = await page.eval_on_selector_all(
            'a[href*="/companies/"]',
            'elements => elements.map(e => ({href: e.href, text: e.innerText.trim()}))'
        )
        print(f"Rendered AI company links count: {len(ai_cards)}")
        for c in ai_cards[:10]:
            print("  AI: ", c)
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(probe_yc_content())
