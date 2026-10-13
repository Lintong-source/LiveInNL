"""Pricing and public image safety tests; no network, no Turso credentials."""
import importlib.util
import pathlib
import unittest
P=pathlib.Path(__file__).resolve().parents[1]/"expatus"/"repositories"/"shortstay.py"
spec=importlib.util.spec_from_file_location("shortstay_price_test",P)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ShortstayMediaPriceTests(unittest.TestCase):
    def test_structured_price_period(self):
        self.assertEqual(mod.public_price({"rent_eur":800,"rent_period":"month","title_cn":"room"}),(800.0,"month","structured"))
    def test_explicit_title_price(self):
        self.assertEqual(mod.public_price({"rent_eur":None,"title_cn":"短租 €750 Leiden"}),(750.0,"unknown","title"))
    def test_two_amounts_ambiguous(self):
        self.assertEqual(mod.public_price({"rent_eur":None,"title_cn":"€800 房租 €100 押金"})[0],None)
    def test_does_not_guess_unknown_price(self):
        self.assertIsNone(mod.public_price({"rent_eur":None,"title_cn":"短租 studio"})[0])
    def test_bad_scraped_price(self):
        self.assertIsNone(mod.public_price({"rent_eur":1.34})[0])
    def test_blob_only(self):
        self.assertEqual(mod.blob_image_url("https://abc.public.blob.vercel-storage.com/a.jpg"),"https://abc.public.blob.vercel-storage.com/a.jpg")
        self.assertIsNone(mod.blob_image_url("https://example.com/a.jpg"))
        self.assertIsNone(mod.blob_image_url("http://abc.public.blob.vercel-storage.com/a.jpg"))

if __name__=="__main__":unittest.main()
