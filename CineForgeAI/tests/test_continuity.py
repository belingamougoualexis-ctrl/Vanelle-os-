import unittest
from cineforge.continuity import validate_story

class ContinuityTests(unittest.TestCase):
    def test_flags_unknown_character_and_bad_duration(self):
        story={"characters":[{"name":"Awa"}],"synopsis":"Un synopsis","scenes":[{"number":1,"action":"Elle part","duration_seconds":0,"characters":["Inconnu"]}]}
        warnings=validate_story(story)
        self.assertTrue(any("durée non positive" in w for w in warnings))
        self.assertTrue(any("absent de la bible" in w for w in warnings))
    def test_flags_missing_story(self):
        warnings=validate_story({"characters":[],"scenes":[]})
        self.assertTrue(any("aucune scène" in w for w in warnings))
if __name__=="__main__": unittest.main()
