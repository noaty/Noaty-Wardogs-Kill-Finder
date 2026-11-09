import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace
from app import App, METHODS
from verification import included_events

class ReviewTests(unittest.TestCase):
 def setUp(self):
  self.app=App(); self.app.root.update()
  self.app.video=Path('example.mp4'); self.app.info={'duration':100}
  self.app.events=[{'seconds':10,'title':'Confirmed','included':True,'verified':True}, {'seconds':20,'title':'Check','included':False,'verified':False}]
  self.app.original=[e.copy() for e in self.app.events]
  self.app.fill(); self.app.set_busy(False)
 def tearDown(self):
  for job in self.app.root.tk.call('after','info'):
   self.app.root.tk.call('after','cancel',job)
  self.app.root.destroy()
 def test_default_and_toggle_restore(self):
  a=self.app
  self.assertEqual(a.method.get(),METHODS[0])
  self.assertEqual(len(included_events(a.events)),1)
  a.tree.selection_set('1'); a.toggle_candidate(SimpleNamespace(keysym='space'))
  self.assertEqual(len(included_events(a.events)),2)
  a.toggle_candidate(SimpleNamespace(keysym='space'))
  a.remove_flagged(); self.assertEqual(len(a.events),1)
  a.restore();self.assertEqual(len(a.events),2)
  self.assertFalse(a.events[1]['included'])
 def test_timestamp_export_filters(self):
  with patch('app.filedialog.askdirectory',return_value='.'),patch('app.marker_files',return_value=Path('a.json')) as save:
   self.app.save()
   self.assertEqual([x['seconds'] for x in save.call_args.args[1]],[10])
 def test_excluded_only_disables_exports(self):
  for e in self.app.events:e['included']=False
  self.app.set_busy(False)
  for button in (self.app.exportbtn,self.app.clipsbtn,self.app.savebtn):
   self.assertEqual(str(button['state']),'disabled')

if __name__=='__main__':unittest.main()

