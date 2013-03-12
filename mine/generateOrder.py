#!/usr/bin/python2.7
from random import choice, randint
import sys
from util import dicttoxmlfile
from mathUtils import edgeDiff

# cd /home/ryan/pallet2
# ./palletandtruckviewer-3.0/palletViewer -o examples/icra2011/palDay1R1Order.xml -p pack.xml -s examples/icra2011/scoreAsPlannedConfig1.xml
# ./ryan2_run.sh examples/icra2011/palDay1R1Order.xml pack.xml examples/icra2011/scoreAsPlannedConfig1.xml

from math import floor, log10
import random

RANDOMIZE = True

descriptions = [ 'Cat Food', 'Cereal', 'Juice', 'Soup', 'Toothpaste', 'Water' ]

def pow10(n):
  if n <= 0: return n
  else: return pow(10, int(floor(log10(n))))
  
def edgeMargin(n, percent):
  return float(pow10(n)*percent)

def edgeWithMargin(n, percent):
  return n-edgeMargin(n, percent)

def getSubPackage(length, width, n):  
  return int(edgeWithMargin(length, 0.05)/n), int(edgeWithMargin(width, 0.05)/n)

def randomizeDimension(side):
  numerator = randint(10,50)
  percent = float(numerator / 100.0)
  return side-edgeMargin(side, percent)

def randomizeDimensions(length, width):
  return int(randomizeDimension(length)), int(randomizeDimension(width))
  
def homogeneousLayers(length, width, partitions):
  layers = list()
  for partition in partitions:
    articles = list()
    aLength, aWidth = getSubPackage(length, width, partition)    
    aHeight = int(((aLength+aWidth)/2))
    aWeight = randint(200,500)
    perLayer = partition * partition
    total = perLayer
    if RANDOMIZE:
      aLength, aWidth = randomizeDimensions(aLength, aWidth)
      total -= randint(0,int(total/2))
    dim = {'length':aLength, 'width':aWidth, 'height':aHeight, 'weight':aWeight}
    layers.append([total, dim])
  return layers

def generateBarcodes(start, count):
  barcodes = list()
  for n in range(0, count):
    barcode = start + n
    barcodes.append(barcode)
  return {'Barcode' : barcodes}

def generateOrderLines(layers):
  orderlines = list()
  orderLineNo = 1;
  for layer in layers:
    total, dim = layer
    barcodeBase = randint(1000,8000)
    orderlines.append({
      'OrderLineNo': orderLineNo,
      'Article' : {
        'ID' : 83774,
        'Description' : choice(descriptions),
        'Type' : 1,
        'Length' : dim['length'],
        'Width' : dim['width'],
        'Height' : dim['height'],
        'Weight' : dim['weight'],
        'Family' : 2
      },
      'Barcodes' : generateBarcodes(barcodeBase, total)
    })
    orderLineNo += 1
  return {'OrderLine':orderlines}
  
def generateOrder(filename, length, width, partitions):
  layers = homogeneousLayers(length, width, partitions)
  order = {
    'Message' : {
      'PalletInit' : { 
        'Pallets' : {
          'Pallet' : {
            'PalletNumber' : 1,
            'Description' : '%dx%d'%(length,width),
            'Dimensions' : {
              'Length' : length,
              'Width' : width,
              'MaxLoadHeight' : 9999,
              'MaxLoadWeight' : 99999,
            },
            'Overhang' : {
              'Length' : 0,
              'Width' : 0,
            },
            'SecurityMargins' : {
            'Length' : 0,
            'Width' : 0,
            },
          },
        },
      },
      'Order' : {
        'ID' : 1,
        'Description' : 'Homogeneous Layers',
        'Restrictions' : {
          'FamilyGrouping' : False,
          'Ranking' : False,
        },
        'OrderLines' : generateOrderLines(layers)
      }
    }
  }

  dicttoxmlfile(order, filename)

if __name__ == '__main__':
  # Usage
  if not len(sys.argv) == 2:
    print "usage:", sys.argv[0], 'filename'
    exit(1)
  path = str(sys.argv[1])
  filename = path+'order.xml'
  generateOrder(filename, 400, 300, list([5,6,4]))
  print 'File Saved:',filename
  

