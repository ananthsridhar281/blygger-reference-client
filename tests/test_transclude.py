# tests/test_transclude.py
import unittest
from blygger.core.transclude import bake
from blygger.core.errors import PublishError

FID = "7c9wk2mhq0v3xj8tn5rzfd41bg"

def resolver(id):
    if id == FID:
        return (3, "<p>quoted</p>")
    raise PublishError(f"unknown {id}")

class TestTransclude(unittest.TestCase):
    def test_directive_line_bakes_blockquote_and_provenance(self):
        html, trans = bake(f"Intro.\n\n![[{FID}]]\n\nOutro.", resolver)
        self.assertIn('<blockquote class="blyg-transclusion" '
                      f'data-blyg-id="{FID}" data-blyg-version="3"><p>quoted</p></blockquote>', html)
        self.assertIn("<p>Intro.</p>", html)
        self.assertIn("<p>Outro.</p>", html)
        self.assertEqual([(t.id, t.version) for t in trans], [(FID, 3)])

    def test_inline_directive_is_inert(self):
        html, trans = bake(f"see ![[{FID}]] here", resolver)
        self.assertEqual(trans, [])
        self.assertNotIn("blyg-transclusion", html)

    def test_reserved_version_form_rejected(self):
        with self.assertRaises(PublishError):
            bake(f"![[{FID}@v2]]", resolver)

    def test_unknown_target_is_publish_error(self):
        with self.assertRaises(PublishError):
            bake("![[" + "0" * 26 + "]]", resolver)

    def test_order_preserved(self):
        second = "1vgtgz0gq5b2c9k7d3m8r4n6xy"
        def r2(id):
            return {FID: (3, "<p>a</p>"), second: (1, "<p>b</p>")}[id]
        _, trans = bake(f"![[{FID}]]\n\n![[{second}]]", r2)
        self.assertEqual([t.id for t in trans], [FID, second])
