#!/usr/bin/python2.6
#
# Sensitivity Optimizer output file statistics
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
# Usage: ./output_statistics.py PID parameterNameFile [fileName] [CopasiSE Path]
# where PID is the process ID prefixed to the files to be summarised
# numOfParameters is the number of parameters to summarise
# fileName [Optional]: file name of copasi file to retrieve parameter names from
# CopasiSE Path [Optional]: path to the CopasiSE binary

# Output:
# 1 line for each parameter, containing min/max sensitivity value, no. of evaluations and CPU time [s]



import sys
import exceptions

from lxml import etree
import os
import subprocess

import copasiFile

#Check stdin
if not sys.stdin.isatty():
    try:
        for line in sys.stdin.readlines():
            pass #Wait and read the final line
            
        stdin = line.split(';')
        pid=stdin[0]
        parameterNames = stdin[1].lstrip('[').rstrip(']').split(',')
        for i in range(len(parameterNames)):
            parameterNames[i] = parameterNames[i].strip().strip("'")
        fileName = stdin[2]
        copasiSE = stdin[3].rstrip('\n')
    except:
        print 'Output_statistics.py: Error parsing input'
        raise
else:
    #Check arguments:
    #[1] = pid
    #[2] = file containing parameter names
    #[3] = Name of original copasi file used to run optimization task
    #[4] = Path to CoapsiSE binary

    try:
        assert sys.argv[1] != None
        assert sys.argv[2] != None
        pid = int(sys.argv[1])
    except:
        print 'Error reading pid from command line. Check usage'
        raise
        
    try:
        assert os.path.isfile(sys.argv[2])
        f = open(sys.argv[2],'r')
        parameterNames = []
        for line in f.readlines():
            parameterNames.append(line.strip('\n'))
    except:
        print 'Error reading parameter names file. Check usage'
    try:
        fileName = sys.argv[3]
        assert os.path.isfile(fileName)
    except:
        print 'No file found with name ' + fileName
        raise
        
    try:
        copasiSE = sys.argv[4]
    except:
        print 'CopasiSE path must be specified'
        raise

    
xmlns = '{http://www.copasi.org/static/schema}'

#names = copasiFile.getParameterNames(fileName, xmlns, copasiSE, pid)
parameterRange=range(len(parameterNames))

copasiFile.generateCurrentSolutions(parameterRange,xmlns,pid,copasiSE)

[mins,maxs] = copasiFile.readOutputFiles(parameterRange,pid)

copasiFile.printOutput(parameterRange,parameterNames,mins,maxs)
