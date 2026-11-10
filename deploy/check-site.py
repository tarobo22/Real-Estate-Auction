import os

from playwright.sync_api import expect, sync_playwright


def check_site(base_url):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        with browser.new_context() as context:
            page = context.new_page()
            homepage = page.goto(f"{base_url}/")
            if homepage is None or homepage.status != 200:
                raise RuntimeError("The homepage did not return HTTP 200.")
            expect(page).to_have_title("경매 홈 · 입찰랩")

            page.goto(f"{base_url}/lots/ri1/")
            count = page.locator("[data-cart-count]")
            expect(count).to_have_text("0")
            page.get_by_role("button", name="장바구니에 담기", exact=True).click()
            expect(count).to_have_text("1")
            page.reload()
            expect(count).to_have_text("1")
            page.get_by_role("button", name="장바구니에서 빼기", exact=True).click()
            expect(count).to_have_text("0")
            page.reload()
            expect(count).to_have_text("0")

    print("Homepage and cart add/remove passed.")


if __name__ == "__main__":
    check_site(os.environ["AUCTION_BROWSER_URL"].rstrip("/"))
