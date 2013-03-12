#!/usr/bin/env python
import os
import sys
import itertools
from util import xmlfiletodict, get_pallet, get_articles, get_packlist_dict, dicttoxmlfile, dicttoxmlstring, xmlfiletodict
from arrange_spread import spread_articles
import cPickle
from binascii import b2a_base64
import ctypes
import fcntl
import random
import tempfile
import zlib

libpallet = ctypes.cdll.LoadLibrary('./libpallet.so.0.0.0')
libpallet.evaluate.restype = ctypes.c_double

def pretty(d, indent=0):
  for key, value in d.iteritems():
    print '\t' * indent + str(key)
    if isinstance(value, dict):
      pretty(value, indent+1)
    else:
      print '\t' * (indent+1) + str(value)

def humpSort(aList=None, verbose=False):
  if aList == None or len(aList) < 2:
    return aList
  else:
    aList = sorted(aList);
    return aList[len(aList)%2::2] + aList[::-2]

def roundeven(num):
  return int((num+1)/2*2)
  
def density(a):
  volume = a['Article']['Length']*a['Article']['Width']*a['Article']['Height']
  return 1000.0*a['Article']['Weight']/volume

# @param a List of articles to be sorted.
def sortLarge(articles):
  return sorted(articles, key=lambda a:(density(a), a['Article']['Height']), reverse=True)
  
def arrange_in_layer(abin, pwidth, pheight):
  # articles are longer than wider default rotation: 
  # width: x-direction, height:  y-direction
  layer = list()
  rest = list()
  root = {'x': 0, 'y': 0,
          'width': pwidth, 'height': pheight,
          'article': None,
          'down': None,
          'right': None}
  layer_max_height = 0

  # traverse the tree until a node is found that is big enough for article
  # with size width x height and return this node or None if not found
  def find_node(root, width, height):
    if root is None:
      return None
    elif root['article']:
      return (find_node(root['right'], width, height) or find_node(root['down'], width, height))
    elif width <= root['width'] and height <= root['height']:
      return root
    else:
      return None

  # after finding a node where an article fits, put article into the node and
  # create childnodes
  def split_node(node, width, height, article):
    node['article'] = article
    node['article']['PlacePosition']['X'] = node['x']+width/2
    node['article']['PlacePosition']['Y'] = node['y']+height/2
    if node['width'] > 0 and node['height']-height > 0:
      node['down'] = {
        'x': node['x'], 'y': node['y']+height,
        'width': node['width'],
        'height': node['height']-height,
        'article': None,
        'down': None,
        'right': None
      }
    else: node['down'] = None
    if node['width']-width > 0 and height > 0:
      node['right'] = {
        'x': node['x']+width, 'y': node['y'],
        'width': node['width']-width,
        'height': height,
        'article': None,
        'down': None,
        'right': None
      }
    else: node['right'] = None
    return node

  # for each article in abin, check and place article at a node. If it doesnt
  # fit, try to rotate. If it still doesnt fit, append to rest
  for article in abin:
    # output format only accepts integer positions, round article sizes up
    # to even numbers
    owidth, oheight = article['Article']['Length'], article['Article']['Width']
    article['Orientation'] = 1
    width, height = roundeven(owidth), roundeven(oheight)
    node = find_node(root, width, height)
    if (node):
      node = split_node(node, width, height, article)
    else:
      # rotate article
      # output format only accepts integer positions, round article sizes up
      # to even numbers
      article['Orientation'] = 2
      width, height = roundeven(oheight), roundeven(owidth)
      node = find_node(root, width, height)
      if (node):
        node = split_node(node, width, height, article)
      else:
        # rotate back
        article['Orientation'] = 1
        rest.append(article)

  # gather all articles that were
  def find_articles(node):
    if not node['article']:
      return
    layer.append(node['article'])
    if node['right']:
      find_articles(node['right'])
    if node['down']:
      find_articles(node['down'])

  find_articles(root)

  return root, layer, sortLarge(rest)
  
def rotate(node):
  if node is None:
    return

  if node['article']:
    # exchange x and y coordinate
    node['article']['PlacePosition']['X'], node['article']['PlacePosition']['Y'] = node['article']['PlacePosition']['Y'], node['article']['PlacePosition']['X']
    # rotate article
    node['article']['Orientation'] = node['article']['Orientation']%2+1

  rotate(node['right'])
  rotate(node['down'])

def get_layers(boxes, pallet):
  layers = []
  done = False
  plength, pwidth = (pallet['Dimensions']['Width'], pallet['Dimensions']['Length'])
  root, layer, rest = arrange_in_layer(boxes, pwidth, plength)
  root, layer, rest = arrange_in_layer(humpSort(layer)+rest, pwidth, plength)
  layers.append(layer)
  while not done:
    spread_articles(root)
    root, layer, rest = arrange_in_layer(rest, pwidth, plength)
    root, layer, rest = arrange_in_layer(humpSort(layer)+rest, pwidth, plength)
    layers.append(layer)
    if len(rest) < 1: done = True
  return layers

def get_max_height(layer):
  max_height = 0
  for l in layer:
    h = l['Article']['Height']
    if h > max_height:
      max_height = h
  return max_height

def pack_single_pallet(layers, pallet):
  pack_sequence = 1
  pack_height = 0

  articles_to_pack = list()

  for layer in layers:
    max_height = get_max_height(layer)
    pack_height += max_height
    for article in layer:
      article['PackSequence'] = pack_sequence
      height_diff = max_height - article['Article']['Height']
      article['PlacePosition']['Z'] = pack_height - height_diff
      articles_to_pack.append(article)
      pack_sequence += 1

  return get_packlist_dict(pallet, articles_to_pack)
  
def evaluate_single_pallet(packlist):
  tmp_fh, tmp = tempfile.mkstemp()
  dicttoxmlfile(packlist, tmp)
  result = libpallet.evaluate(sys.argv[1], tmp, sys.argv[3])
  os.close(tmp_fh)
  os.remove(tmp)
  return result

def evaluate_layers(layers, score_max, pallet, result_max): 
  # Center the higest layer
  topLayer = layers.pop()
  plength, pwidth = (pallet['Dimensions']['Length'], pallet['Dimensions']['Width'])
  com_x = 0
  com_y = 0
  leftmost = pallet['Dimensions']['Length']
  rightmost = 0
  bottommost = pallet['Dimensions']['Width']
  topmost = 0
  
  for article in topLayer:
    com_x += article['PlacePosition']['X']
    com_y += article['PlacePosition']['Y']
    if article['PlacePosition']['X']-article['Article']['Length']/2 < leftmost:
      leftmost = article['PlacePosition']['X']-article['Article']['Length']/2
    if article['PlacePosition']['X']+article['Article']['Length']/2 > rightmost:
      rightmost = article['PlacePosition']['X']+article['Article']['Length']/2
    if article['PlacePosition']['Y']-article['Article']['Width']/2 < bottommost:
      bottommost = article['PlacePosition']['Y']-article['Article']['Width']/2
    if article['PlacePosition']['Y']+article['Article']['Width']/2 > topmost:
      topmost = article['PlacePosition']['Y']+article['Article']['Width']/2
  com_x, com_y = com_x/len(topLayer), com_y/len(topLayer)

  llength = rightmost - leftmost
  lwidth = topmost - bottommost

  if com_x < llength-plength/2:
    com_x = llength-plength/2
  elif com_x > plength/2:
    com_x = plength/2
  if com_y < lwidth-pwidth/2:
    com_y = lwidth-pwidth/2
  elif com_y > pwidth/2:
    com_y = pwidth/2

  diff_x, diff_y = plength*0.5-com_x, pwidth*0.5-com_y

  for article in topLayer:
    article['PlacePosition']['X'] += diff_x
    article['PlacePosition']['Y'] += diff_y

  layers.append(topLayer) # Add modified layer back to layers
  
  max_count = 50
  cur_count = 0
  permutations = itertools.permutations(layers)
  for permut_layers in permutations:
    permut_layers = list(permut_layers)
    random.shuffle(permut_layers)
    packlist = pack_single_pallet(permut_layers, pallet)
    score = evaluate_single_pallet(packlist)
    if score >= score_max[0]:
      result_max[0] = dicttoxmlstring(packlist)
      score_max[0] = score
      print score
    cur_count += 1
    if max_count < 1 or cur_count > max_count: break

def main():
  # Usage
  if len(sys.argv) < 4:
    print "usage:", sys.argv[0], "order.xml packlist.xml scoring.xml"
    exit(1)

  # Create a new dictionary from the order
  orderline = xmlfiletodict(sys.argv[1])
  # Get pallet sub-dictionary from order dictionary
  pallet = get_pallet(orderline)
  # Get articles sub-dictionary from the order dictionary
  articles = get_articles(orderline)
  # Create a dictionary that separates each height into a separate bin
  aStack = sortLarge(articles)
  
  layers = get_layers(aStack, pallet)
  
  for layer in layers:
    print '\n'
    for article in layer:
      print '%.2f - %d - %dx%d'%(density(article), article['Article']['Height'], article['Article']['Length'], article['Article']['Width'])
      
  score_max = [0]
  result_max = [None]
  evaluate_layers(layers, score_max, pallet, result_max)

  print score_max[0]

  lock = open("score_max.lock", "w")
  fcntl.lockf(lock, fcntl.LOCK_EX)
  if os.path.isfile("score_max"):
    with open("score_max", "r") as f:
      score_max_f = float(f.read())
  else:
      score_max_f = 0.0
  if score_max[0] > score_max_f:
    with open(sys.argv[2], "w+") as f:
      f.write(result_max[0])
    with open("score_max", "w+") as f:
      f.write(str(score_max[0]))
  lock.close()
      
    
      
  # cd /home/ryan/sisyphus
  #$ ./ryan2_run.sh examples/icra2011/palDay2R2Order.xml packlist.xml examples/icra2011/scoreAsPlannedConfig1.xml 

if __name__ == "__main__":
  main()
