#!/usr/bin/python2.6
#
# Sensitivity Optimizer Script
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
#CopasiSE must already be in the path
#Source Copasi file must already be set up for optimization of sensitivities, 
#The lxml package must be installed and in the python path
#
#A list of parameter names (which can be generated using nameGenerator.py) can now be passed as sdin
##########
#Default path to directory containing CopasiSE binaries. Can be overwritten by command-line flag '-p'
copasiPath = '/usr/share/copasi'
##########

from lxml import etree
from string import Template
import sys
import exceptions
from os import popen2
import subprocess
import time
import datetime
import os
from optparse import OptionParser
import traceback
import shutil
import copasiFile

def createObjectiveFunction(a,b,flux,mca): # a,b = integer indices, flux = bool, mca=bool
    
    if mca:
        if flux:
            s = Template('<CN=Root,Vector=TaskList[Metabolic Control Analysis],Method=MCA Method (Reder),Array=Scaled flux control coefficients[$i][$j]>')
        else:
            s = Template('<CN=Root,Vector=TaskList[Metabolic Control Analysis],Method=MCA Method (Reder),Array=Scaled concentration control coefficients[$i][$j]>')
    else: #Sensitivities
        if not flux:
            s = Template('<CN=Root,Vector=TaskList[Sensitivities],Problem=Sensitivities,Array=Scaled sensitivities array[$i][$j]>')
        else:
            raise Exception('Error: must set flux manually using Copasi GUI when using Sensitivities task')
    return s.substitute(i=a,j=b)

#Get process id
#This is included in temp file names to ensure that running the script concurrently in the
#same directory will not cause conflicts 
pid = os.getpid()
log = open(str(pid)+'.log', 'w',0)


#Parse the command line options
parser = OptionParser()
parser.add_option('-i', '--input', dest='inputfilename', help='Copasi file to import')
#parser.add_option('-o', '--output', dest='outputfilename', help='The filename to write the results to. Must not already exist')
parser.add_option('-f', '--flux', dest='flux', action='store_true', default=False, help='Calculate flux control coeficients. othewise concentration controls will be calculated')
#parser.add_option('-n', '--number', dest='paramRange', help='The zero-index ID of the final parameter to calculate sensitivies for. Specify this or -l', type='int', default=None)
#parser.add_option('-c', '--species', dest='speciesIndex', help='The zero-indexed ID of the species (or reaction) to calculate sensitivies against', type='int')
#parser.add_option('-d', '--display', dest='display', action='store_true', help='Display the results', default=False)
#parser.add_option('-w', '--update', dest='update', action='store_true', default=False, help='Update and save the temporary xml files after optimization. For debugging use')
#parser.add_option('-l', '--list', dest='paramList', help='List of zero-indexed parameter indexes to calculate sensitivies for. Specify this or -n', default=None)
parser.add_option('-p', '--path', dest='copasiPath', help='Path to directory containing CopasiSE binaries. Default = ' + copasiPath, default= copasiPath)

try:
    (opts, args) = parser.parse_args()
    inputfilename = opts.inputfilename
#    speciesIndex = (opts.speciesIndex) #Species index that we want to use for the sensitivity analysis
    flux = opts.flux
    copasiPath = opts.copasiPath
except:
    print >>log, 'Error parsing arguments. Run with the -h flag for help'
    raise
    
##Check either parameter range or parameter list has been set
#if opts.paramRange == None and opts.paramList == None:
#    raise Exception('Argument error. Either parameter number or list must be set!')
#if (opts.paramRange != None) and  (opts.paramList != None):
#    raise Exception('Argument error. Only one of parameter number or list can be set!')

#if opts.paramRange != None:
#    parameterRange = range(opts.paramRange + 1)
#else:
#    try:
#        parameterRange = map(int,opts.paramList.split(','))
#    except:
#        raise Exception('Error parsing parameter list')

#Note the start time of the script
start = time.time()

#Check that:
#    The input file exists
#    The output file doesn't exist
try:
    assert os.path.isfile(inputfilename)
except:
    print >>log, 'Error: the input file could not be found'
    raise Exception('No input file')



print >> log, 'Ed\'s sensitivity optimizer. Starting...'

#Load the copasi file
xmlns = '{http://www.copasi.org/static/schema}' ##NEW


#If present, read stdin as list of parameter names
if not sys.stdin.isatty():
    names = []
    try:
        for line in sys.stdin.readlines():
            names.append(line.strip('\n'))
    except:
        print 'Error reading list of parameter names from stdin'
        raise
#Else, assume that all parameters should be optimized
else:
    #Get names of paramters to optimize:
    names = copasiFile.getParameterNames(inputfilename, xmlns, os.path.join(copasiPath,'CopasiSE.LINUX.X86_64'), str(pid), strip=False)

#Parse the copasi XML
try:
    doc = etree.parse(inputfilename)
    
except:
    print >>log, 'Error loading copasi file'
    raise


#Open up the sensitivities task:
sensTask = copasiFile.getSensitivitiesTask(doc,xmlns)
#Open up the <problem>
problem = sensTask.find(xmlns + 'Problem')
#And open the listofvariables
#parameterGroups = problem.find(xmlns + 'ParameterGroup')

for pG in problem:
    if (pG.attrib['name'] == 'TargetFunctions'):
        targetFunctions = pG
    if (pG.attrib['name'] == 'ListOfVariables'):
        listOfVariables = pG
assert targetFunctions != None
assert listOfVariables != None

#Read the target functions:
try:
    for parameter in targetFunctions:
        if parameter.attrib['name'] == 'SingleObject':
            targetFunctionValue = parameter.attrib['value']
    assert targetFunctionValue != None
except:
    print 'Error reading sensitivities task target function. Ensure that a single object has been set'
    raise

#targetFunctionValue will be something similar to: "CN=Root,Model=MAPK cascade,Vector=Compartments[compartment],Vector=Metabolites[PP-MAPK],Reference=Concentration"
try:
    strings = targetFunctionValue.split(',')
    for s in strings:
        s = s.split('=')
        if s[0] == 'Model':
            modelName = s[1]
            break
    assert modelName != None
except:
    print 'Error processing sensitivities task target function. Ensure that a single object has been set'
    raise

#Reset the listOfVariables
listOfVariables.clear()
listOfVariables.set('name', 'ListOfVariables')

#Add a new child element: <ParameterGroup name='Variables'>
variables = etree.SubElement(listOfVariables, xmlns + 'ParameterGroup')
variables.set('name', 'Variables')

#Add two new children to variables:
#<Parameter name='SingleObject')
singleObject = etree.SubElement(variables, xmlns + 'Parameter')
singleObject.set('name', 'SingleObject')
singleObject.set('type', 'cn')
#<Parameter name='ObjectListType'>
objectListType = etree.SubElement(variables, xmlns + 'Parameter')
objectListType.set('name', 'ObjectListType')
objectListType.set('type', 'unsignedInteger')
objectListType.set('value', '1')



optTask = copasiFile.getOptimizationTask(doc,xmlns)

#Set the optimization task as scheduled to run, and if requested, to update the model
try:
    optTask.attrib['scheduled'] = 'true'
    optTask.attrib['updateModel'] = 'true' #New: always update the temp file
except:
    raise

#Find the objective function we wish to change
#First open the problem, then get the parameter with name ObjectiveFunction
#Then store the parameter for maximising
try:
    problemParameters = optTask.find(xmlns + 'Problem')
    for parameter in problemParameters:
        if (parameter.attrib['name'] == 'ObjectiveExpression'): ##NEW, was ObjectiveFunction
            objectiveFunction = parameter
            
        if (parameter.attrib['name'] == 'Maximize'):
            maximizeParameter = parameter
            
        if (parameter.attrib['name'] == 'Subtask'):
            subtask = parameter.attrib['value']
            if subtask == 'CN=Root,Vector=TaskList[Sensitivities]':
                mca = False
            elif subtask == 'CN=Root,Vector=TaskList[Metabolic Control Analysis]':
                mca = True
            else:
                print >>log, 'Invalid optimization subtask. Select either Sensitivities or MCA'
                raise
    assert objectiveFunction != None
    assert maximizeParameter != None
    assert subtask != ''
except:
    print >>log, 'Error finding the objective function or maximize parameter, or invalid subtask'
    raise

#Set the appropriate objective function for the optimization task:
if ((not mca) and (not flux)):
    objectiveFunction.text = '<CN=Root,Vector=TaskList[Sensitivities],Problem=Sensitivities,Array=Scaled sensitivities array[.]>'
else:
    print 'Error: MCA subtask and/or Flux Control Coefficients not currently supported'
    raise

#Create a new custom report

#Structure of new report is:
#1: #----
#2: 


try:
    report_key = 'auto_report_' + str(pid)
    copasiFile.createReport(doc,xmlns,report_key)
except Exception, e:
    print >>log, 'Error creating new report'
    raise
    
report = copasiFile.report(optTask,xmlns,report_key)

#Build a list of the strings to insert in the sensitivities task for each optimization run
#Read through the list of names in order:
optimizationStrings = []
for name in names:
    #First ascertain if the paramter is a global or local parameter
    #Global parameter will be of the form: Values[global_quantity_1].InitialValue
    if name[:5] == 'Values[':
        globalName = True
    #Else, assume the name is a local parameter of the form: (binding of MAPKKK activator).k1
    else:
        globalName = False
        
    #If the name is a global value, the optimization string should be of the form: CN=Root,Model=MAPK cascade,Vector=Values[global_quantity_1],Reference=InitialValue
    if globalName:
        nameVector = name.split('.')
        nameString = 'CN=Root,Model=' + modelName + ',Vector=' + nameVector[0] + ',Reference=' + nameVector[1]
    #Otherwise, assuming the name is a local value, the optimization string should be of the form: CN=Root,Model=MAPK cascade,Vector=Reactions[binding of MAPKKK activator],ParameterGroup=Parameters,Parameter=k1,Reference=Value
    else:
        nameVector = name.split('.')
        #Remove the brackets
        reactionName = nameVector[0].strip('(').rstrip(')')
        reactionParameter = nameVector[1]
        
        nameString = 'CN=Root,Model=' + modelName + ',Vector=Reactions[' + reactionName + '],ParameterGroup=Parameters,Parameter=' + reactionParameter + ',Reference=Value'
    
    assert nameString != None
    optimizationStrings.append(nameString)
    
    
#start building new xml file:
i = 0
try:
    for optString in optimizationStrings:
        maximizeParameter.attrib['value'] = '1'
        #objectiveFunction.text = createObjectiveFunction(speciesIndex,i,flux,mca)
        s = Template('${pid}_max_$index.txt')
        report.attrib['target'] = s.substitute(index=i, pid=pid)
        xml_output_string = Template('auto_copasi_xml_${pid}_max_$index.cps').substitute(index=i, pid=pid)
        
        #Update the sensitivities object
        singleObject.set('value',optString)
        doc.write(xml_output_string)
    
        maximizeParameter.attrib['value'] = '0'
        s = Template('${pid}_min_$index.txt')
        report.attrib['target'] = s.substitute(index=i, pid=pid)
        xml_output_string = Template('auto_copasi_xml_${pid}_min_$index.cps').substitute(index=i, pid=pid)
        doc.write(xml_output_string)
        i = i + 1
except:
    print >>log, "Error building xml file"
    raise
        

print >>log, 'Temporary XML files successfully created. Running CopasiSE to minimize and maximize each parameter...\n'

#Build condor job files

condor_processes = []

try:
    for i in range(len(names)):
        raw_condor_job_string = '''#Condor job
executable = ${copasiPath}/CopasiSE.$$$$(OpSys).$$$$(Arch)
universe       = vanilla 
arguments = --nologo --home . ${copasiFile} --save ${copasiFile}
transfer_input_files = ${copasiFile}
log =  ${copasiFile}.log  
error = ${copasiFile}.err
output = ${copasiFile}.out
Requirements = ( (OpSys == "WINNT51" && Arch == "INTEL" ) || (OpSys == "LINUX" && Arch == "X86_64" ) || (OpSys == "OSX" && Arch == "PPC" ) || (OpSys == "OSX" && Arch == "INTEL" ) || (OpSys == "LINUX" && Arch == "INTEL" ) ) && (Memory > 0 ) && (Machine != "turing.mib.man.ac.uk") && (Machine != "e-cskc38c04.eps.manchester.ac.uk")
#Requirements = (OpSys == "LINUX" && Arch == "X86_64" )
should_transfer_files = YES
when_to_transfer_output = ON_EXIT
queue\n'''
        #Max
        xml_output_string = Template('auto_copasi_xml_${pid}_max_$index.cps').substitute(index=i, pid=pid)
        condor_job_string = Template(raw_condor_job_string).substitute(copasiFile=xml_output_string, pid=pid, index=i, copasiPath=copasiPath)
        condor_job_filename = Template('auto_condor_${pid}_max_$index.job').substitute(index=i, pid=pid)
        
        condor_file = open(condor_job_filename, 'w')
        condor_file.write(condor_job_string)
        condor_file.close()

        p = subprocess.Popen('condor_submit ' + condor_job_filename,shell=True, stdout=subprocess.PIPE)
        process_output = p.communicate()[0]
        #Get condor_process number...
        condor_processes.append(int(process_output.splitlines()[2].split()[5].strip('.')))
        print >>log, 'Job submitted to condor, id = ' + process_output.splitlines()[2].split()[5].strip('.')
        #Sleep for 10s
        time.sleep(10)
            
        #Min
        xml_output_string = Template('auto_copasi_xml_${pid}_min_$index.cps').substitute(index=i, pid=pid)
        condor_job_string = Template(raw_condor_job_string).substitute(copasiFile=xml_output_string, pid=pid, index=i, copasiPath=copasiPath)
        condor_job_filename = Template('auto_condor_${pid}_min_$index.job').substitute(index=i, pid=pid)
        
        condor_file = open(condor_job_filename, 'w')
        condor_file.write(condor_job_string)
        condor_file.close()

        p = subprocess.Popen('condor_submit ' + condor_job_filename,shell=True, stdout=subprocess.PIPE)
        process_output = p.communicate()[0]
        #Get condor_process number...
        condor_processes.append(int(process_output.splitlines()[2].split()[5].strip('.')))
        print >>log, 'Job submitted to condor, id = ' + str(int(float(process_output.splitlines()[2].split()[5])))
        #Sleep for 10s
        time.sleep(10)
except:
    print >>log, 'Error running job'
    raise

#Wait for jobs to finish.

######################
#New method for checking if jobs have run, doesn't poll condor_q:
#Each job, when finished, should return a file called $pid_max/min_index.txt
#Go through each of these files and see if it exists using os.path.isfile()
finished = False

while not finished:
    finished = True
    for i in range(len(names)):
        minFile = Template('${pid}_min_$index.txt').substitute(pid=pid,index=i)
        maxFile = Template('${pid}_max_$index.txt').substitute(pid=pid,index=i)
        if not os.path.isfile(minFile):
            finished = False
            break
        if not os.path.isfile(maxFile):
            finished = False
            break

    time.sleep(10)



#########################
#Old method of checking if jobs are still running
#Polls condor_q - DO NOT USE ANY MORE!!
#########################
#still_running = True
#while still_running:
#    p = subprocess.Popen('condor_q', shell=True, stdout=subprocess.PIPE)
#    communicate = p.communicate()
#    process_output = communicate[0]
#    process_error = communicate[1]
#    split = process_output.splitlines()

#    #Format of condor_q output should be: for n jobs running...
#    #[0]Blank line
#    #[1]Blank line
#    #[2]Title line
#    #[3]Table heading line
#    #[3+n]Job lines
#    #[4+n]Blank line
#    #[5+n]Summary line
#    
#    #First, check we have a valid condor_q output, and not an error message. If it's an error message, sleep for 10s and try again
#    
#    try:
#    
#        #Check that the stdout (process_error) is blank
#        assert process_error == None
#    
#        #Check the final line is of the form 
#        assert split[-1].split(' ')[1] == 'jobs;'
#        #And that the third line is of the form -- Submitter: ...
#        split2 = split[2].split(' ')
#        assert split2[0] == '--'
#        assert split2[1] == 'Submitter:'
#        
#        
#        #Assume that no process are running
#        still_running = False
#        
#        for n in range(len(split)):
#            if not (n <= 3 or n >= len(split) - 2):
#                id = int(float(split[n].split()[0]))
#                if (id in condor_processes):
#                    still_running = True
#                    break
#        time.sleep(1)
#        
#    except:
#        #Something's gone wrong
#        print >>log, 'Error in condor_q output:'
#        print >>log, str(split)
#        print >>log, 'Stderr:'
#        print >>log, str(process_error)
#        print >>log, 'Time: ' + str(time.time())
#        print >>log, 'Error reading condor_q. Sleeping for 10 s'
#        still_running = True
#        time.sleep(10)
#


#Remove condor job file(s)
try:
    for i in range(len(names)):
        maxfile = Template('auto_condor_${pid}_max_$index.job').substitute(index=i, pid=pid)
        minfile = Template('auto_condor_${pid}_min_$index.job').substitute(index=i, pid=pid)
        os.remove(maxfile)
        os.remove(minfile)
except:
    print >>log, 'Error removing condor job files'
    raise
log.close()
print str(pid) + ';' + str(names) + ';' + inputfilename + ';' + os.path.join(copasiPath,'CopasiSE.LINUX.X86_64')
