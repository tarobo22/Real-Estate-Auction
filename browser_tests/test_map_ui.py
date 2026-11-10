import os
import unittest

from playwright.sync_api import expect, sync_playwright


BASE = os.environ.get("AUCTION_BROWSER_URL", "http://127.0.0.1:8000").rstrip("/")


class MapLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        playwright = sync_playwright().start()
        cls.addClassCleanup(playwright.stop)
        channel = os.environ.get("AUCTION_BROWSER_CHANNEL")
        cls.browser = playwright.chromium.launch(**({"channel": channel} if channel else {}))
        cls.addClassCleanup(cls.browser.close)

    def page(self, width, height, mobile=False):
        context = self.browser.new_context(
            viewport={"width": width, "height": height},
            is_mobile=mobile,
            has_touch=mobile,
        )
        self.addCleanup(context.close)
        page = context.new_page()
        page.goto(BASE + "/map/")
        return page

    def test_phone_shows_map_and_keeps_sheet_above_navigation(self):
        page = self.page(390, 844, mobile=True)
        sheet = page.locator("#map-list")
        summary = sheet.locator("summary")
        map_view = page.locator(".map-viewport")
        first_lot = sheet.locator(".map-lot-link").first
        expect(first_lot).not_to_be_visible()
        self.assertGreater(map_view.bounding_box()["height"], 360)
        collapsed = summary.bounding_box()
        self.assertGreater(collapsed["y"] + collapsed["height"], 755)
        self.assertLessEqual(collapsed["y"] + collapsed["height"], 805)

        summary.tap()
        expect(first_lot).to_be_visible()
        self.assertLess(summary.bounding_box()["y"], collapsed["y"])
        opener = first_lot
        opener.tap()
        expect(page.locator("#lot-dialog .lot-detail")).to_be_visible()
        page.get_by_role("button", name="상세 닫기").tap()
        expect(opener).to_be_focused()
        self.assertTrue(sheet.evaluate("(element) => element.open"))
        summary.tap()
        expect(first_lot).not_to_be_visible()

        summary.tap()
        sheet.locator("[data-map-locate]").first.tap()
        expect(first_lot).not_to_be_visible()
        expect(map_view).to_be_focused()
        expect(page.locator(".map-marker.is-located, .map-pin.is-located")).to_be_visible()

    def test_desktop_keeps_list_beside_map_without_a_collapsible_header(self):
        page = self.page(1440, 900)
        listing = page.locator("#map-list")
        map_view = page.locator(".map-viewport")
        expect(listing.locator(".map-lot-link").first).to_be_visible()
        expect(listing.locator("summary")).not_to_be_visible()
        left, right = listing.bounding_box(), map_view.bounding_box()
        self.assertLessEqual(left["x"] + left["width"], right["x"])
        self.assertGreater(right["height"], 475)
