import os
import re
import unittest
from urllib.parse import parse_qs, urlencode, urlsplit

from playwright.sync_api import expect, sync_playwright


BASE = os.environ.get("AUCTION_BROWSER_URL", "http://127.0.0.1:8000").rstrip("/")
INCHON_APARTMENT = {"region": "인천", "use": "아파트", "budget": "50000"}


class AuctionBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        channel = os.environ.get("AUCTION_BROWSER_CHANNEL")
        cls.browser = cls.playwright.chromium.launch(**({"channel": channel} if channel else {}))
        cls.addClassCleanup(cls.browser.close)

    def page(self, **options):
        context = self.browser.new_context(**options)
        self.addCleanup(context.close)
        page = context.new_page()
        page.set_default_timeout(8_000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(errors, []))
        return page

    def test_desktop_search_bounds_details_and_cart(self):
        page = self.page(viewport={"width": 1440, "height": 900})
        page.goto(BASE + "/")
        page.locator('select[name="region"]').select_option("인천")
        page.locator('select[name="use"]').select_option("아파트")
        page.locator('select[name="budget"]').select_option("50000")
        with page.expect_navigation():
            page.get_by_role("button", name="지도에서 보기").click()
        self.assertEqual(parse_qs(urlsplit(page.url).query), {key: [value] for key, value in INCHON_APARTMENT.items()})
        expect(page.locator("#map-provider")).to_have_text("행정구역 지도")
        expect(page.locator("#boundary-layer path").first).to_be_visible()
        expect(page.locator("#map-rows .map-row")).to_have_count(1)

        with page.expect_response(lambda response: "/api/map/lots/" in response.url) as pending:
            page.get_by_role("button", name="이 지도에서 찾기").click()
        self.assertEqual(pending.value.status, 200)
        self.assertEqual([row["id"] for row in pending.value.json()["lots"]], ["ri1"])
        expect(page.locator("#map-clear-range")).to_be_visible()

        opener = page.locator(".map-lot-link")
        opener.click()
        dialog = page.locator("#lot-dialog")
        expect(dialog.get_by_text("2024타경526336", exact=False)).to_be_visible()
        dialog.get_by_role("button", name="장바구니에 담기").click()
        expect(page.locator("[data-cart-count]")).to_have_text("1")
        page.keyboard.press("Escape")
        expect(dialog).not_to_be_visible()
        expect(opener).to_be_focused()

        with page.expect_navigation():
            page.get_by_role("link", name="지도 범위 해제").click()
        expect(page.locator("#map-clear-range")).not_to_be_visible()
        expect(page.locator("#map-rows .map-row")).to_have_count(1)
        page.locator("#cart-opener").click()
        expect(page.locator("#site-cart").get_by_role("link", name="쌍용아파트", exact=False)).to_be_visible()

    def test_mobile_map_range_opens_list_and_restores_focus(self):
        page = self.page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page.goto(BASE + "/map/?" + urlencode(INCHON_APARTMENT))
        listing = page.locator("#map-list")
        expect(page.locator(".map-lot-link")).not_to_be_visible()
        self.assertFalse(listing.evaluate("(element) => element.open"))
        page.get_by_role("button", name="이 지도에서 찾기").click()
        expect(page.locator(".map-lot-link")).to_be_visible()
        self.assertTrue(listing.evaluate("(element) => element.open"))
        opener = page.locator(".map-lot-link")
        opener.click()
        expect(page.locator("#lot-dialog .lot-detail")).to_be_visible()
        page.get_by_role("button", name="상세 닫기").click()
        expect(opener).to_be_focused()
        self.assertTrue(listing.evaluate("(element) => element.open"))

    def test_vs_recommendation_briefing_and_inquiry_copy(self):
        page = self.page(reduced_motion="reduce")
        page.add_init_script("""
            Object.defineProperty(navigator, "clipboard", { value: {
                writeText(text) {
                    if (window.testClipboardMode === "denied") return Promise.reject(new Error("denied"));
                    if (window.testClipboardMode === "pending") {
                        return new Promise((resolve) => { window.finishTestCopy = resolve; });
                    }
                    window.testClipboard = text;
                    return Promise.resolve();
                }
            }});
        """)
        page.goto(BASE + "/vs/")
        seen = set()
        for _ in range(5):
            choices = page.locator("[data-vs-slot]").all()
            choice = next(button for button in choices if button.get_attribute("value") not in seen)
            seen.add(choice.get_attribute("value"))
            with page.expect_navigation():
                choice.press("Enter")
        recommendation = page.locator("#recommendation")
        expect(recommendation).to_be_visible()
        recommendation.get_by_role("link", name="이긴 매물로 브리핑").click()
        question = page.get_by_role("textbox", name="질문")
        question.fill("인천 아파트 5억 이하")
        question.dispatch_event("keydown", {"key": "Enter", "isComposing": True})
        self.assertNotIn("thread=", page.url)
        with page.expect_navigation():
            question.press("Enter")
        expect(page.locator(".briefing-question")).to_have_text("인천 아파트 5억 이하")
        expect(page.locator(".briefing-turn a").first).to_be_visible()

        page.goto(BASE + "/vs/")
        opener = page.get_by_role("link", name="바로 문의하기")
        opener.click()
        dialog = page.locator("#auction-inquiry")
        message = dialog.get_by_role("textbox", name="문의 내용")
        status = dialog.get_by_role("status")
        copy = dialog.get_by_role("button", name="문의 내용 복사")
        expect(message).to_have_value(re.compile("타경"))
        message.fill(" ")
        copy.click()
        expect(message).to_be_focused()
        expect(status).to_have_text("복사할 문의 내용을 입력해 주세요.")
        message.fill("테스트 문의")
        copy.click()
        expect(status).to_have_text("문의 내용을 복사했습니다.")
        self.assertEqual(page.evaluate("window.testClipboard"), "테스트 문의")
        page.evaluate("window.testClipboardMode = 'denied'")
        copy.click()
        expect(status).to_contain_text("내용을 선택했습니다.")

        page.evaluate("window.testClipboardMode = 'pending'")
        copy.click()
        page.wait_for_function("typeof window.finishTestCopy === 'function'")
        page.keyboard.press("Escape")
        expect(opener).to_be_focused()
        opener.click()
        page.evaluate("window.finishTestCopy()")
        expect(status).to_have_text("")
