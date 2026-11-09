"""Animated, explicit ON/OFF export switches aligned to visible result rows."""
import tkinter as tk
import time

class RowSwitches:
 def __init__(self, tree, events, toggle):
  self.tree,self.events,self.toggle=tree,events,toggle
  self.widgets={}
  self.tick()
 def tick(self):
  if not self.tree.winfo_exists():return
  visible=set()
  for row in self.tree.get_children():
   box=self.tree.bbox(row,'keep')
   if not box:continue
   x,y,w,h=box
   if y<20 or y+h>self.tree.winfo_height():continue
   visible.add(row)
   if row not in self.widgets:
    c=tk.Canvas(self.tree,highlightthickness=0,bg='#111a22',cursor='hand2')
    c.bind('<Button-1>',lambda e,r=row:self.toggle(r))
    self.widgets[row]=[c,None,0.,0.,0.]
   state=self.widgets[row];c=state[0]
   on=self.events()[int(row)].get('included',True)
   now=time.monotonic()
   if state[1] is None:state[2]=float(on);state[3]=float(on)
   elif state[1]!=on:state[3]=state[2];state[4]=now
   state[1]=on
   progress=min(1,(now-state[4])/.16)
   state[2]=state[3]+(float(on)-state[3])*progress
   c.place(x=x,y=y,width=w,height=h)
   c.delete('all')
   color='#9fe76b' if on else '#53616c'
   cy=h/2
   c.create_line(14,cy,40,cy,width=20,fill=color,capstyle='round')
   knob=14+26*state[2]
   c.create_oval(knob-8,cy-8,knob+8,cy+8,fill='#ffffff',outline='')
   c.create_text(64,cy,text='ON' if on else 'OFF',fill='#c1f985' if on else '#ccd3d9',font=('Segoe UI',9,'bold'))
  for row in list(self.widgets):
   if row not in visible:self.widgets.pop(row)[0].destroy()
  self.tree.after(20,self.tick)
