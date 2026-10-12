import hashlib, unittest
from blygger.core.hashing import content_hash

class TestHashing(unittest.TestCase):
    def test_prefixed_sha256_of_utf8_markdown(self):
        md = "Markdown source of the *latest* version."
        expected = "sha256:" + hashlib.sha256(md.encode("utf-8")).hexdigest()
        self.assertEqual(content_hash(md), expected)

    def test_empty_string(self):
        self.assertEqual(
            content_hash(""),
            "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )

    def test_unicode_is_utf8_encoded(self):
        self.assertEqual(content_hash("café"),
                         "sha256:" + hashlib.sha256("café".encode("utf-8")).hexdigest())
