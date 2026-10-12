# tests/test_markdown.py
import unittest
from blygger.core.markdown import render

class TestMarkdown(unittest.TestCase):
    def test_paragraph_and_emphasis(self):
        self.assertEqual(render("Markdown source of the *latest* version."),
                         "<p>Markdown source of the <em>latest</em> version.</p>")

    def test_underscore_emphasis(self):
        self.assertEqual(render("a _b_ c"), "<p>a <em>b</em> c</p>")

    def test_inline_code_is_escaped(self):
        self.assertEqual(render("use `a<b>`"), "<p>use <code>a&lt;b&gt;</code></p>")

    def test_link_and_image(self):
        self.assertEqual(render("[t](https://x)"), '<p><a href="https://x">t</a></p>')
        self.assertEqual(render("![alt](https://x/i.png)"),
                         '<p><img src="https://x/i.png" alt="alt"></p>')

    def test_blockquote(self):
        self.assertEqual(render("> quoted"), "<blockquote><p>quoted</p></blockquote>")

    def test_fenced_code_block_escapes(self):
        self.assertEqual(render("```\na < b\n```"), "<pre><code>a &lt; b\n</code></pre>")

    def test_two_paragraphs(self):
        self.assertEqual(render("one\n\ntwo"), "<p>one</p>\n<p>two</p>")

    def test_html_special_chars_escaped_in_text(self):
        self.assertEqual(render("a & b < c"), "<p>a &amp; b &lt; c</p>")
