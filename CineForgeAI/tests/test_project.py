import tempfile, unittest
from pathlib import Path
from cineforge.project import new_project, save_project, load_project
class ProjectTests(unittest.TestCase):
 def test_round_trip(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"x.json"; x=new_project("Test","Premise");x["scenes"]=[{"number":1}];save_project(x,p)
   y=load_project(p);self.assertEqual(y["title"],"Test");self.assertEqual(len(y["scenes"]),1)
 def test_invalid_schema(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"x.json";p.write_text('{"schema_version":99,"scenes":[]}')
   with self.assertRaises(ValueError):load_project(p)
if __name__=="__main__":unittest.main()
