#!/usr/bin/python2.6
#
# Parameter Name Generator
# Copyright (C) Ed Kent 2010
#
# This script is free software.  You can redistribute it and/or
# modify it under the terms of the Artistic License 2.0.
#
# This program is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.

##########
# Notes
##########
#Usage ./nameGenerator.py filename [CopasiSE path]
#Where:
#filename is the the Copasi file to generate parameter names from
#CopasiSE path is the path to the Copasi SE binary if not in the default location
#The lxml package must be installed and in the python path
#
##########
#Default path to CopasiSE binaries. Can be overwritten by including the path to the CopasiSE binary as the second argument
copasiPath = '/usr/share/copasi/CopasiSE.LINUX.X86_64'
##########

from lxml import etree
import subprocess
import copasiFile
import os
import sys

#Check arguments:
#[1] = filename
#[2] = [CopasiSE path]

try:
    assert sys.argv[1] != None
    fileName = sys.argv[1]
    assert os.path.isfile(fileName)
except:
    print 'Error reading filename'
    raise
try:
    if sys.argv[2] != None:
        copasiSE = sys.argv[2]
        assert os.path.isfile(copasiSE)
except:
    print 'Error finding CopasiSE binary'
    raise
    
xmlns = '{http://www.copasi.org/static/schema}'
pid = os.getpid()

names = copasiFile.getParameterNames(fileName, xmlns, copasiSE, pid)

for name in names:
    print name
