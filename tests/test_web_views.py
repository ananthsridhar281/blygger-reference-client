import unittest
from blygger.web import views


class TestViews(unittest.TestCase):
    def test_render_page_escapes_title_and_has_nav(self):
        html = views.render_page("A & B", "studio", "<p>x</p>")
        self.assertIn("A &amp; B", html)
        self.assertIn('href="/studio"', html)
        self.assertIn('href="/reader"', html)

    def test_studio_view_lists_item_and_forms(self):
        items = [{"id": "7" * 26, "authored_kind": "fragment", "version": 1,
                  "kind": "fragment", "note": None, "pinned_versions": [],
                  "withdrawn": False, "md_snippet": "hi there", "at": "t"}]
        body = views.studio_view(items, "https://x/blyg/", ["7" * 26], False)
        self.assertIn("7" * 26, body)
        self.assertIn('action="/studio/publish-fragment"', body)
        self.assertIn('action="/studio/publish-thread"', body)
        self.assertIn("hi there", body)

    def test_reader_view_none_shows_prompt(self):
        self.assertIn("Enter a blyg URL", views.reader_view("", None))

    def test_reader_item_rendered_in_sandboxed_iframe_escapes_scripts(self):
        result = {"origin": "https://x/blyg/", "title": "T", "site_mismatch": False,
                  "fetched": 1, "discrepancies": [],
                  "items": [{"id": "7" * 26, "withdrawn": False, "version": 1,
                             "kind": "fragment",
                             "content_html": "<p>hi <script>bad()</script></p>",
                             "author_name": None}]}
        body = views.reader_view("https://x/blyg/", result)
        self.assertIn('<iframe class="content" sandbox srcdoc=', body)
        self.assertNotIn("allow-scripts", body)          # scripts stay disabled
        self.assertNotIn("<script>bad()", body)          # not live in the parent doc
        self.assertIn("&lt;script&gt;bad()", body)       # escaped inside srcdoc

    def test_reader_withdrawn_is_tombstone(self):
        result = {"origin": "o", "title": "T", "site_mismatch": False, "fetched": 1,
                  "discrepancies": [],
                  "items": [{"id": "7" * 26, "withdrawn": True, "version": 2,
                             "kind": "withdrawn", "content_html": "", "author_name": None}]}
        self.assertIn("withdrawn by the author", views.reader_view("", result))

    def test_reader_discrepancy_banner(self):
        result = {"origin": "o", "title": "T", "site_mismatch": False, "fetched": 1,
                  "discrepancies": [("stealth_edit", "7" * 26, "hash changed")], "items": []}
        body = views.reader_view("", result)
        self.assertIn("stealth_edit", body)
        self.assertIn("hash changed", body)

    def test_site_mismatch_warning(self):
        result = {"origin": "https://real/blyg/", "title": "T", "site_mismatch": True,
                  "fetched": 0, "discrepancies": [], "items": []}
        self.assertIn("disagrees with the", views.reader_view("", result))
