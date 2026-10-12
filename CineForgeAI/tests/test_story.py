import json, unittest
from unittest.mock import patch
from cineforge.story import complete_story
class FakeResponse:
 def __enter__(self):return self
 def __exit__(self,*a):return False
 def read(self):return json.dumps({"message":{"content":json.dumps({"title":"Essai","scenes":[{"action":"Une porte s'ouvre"}]})}}).encode()
class StoryTests(unittest.TestCase):
 def test_empty_rejected(self):
  with self.assertRaises(ValueError):complete_story(" ")
 @patch("urllib.request.urlopen",return_value=FakeResponse())
 def test_json_parse(self,_):
  s=complete_story("Un début")
  self.assertEqual(s["title"],"Essai");self.assertEqual(s["scenes"][0]["duration_seconds"],5)
if __name__=="__main__":unittest.main()
