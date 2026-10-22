"""Offline SEO regression checks (no credentials or network)."""
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
class ShortstaySEOTests(unittest.TestCase):
    def test_indexable(self):
        html=(ROOT/'templates/pages/shortstay.html').read_text('utf-8')
        self.assertNotIn('noindex',html)
        self.assertIn('name="robots" content="index,follow"',html)
        self.assertIn('ss_initial["items"]',html)
        self.assertIn('item.original_url',html)
        self.assertIn('item.summary',html)
    def test_search_and_sharing_metadata(self):
        html=(ROOT/'templates/pages/shortstay.html').read_text('utf-8')
        self.assertIn('莱顿、海牙、阿姆斯特丹及周边',html)
        self.assertIn('name="description"',html)
        self.assertIn('property="og:title"',html)
        self.assertIn('property="og:description"',html)
        self.assertIn('property="og:url"',html)
        self.assertIn('name="twitter:card"',html)
        self.assertNotIn('name="keywords"',html)

    def test_sitemap(self):
        routes=(ROOT/'expatus/controllers/pages.py').read_text('utf-8')
        self.assertIn('("/shortstay", "daily", "0.8")',routes)
    def test_no_initial_client_refetch(self):
        js=(ROOT/'static/js/shortstay.js').read_text('utf-8')
        self.assertIn('let mode="30d"',js)
        self.assertNotIn('  load();\n})();',js)
    def test_catalog_does_not_scrape(self):
        controller=(ROOT/'expatus/controllers/shortstay.py').read_text('utf-8')
        self.assertIn('query_listings("leiden", "30d")',controller)
        self.assertNotIn('run_scanner',controller)

if __name__=="__main__":
    unittest.main()
