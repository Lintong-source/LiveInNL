"""Ensure Dutch place names stay in the public listing titles."""
import importlib.util
import json
import pathlib
import unittest

path=pathlib.Path(__file__).resolve().parents[1]/"expatus"/"repositories"/"shortstay.py"
spec=importlib.util.spec_from_file_location("shortstay_titles",path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class TitleTests(unittest.TestCase):
    def test_source_title_preserves_street_city(self):
        raw=json.dumps({"detail":{"raw_title":"Room for rent €1200 euro Vriendenlaan, Rotterdam | Kamernet"}})
        title=module.display_title({"title_cn":"鹿特丹的房间"},raw,"kamernet")
        self.assertIn("Vriendenlaan, Rotterdam",title)
        self.assertNotIn("鹿特丹",title)
        self.assertTrue(title.startswith("出租房间"))
    def test_missing_original_uses_existing(self):
        self.assertEqual(module.display_title({"title_cn":"原有标题"},"{}","kamernet"),"原有标题")
    def test_bad_json_safe(self):
        self.assertEqual(module.display_title({"title_cn":"原有标题"},"{bad","kamernet"),"原有标题")

if __name__=="__main__":
    unittest.main()
