import os
import unittest

from playwright.sync_api import expect, sync_playwright


BASE = os.environ.get("AUCTION_BROWSER_URL", "http://127.0.0.1:8000").rstrip("/")


class ComparisonBriefingUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        playwright = sync_playwright().start()
        cls.addClassCleanup(playwright.stop)
        channel = os.environ.get("AUCTION_BROWSER_CHANNEL")
        cls.browser = playwright.chromium.launch(**({"channel": channel} if channel else {}))
        cls.addClassCleanup(cls.browser.close)

    def mobile_page(self):
        context = self.browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        self.addCleanup(context.close)
        page = context.new_page()
        page.set_default_timeout(5000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(errors, []))
        return page

    def test_photo_card_selects_and_detail_preserves_the_round(self):
        page = self.mobile_page()
        page.goto(BASE + "/")
        cards = page.locator(".vs-pair .vs-card")
        expect(cards.locator(".vs-visual img")).to_have_count(2, timeout=2500)
        expect(cards.locator(".vs-visual img").first).to_be_visible()
        choose = cards.first.locator("[data-vs-slot]")
        expect(choose).to_have_text("")
        detail = cards.first.get_by_role("link", name="상세 보기")
        token = cards.first.locator('input[name="token"]').input_value()
        detail.click()
        expect(page.locator("#vs-detail-dialog .lot-detail")).to_be_visible()
        page.keyboard.press("Escape")
        expect(detail).to_be_focused()
        self.assertEqual(cards.first.locator('input[name="token"]').input_value(), token)
        with page.expect_navigation():
            choose.press("Enter")
        expect(page.locator(".winner-card")).to_have_count(1)
        expect(cards.first.locator('input[name="token"]')).not_to_have_value(token)
        expect(choose).to_be_focused()

    def test_mobile_briefing_history_drawer_reopens_saved_thread(self):
        page = self.mobile_page()
        page.goto(BASE + "/briefing/")
        trigger = page.get_by_role("button", name="최근 대화")
        expect(trigger).to_be_visible(timeout=2500)
        history = page.get_by_role("dialog", name="최근 대화")
        trigger.click()
        expect(history.get_by_text("최근 대화가 없습니다.")).to_be_visible()
        page.keyboard.press("Escape")
        expect(trigger).to_be_focused()

        question = page.get_by_role("textbox", name="질문")
        question.fill("인천 아파트 5억 이하")
        with page.expect_navigation():
            question.press("Enter")
        saved_url = page.url
        expect(page.locator(".briefing-question")).to_have_text("인천 아파트 5억 이하")
        page.get_by_role("link", name="새 대화").click()
        trigger.click()
        history.get_by_role("link", name="인천 아파트 5억 이하").click()
        expect(page).to_have_url(saved_url)
        expect(page.locator(".briefing-question")).to_have_text("인천 아파트 5억 이하")
