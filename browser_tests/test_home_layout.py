import os
import unittest

from playwright.sync_api import expect, sync_playwright


BASE = os.environ.get("AUCTION_BROWSER_URL", "http://127.0.0.1:8000").rstrip("/")


class AuctionHomeLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        playwright = sync_playwright().start()
        cls.addClassCleanup(playwright.stop)
        channel = os.environ.get("AUCTION_BROWSER_CHANNEL")
        cls.browser = playwright.chromium.launch(**({"channel": channel} if channel else {}))
        cls.addClassCleanup(cls.browser.close)

    def home(self, width, height):
        page = self.browser.new_page(viewport={"width": width, "height": height}, reduced_motion="reduce")
        self.addCleanup(page.close)
        page.goto(BASE + "/")
        return page

    def test_desktop_discovery_places_categories_next_to_photo_comparison(self):
        page = self.home(1440, 900)
        first_category = page.get_by_role("link", name="아파트 입찰 예정 4건", exact=True)
        comparison = page.get_by_role("heading", name="경매 VS", exact=True)
        category_box = first_category.bounding_box()
        comparison_box = comparison.bounding_box()
        self.assertLess(category_box["x"] + category_box["width"], comparison_box["x"])
        self.assertLess(abs(category_box["y"] - comparison_box["y"]), 30)
        self.assertLess(page.locator("#home-search").bounding_box()["height"], 110)
        expect(page.get_by_role("region", name="경매 VS", exact=True).locator("img").first).to_be_visible()
        self.assertEqual(page.locator('select[name="region"] option').all_text_contents(), [
            "전체 지역", "서울", "경기", "인천",
        ])

    def test_mobile_discovery_fits_five_categories_and_comparison_above_fold(self):
        page = self.home(390, 844)
        category_links = page.get_by_role("link").filter(has_text="입찰 예정 4건")
        self.assertLess(category_links.first.bounding_box()["y"], 240)
        categories = page.locator('.home-category-grid > a')
        expect(categories).to_have_count(5)
        tops = categories.evaluate_all("elements => elements.map(el => el.getBoundingClientRect().top)")
        self.assertLess(max(tops) - min(tops), 1)
        self.assertLess(page.get_by_role("heading", name="경매 VS", exact=True).bounding_box()["y"], 340)
        self.assertLess(page.get_by_role("link", name="대화 시작", exact=False).bounding_box()["y"], 680)
        self.assertEqual(page.evaluate("document.documentElement.scrollWidth"), 390)

    def test_desktop_upcoming_rail_advances_and_wraps_in_both_directions(self):
        page = self.home(1440, 900)
        rail = page.locator("#upcoming-rail")
        cards = rail.locator(".home-lot")
        hrefs = cards.evaluate_all("links => links.map(link => link.getAttribute('href'))")
        self.assertGreaterEqual(len(hrefs), 4)
        section = page.get_by_role("region", name="다가오는 입찰", exact=True)
        next_button = section.get_by_role("button", name="다음 매물")
        previous_button = section.get_by_role("button", name="이전 매물")

        def expect_leading(href):
            page.wait_for_function("""href => {
                const rail = document.getElementById('upcoming-rail');
                const left = rail.getBoundingClientRect().left;
                return Array.from(rail.querySelectorAll('.home-lot')).some(card =>
                    card.getAttribute('href') === href && Math.abs(card.getBoundingClientRect().left - left) < 2);
            }""", arg=href, timeout=1_500)

        expect_leading(hrefs[0])
        for href in hrefs[1:] + hrefs[:1]:
            next_button.click()
            expect_leading(href)
        previous_button.click()
        expect_leading(hrefs[-1])
        expect(cards).to_have_count(len(hrefs))
