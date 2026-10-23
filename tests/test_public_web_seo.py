"""Regressions for ObraSignal's public search identity, without network access."""
import tempfile
import unittest
from pathlib import Path

from scripts.public_web_seo import (
    PUBLIC_TITLE, CANONICAL_URL, stamp_public_seo, write_public_discovery_files,
    validate_public_seo,
)


class PublicSearchIdentityTests(unittest.TestCase):
    def setUp(self):
        self.export = tempfile.TemporaryDirectory()
        self.addCleanup(self.export.cleanup)
        self.root = Path(self.export.name)

    def test_canonical_metadata_does_not_publish_build_id_as_title(self):
        example = (
            '<!doctype html><html><head><title>ObraSignal • a9fcd04</title>'
            '<meta name="obrasignal-build" content="a9fcd04">'
            '</head><body><div id="root"></div></body></html>'
        )
        stamped = stamp_public_seo(example)
        self.assertIn('<title>' + PUBLIC_TITLE + '</title>', stamped)
        self.assertNotIn('<title>ObraSignal • a9fcd04</title>', stamped)
        self.assertIn('<meta name="obrasignal-build" content="a9fcd04">', stamped)
        self.assertIn('<link rel="canonical" href="' + CANONICAL_URL + '">', stamped)
        self.assertIn('<meta name="description"', stamped)
        self.assertIn('<meta property="og:title"', stamped)
        self.assertIn('<meta name="twitter:card"', stamped)

    def test_idempotence_and_duplicate_titles_or_meta_removed(self):
        html = ('<html><head><title>Old title</title>'
                '<meta name="description" content="Old description">'
                '<link rel="canonical" href="https://example.invalid/">'
                '<meta property="og:title" content="Wrong brand"></head></html>')
        once = stamp_public_seo(html)
        twice = stamp_public_seo(once)
        self.assertEqual(once, twice)
        self.assertEqual(twice.count('<title>'), 1)
        self.assertEqual(twice.count('rel="canonical"'), 1)
        self.assertNotIn('example.invalid', twice)
        self.assertNotIn('Wrong brand', twice)

    def test_noindex_or_invalid_document_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "noindex"):
            stamp_public_seo('<head><meta name="robots" content="noindex,nofollow"></head>')
        with self.assertRaisesRegex(ValueError, "complete HTML head"):
            stamp_public_seo('<h1>ObraSignal</h1>')

    def test_public_search_files_include_only_official_root(self):
        (self.root / "index.html").write_text(stamp_public_seo('<head></head>'), encoding="utf-8")
        write_public_discovery_files(self.root)
        validate_public_seo(self.root)
        sitemap = (self.root / "sitemap.xml").read_text(encoding="utf-8")
        self.assertEqual(sitemap.count('<loc>'), 1)
        self.assertIn('<loc>https://obrasignal.com/</loc>', sitemap)
        self.assertNotIn('/login', sitemap)
        self.assertIn('Sitemap: https://obrasignal.com/sitemap.xml',
                      (self.root / "robots.txt").read_text(encoding="utf-8"))

    def test_release_validation_rejects_old_commit_title(self):
        (self.root / 'index.html').write_text(
            '<head><title>ObraSignal • a9fcd04</title></head>', encoding='utf-8'
        )
        write_public_discovery_files(self.root)
        with self.assertRaisesRegex(ValueError, "exactly stable|commit SHA"):
            validate_public_seo(self.root)

    def test_deployment_workflow_uses_static_public_seo_helper(self):
        workflow = (Path(__file__).resolve().parents[1]
                    / ".github/workflows/web-preview.yml").read_text(encoding="utf-8")
        self.assertIn("stamp_public_seo", workflow)
        self.assertIn("validate_public_seo", workflow)
        self.assertNotIn("f'<title>ObraSignal • {build}</title>'", workflow)


if __name__ == "__main__":
    unittest.main()
