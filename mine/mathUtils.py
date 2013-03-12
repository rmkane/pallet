#!/usr/bin/python

from math import floor, log10
import random

def pow10(n):
  if n <= 0: return n
  else: return pow(10, int(floor(log10(n))))
  
def edgeDiff(n):
  return float(pow10(n)/20) # 5 percent
