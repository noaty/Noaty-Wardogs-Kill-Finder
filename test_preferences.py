import json,tempfile,unittest
from pathlib import Path
import preferences
class PreferencesTests(unittest.TestCase):
 def test_roundtrip_preserves_runtime(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'settings.json';p.write_text(json.dumps({'ffmpeg':'example.exe'}))
   values=preferences.DEFAULTS | {'audio_threshold':'15','track':'All tracks'}
   preferences.save(p,values)
   self.assertEqual(preferences.load(p),values)
   self.assertEqual(json.loads(p.read_text())['ffmpeg'],'example.exe')
   preferences.save(p,preferences.DEFAULTS)
   self.assertEqual(preferences.load(p),preferences.DEFAULTS)
 def test_invalid_values_rejected(self):
  for key,value in [('threshold','nan'),('audio_threshold','41'),('track','0')]:
   with self.assertRaises(ValueError):preferences.validate(preferences.DEFAULTS|{key:value})
if __name__=='__main__':unittest.main()
