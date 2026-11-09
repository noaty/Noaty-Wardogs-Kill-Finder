"""Validated detection preferences; preserve other runtime settings."""
import json
import math

DEFAULTS = dict(method='Audio + visual check (recommended)', audio_threshold='12', track='Auto', threshold='0.78', scale='Auto')
METHODS = (DEFAULTS['method'], 'Kill sound (audio only)', 'Notification text (video only)')
SCALES = ('Auto','75%','85%','90%','100%','110%','125%','150%')

def validate(values):
 values = {k:str(values.get(k,v)) for k,v in DEFAULTS.items()}
 if values['method'] not in METHODS or values['scale'] not in SCALES:
  raise ValueError('Choose a listed detection method and HUD scale.')
 for key,lo,hi in [('audio_threshold',3,40),('threshold',.5,.99)]:
  try: number=float(values[key])
  except ValueError: raise ValueError('Enter numeric sensitivity and match threshold values.')
  if not math.isfinite(number) or not lo <= number <= hi:
   raise ValueError('Sound sensitivity must be 3-40 dB; match threshold must be 0.50-0.99.')
 track=values['track']
 if track not in ('Auto','All tracks') and (not track.isdigit() or int(track)<1):
  raise ValueError('Choose Auto, All tracks, or a positive audio track number.')
 return values

def load(path):
 try:
  data=json.loads(path.read_text(encoding='utf-8'))
  return validate(data.get('detection',{}))
 except (OSError,ValueError,TypeError,AttributeError):return DEFAULTS.copy()

def save(path, values):
 values=validate(values)
 try:
  data=json.loads(path.read_text(encoding='utf-8'))
  if not isinstance(data,dict):data={}
 except (OSError,ValueError):data={}
 data['detection']=values
 path.parent.mkdir(parents=True,exist_ok=True)
 temp=path.with_suffix('.tmp')
 temp.write_text(json.dumps(data,indent=2),encoding='utf-8')
 temp.replace(path)
 return values
