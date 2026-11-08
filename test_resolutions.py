import sys, subprocess, tempfile
from pathlib import Path
import cv2,numpy as np
ROOT = Path(__file__).resolve().parent
from engine import ffmpeg,scan
scratch = tempfile.TemporaryDirectory()
root = Path(scratch.name)
t=cv2.imread(str(ROOT/'template.png'),0)
for w,h in [(854,480),(1280,720),(1920,1080),(2560,1440),(3840,2160),(2560,1080),(3440,1440),(5120,1440),(1280,1024),(1920,1200)]:
    base=np.full((1080,round(w/h*1080)),30,np.uint8); th,tw=t.shape
    x=base.shape[1]//2-tw//2; base[730:730+th,x:x+tw]=t
    frame=cv2.resize(base,(w,h),interpolation=cv2.INTER_AREA)
    png=root/f'{w}x{h}.png';cv2.imwrite(str(png),frame)
    mp4=png.with_suffix('.mp4')
    subprocess.run([ffmpeg(),'-v','error','-loop','1','-i',str(png),'-t','0.5','-r','10','-c:v','libx264','-preset','ultrafast','-crf','18','-pix_fmt','yuv420p','-y',str(mp4)],check=True)
    events,_,_=scan(mp4,str(ROOT/'template.png'))
    assert len(events) == 1, (w, h, events)
    print('PASS', w, h, flush=True)


scratch.cleanup()
