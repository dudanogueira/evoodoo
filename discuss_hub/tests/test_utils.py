from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..models.utils import add_strikethrough_to_paragraphs, html_to_whatsapp


@tagged("discuss_hub", "utils")
class TestStrikethroughFunction(TransactionCase):
    def test_basic_paragraph(self):
        html = "<p>Hello</p>"
        expected = "<p><s>Hello</s></p>"
        result = add_strikethrough_to_paragraphs(html)
        self.assertEqual(str(result), expected)

    def test_multiple_paragraphs(self):
        html = "<p>One</p><p>Two</p>"
        expected = "<p><s>One</s></p><p><s>Two</s></p>"
        result = add_strikethrough_to_paragraphs(html)
        self.assertEqual(str(result), expected)

    def test_paragraph_with_attributes(self):
        html = '<p class="foo">Text</p>'
        expected = '<p class="foo"><s>Text</s></p>'
        result = add_strikethrough_to_paragraphs(html)
        self.assertEqual(str(result), expected)

    def test_empty_paragraph(self):
        html = "<p></p>"
        expected = "<p><s></s></p>"
        result = add_strikethrough_to_paragraphs(html)
        self.assertEqual(str(result), expected)

    def test_nested_tags_inside_p(self):
        html = "<p>Hello <strong>World</strong></p>"
        expected = "<p><s>Hello <strong>World</strong></s></p>"
        result = add_strikethrough_to_paragraphs(html)
        self.assertEqual(str(result), expected)


@tagged("discuss_hub", "utils")
class TestHtmlToWhatsapp(TransactionCase):
    def test_bold_and_italic(self):
        html = "<b>Bold</b> and <i>Italic</i>"
        expected = "*Bold* and _Italic_"
        self.assertEqual(html_to_whatsapp(html), expected)

    def test_paragraphs_and_linebreaks(self):
        html = "<p>First paragraph</p><p>Second</p><br>Line"
        expected = "First paragraph\n\nSecond\nLine"
        self.assertEqual(html_to_whatsapp(html), expected)

    def test_strike_and_underline(self):
        html = "<p>First paragraph</p><p>Second</p><br>Line"
        expected = "First paragraph\n\nSecond\nLine"
        self.assertEqual(html_to_whatsapp(html), expected)

    def test_nested_tags(self):
        html = "<b><i>Bold Italic</i></b>"
        expected = "*_Bold Italic_*"
        self.assertEqual(html_to_whatsapp(html), expected)

    def test_html_entities(self):
        html = "Tom &amp; Jerry"
        expected = "Tom & Jerry"
        self.assertEqual(html_to_whatsapp(html), expected)

    def test_empty_and_plain_text(self):
        self.assertEqual(html_to_whatsapp(""), "")
        self.assertEqual(html_to_whatsapp("Just text"), "Just text")
