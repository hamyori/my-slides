import json
import tempfile
import unittest
from pathlib import Path

from indexer import build_index, parse_presentation


DECK_HTML = """<!doctype html>
<html><head>
  <title>Fallback document title</title>
  <meta name="date" content="">
  <meta name="course" content="Computer Science">
  <meta name="tags" content="git, systems">
  <meta name="description" content="A searchable deck.">
  <meta name="author" content="Study Group">
</head><body>
  <main class="deck-stage">
    <section class="slide"><h1>First topic</h1><p>Searchable body text.</p></section>
    <section class="slide"><h2>Second topic</h2><script>hidden script phrase</script></section>
  </main>
</body></html>"""


class IndexerTests(unittest.TestCase):
    def test_parses_metadata_text_and_folder_date_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            deck = root / "slides" / "2026-10-3-demo" / "index.html"
            deck.parent.mkdir(parents=True)
            deck.write_text(DECK_HTML, encoding="utf-8")

            presentation, errors = parse_presentation(deck, root)

            self.assertEqual(errors, [])
            self.assertIsNotNone(presentation)
            self.assertEqual(presentation["date"], "2026-10-03")
            self.assertEqual(presentation["title"], "Fallback document title")
            self.assertEqual(presentation["tags"], ["git", "systems"])
            self.assertEqual(presentation["slide_count"], 2)
            self.assertEqual(presentation["duration_minutes"], 3)
            self.assertTrue(presentation["duration_estimated"])
            self.assertEqual(presentation["slide_titles"], ["First topic", "Second topic"])
            self.assertIn("searchable body text", presentation["full_text"])
            self.assertNotIn("hidden script phrase", presentation["full_text"])

    def test_builds_relative_urls_and_valid_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            deck = root / "slides" / "2026-10-3-demo" / "index.html"
            deck.parent.mkdir(parents=True)
            deck.write_text(DECK_HTML, encoding="utf-8")
            output = root / "presentaciones.json"

            result = build_index(root / "slides", output, root)

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["url"], "slides/2026-10-3-demo/index.html")
            self.assertEqual(result[0]["preview"], "slides/2026-10-3-demo/catalog-preview.generated.svg")
            self.assertTrue((deck.parent / "catalog-preview.generated.svg").is_file())
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), result)

    def test_rejects_missing_description(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            deck = root / "slides" / "2026-10-03-demo" / "index.html"
            deck.parent.mkdir(parents=True)
            deck.write_text(DECK_HTML.replace('<meta name="description" content="A searchable deck.">', ""), encoding="utf-8")

            presentation, errors = parse_presentation(deck, root)

            self.assertIsNone(presentation)
            self.assertTrue(any("missing required metadata: description" in error for error in errors))

    def test_rejects_html_without_slide_sections(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            deck = root / "slides" / "2026-10-03-demo" / "index.html"
            deck.parent.mkdir(parents=True)
            html = DECK_HTML.replace('<section class="slide">', '<div class="slide">').replace("</section>", "</div>")
            deck.write_text(html, encoding="utf-8")

            presentation, errors = parse_presentation(deck, root)

            self.assertIsNone(presentation)
            self.assertTrue(any("no <section class=\"slide\"> sections found" in error for error in errors))

    def test_uses_author_duration_when_present(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            deck = root / "slides" / "2026-10-03-demo" / "index.html"
            deck.parent.mkdir(parents=True)
            html = DECK_HTML.replace("<meta name=\"author\" content=\"Study Group\">", '<meta name="author" content="Study Group"><meta name="duration-minutes" content="8">')
            deck.write_text(html, encoding="utf-8")

            presentation, errors = parse_presentation(deck, root)

            self.assertEqual(errors, [])
            self.assertEqual(presentation["duration_minutes"], 8)
            self.assertFalse(presentation["duration_estimated"])


if __name__ == "__main__":
    unittest.main()
