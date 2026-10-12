import tempfile, unittest
from pathlib import Path
from cineforge.video import assemble_mp4
class VideoTests(unittest.TestCase):
 def test_missing_clip(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(FileNotFoundError):assemble_mp4([str(Path(d)/"absent.mp4")],str(Path(d)/"out.mp4"))
if __name__=="__main__":unittest.main()
