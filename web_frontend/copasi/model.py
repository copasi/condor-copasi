import subprocess, os, re
from web_frontend import settings
from lxml import etree
from string import Template
xmlns = '{http://www.copasi.org/static/schema}'
raw_condor_job_string = """#Condor job
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
queue\n"""


class CopasiModel:
    """Class representing a Copasi model"""
    def __init__(self, filename, binary=settings.COPASI_LOCAL_BINARY, binary_dir=settings.COPASI_BINARY_DIR):
        #Load the copasi binary
        self.model = etree.parse(filename)
        self.binary = binary
        self.binary_dir = binary_dir
        self.name = filename #TODO: change this to represent the actual model name, found in the xml
        (head, tail) = os.path.split(filename)
        self.path = head
    def __unicode__(self):
        return self.name
    def __string__(self):
        return self.name
        
    def is_valid(self, job_type):
        if job_type == 'SO':
            #Check that a single object has been set for the sensitivities task:
            if self.get_sensitivities_object() == '':
                return 'A single object has not been set for the sensitivities task'
            #And check that at least one parameter has been set
            if len(self.get_optimization_parameters()) == 0:
                return 'No parameters have been set for the optimization task'

            return True
            
        elif job_type == 'SS':
            if self.get_timecourse_method() == 'Deterministic (LSODA)':
                return 'Time course task must have a valid Stochastic or Hybrid algorithm set'
            try:
                timeTask = self.__getTask('timeCourse')
                timeReport = timeTask.find(xmlns + 'Report')
                assert timeReport.attrib['reference'] != ''
            except:
                return 'Time course task must have a valid report selected'
            return True
            
        else:
            return True
        
    def __copasiExecute(self, filename, tempdir):
        """Private function to run Copasi locally in a temporary folder."""
        p = subprocess.Popen([self.binary, '--nologo',  '--home', tempdir, filename], stdout=subprocess.PIPE, cwd=tempdir)
        p.communicate()
        
   
    def __getTask(self,task_type):
        """Get the XML tree representing a task with type: 'type'"""
        #Get the task list
        try:
            listOfTasks = self.model.find(xmlns + 'ListOfTasks')
            assert listOfTasks != None
        except:
            raise
        #Find the appropriate task
        try:
            for task in listOfTasks:
                if (task.attrib['type'] == task_type):
                    foundTask = task
                    break
            assert foundTask != None
        except:
            raise
        return foundTask

    def __clear_tasks(self):
        """Go through the task list, and set all tasks as not scheduled to run"""
        listOfTasks = self.model.find(xmlns + 'ListOfTasks') 
        assert listOfTasks != None
        
        for task in listOfTasks:
            task.attrib['scheduled'] = 'false'
    
    def get_name(self):
        """Returns the name of the model"""
        modelTree = self.model.find(xmlns + 'Model')
        return modelTree.attrib['name']

    def get_timecourse_method(self):
        """Returns the algorithm set for the time course task"""
        timeTask = self.__getTask('timeCourse')
        timeMethod = timeTask.find(xmlns + 'Method')
        return timeMethod.attrib['name']

    def get_optimization_method(self):
        """Returns the algorithm set for the optimization task"""
        optTask = self.__getTask('optimization')
        optMethod = optTask.find(xmlns + 'Method')
        return optMethod.attrib['name']

    def get_sensitivities_object(self, friendly=True):
        """Returns the single object set for the sensitvities task"""
        sensTask = self.__getTask('sensitivities')
        sensProblem = sensTask.find(xmlns + 'Problem')
        parameterGroup = sensProblem.find(xmlns + 'ParameterGroup')
        parameter = parameterGroup.find(xmlns + 'Parameter')
        value_string = parameter.attrib['value']
        
        if friendly:
            #Use a regex to extract the parameter name from string of the format:
            #Vector=Metabolites[E1]
            string = r'Vector=(?P<name>(Reactions|Metabolites|Values)\[.+\])'
            r = re.compile(string)
            search = r.search(value_string)
            if search:
                value_string = search.group('name')
        return value_string
            
    def get_optimization_parameters(self, friendly=True):
        """Returns a list of the parameter names to be included in the sensitvitiy optimization task. Will optionally process names to make them more user friendly"""
        #Get the sensitivities task:
        sensTask=self.__getTask('optimization')
        sensProblem = sensTask.find(xmlns + 'Problem')
        optimizationItems = sensProblem.find(xmlns + 'ParameterGroup')
        parameters = []
        for subGroup in optimizationItems:
            name = None
            lowerBound = None
            upperBound = None
            startValue = None
            
            for item in subGroup:
                if item.attrib['name'] == 'ObjectCN':
                    name = item.attrib['value']
                elif item.attrib['name'] == 'UpperBound':
                    upperBound = item.attrib['value']
                elif item.attrib['name'] == 'LowerBound':
                    lowerBound = item.attrib['value']
                elif item.attrib['name'] == 'StartValue':
                    startValue = item.attrib['value']
            assert name !=None
            assert lowerBound != None
            assert upperBound != None
            assert startValue != None
              
            if friendly:
                #Construct a user-friendly name for the parameter name using regexs
                #Look for a match for global parameters: Vector=Values[Test parameter],
                global_string = r'.*Vector=Values\[(?P<name>.*)\].*'
                global_string_re = re.compile(global_string)
                global_match = re.match(global_string_re, name)
                
                if global_match:
                    name = global_match.group('name')
                
                #else check for a local match.
                #Vector=Reactions[Reaction] Parameter=k1
                local_string = r'.*Vector=Reactions\[(?P<reaction>.*)\].*Parameter=(?P<parameter>.*),Reference=Value.*'
                local_string_re = re.compile(local_string)
                local_match = re.match(local_string_re, name)
                
                if local_match:
                    reaction = local_match.group('reaction')
                    parameter = local_match.group('parameter')
                    name = '(%s).%s'%(reaction, parameter)

            parameters.append((name, lowerBound, upperBound, startValue))

        return parameters
    
    
    def __create_report(self, report_type, report_key):
        """Create a report for a particular task, e.g. sensitivity optimization, with key report_key
        
        report_type: a string representing the job type, e.g. SO for sensitivity optimization"""
        if report_type == 'SO':
            listOfReports = self.model.find(xmlns + 'ListOfReports')
            
            #Check a report with the current key doesn't already exist. If it does, delete it
            foundReport = False
            for report in listOfReports:
                if report.attrib['key'] == report_key:
                    foundReport = report
            if foundReport:
                listOfReports.remove(foundReport)
            
            newReport = etree.SubElement(listOfReports, xmlns + 'Report')
            newReport.set('key', report_key)
            newReport.set('name', report_key)
            newReport.set('taskType', 'optimization')
            newReport.set('seperator', '&#x09;')
            newReport.set('precision', '6')
            
            newReport_Comment = etree.SubElement(newReport, xmlns + 'Comment')
            newReport_Comment_body = etree.SubElement(newReport_Comment, xmlns + 'body')
            newReport_Comment_body.set('xmlns', 'http://www.w3.org/1999/xhtml')
            newReport_Comment_body.text = 'Report automatically generated by condor-copasi'

            newReport_Body = etree.SubElement(newReport, xmlns + 'Body')

            newReport_Body_Object1 = etree.SubElement(newReport_Body, xmlns + 'Object')
            newReport_Body_Object1.set('cn','String=#----\n')

            newReport_Body_Object2 = etree.SubElement(newReport_Body, xmlns + 'Object')
            newReport_Body_Object2.set('cn','String=Evals \= ')

            newReport_Body_Object3 = etree.SubElement(newReport_Body, xmlns + 'Object')
            newReport_Body_Object3.set('cn','CN=Root,Vector=TaskList[Optimization],Problem=Optimization,Reference=Function Evaluations')

            newReport_Body_Object4 = etree.SubElement(newReport_Body, xmlns + 'Object')
            newReport_Body_Object4.set('cn','String=\nTime \= ')

            newReport_Body_Object5 = etree.SubElement(newReport_Body, xmlns + 'Object')
            newReport_Body_Object5.set('cn','CN=Root,Vector=TaskList[Optimization],Problem=Optimization,Timer=CPU Time')

            newReport_Body_Object6 = etree.SubElement(newReport_Body, xmlns + 'Object')
            newReport_Body_Object6.set('cn','String=\n')

            newReport_Body_Object7 = etree.SubElement(newReport_Body, xmlns + 'Object')
            newReport_Body_Object7.set('cn','CN=Root,Vector=TaskList[Optimization],Problem=Optimization,Reference=Best Value')
            
        else:
            raise Exception('Unknown report type')
        
    def prepare_so_task(self):
        """Generate the files required to perform the sensitivity optimization, 
        
        This involves creating the appropriate temporary .cps files. The .job files are generated seperately"""
        #First clear the task list, to ensure that no tasks are set to run
        self.__clear_tasks()
        
        #Next, go to the sensitivities task and set the appropriate variables
        sensTask = self.__getTask('sensitivities')
        problem = sensTask.find(xmlns + 'Problem')
        #And open the listofvariables
        for pG in problem:
            if (pG.attrib['name'] == 'ListOfVariables'):
                listOfVariables = pG
        assert listOfVariables != None
        
        #Reset the listOfVariables, and add the appropriate objects
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
        
        ############
        
        #Next, load the optimization task
        optTask = self.__getTask('optimization')
        #And set it scheduled to run, and to update the model
        optTask.attrib['scheduled'] = 'true'
        optTask.attrib['updateModel'] = 'true'
        
        #Find the objective function we wish to change
        problemParameters = optTask.find(xmlns + 'Problem')
        for parameter in problemParameters:
            if (parameter.attrib['name'] == 'ObjectiveExpression'):
                objectiveFunction = parameter
                
            if (parameter.attrib['name'] == 'Maximize'):
                maximizeParameter = parameter
                
            #Set the subtask to sensitivities
            #TODO: At some point allow for other subtasks
            if (parameter.attrib['name'] == 'Subtask'):
                parameter.attrib['value'] = 'CN=Root,Vector=TaskList[Sensitivities]'

        assert objectiveFunction != None
        assert maximizeParameter != None

        #Set the appropriate objective function for the optimization task:
        objectiveFunction.text = '<CN=Root,Vector=TaskList[Sensitivities],Problem=Sensitivities,Array=Scaled sensitivities array[.]>'
        
        ############
        #Create a new report for the optimization task
        report_key = 'condor_copasi_sensitivity_optimization_report'
        self.__create_report('SO', report_key)
        
        #And set the new report for the optimization task
        report = optTask.find(xmlns + 'Report')
    
        #If no report has yet been set, report == None. Therefore, create new report
        if report == None:
            report = etree.Element(xmlns + 'Report')
            optTask.insert(0,report)
        
        report.set('reference', report_key)
        report.set('append', '1')
        
        
        #############
        #get the list of strings to optimize
        #self.get_optimization_parameters(friendly=False) returns a tuple containing the parameter name as the first element
        optimizationStrings = []
        for parameter in self.get_optimization_parameters(friendly=False):
            optimizationStrings.append(parameter[0])
        
        #Build the new xml files and save them
        i = 0
        for optString in optimizationStrings:
            maximizeParameter.attrib['value'] = '1'
            s = Template('max_$index.txt')
            report.attrib['target'] = s.substitute(index=i)
            
            #Update the sensitivities object
            singleObject.set('value',optString)
            
            target = os.path.join(self.path, Template('auto_copasi_xml_max_$index.cps').substitute(index=i))
            
            self.model.write(target)
        
            maximizeParameter.attrib['value'] = '0'
            s = Template('min_$index.txt')
            report.attrib['target'] = s.substitute(index=i)
            target = os.path.join(self.path, Template('auto_copasi_xml_min_$index.cps').substitute(index=i))
            self.model.write(target)
            i = i + 1
        
        
    def prepare_so_condor_jobs(self):
        """Prepare the neccessary .job files to submit to condor for the sensitivity optimization task"""
        ############
        #Build the appropriate .job files for the sensitivity optimization task, write them to disk, and make a note of their locations
        condor_jobs = []
                    
        for i in range(len(self.get_optimization_parameters())):
            for max in ('min', 'max'):
                copasi_file = Template('auto_copasi_xml_${max}_$index.cps').substitute(index=i, max=max)
                condor_job_string = Template(raw_condor_job_string).substitute(copasiPath=self.binary_dir, copasiFile=copasi_file)
                condor_job_filename = os.path.join(self.path, Template('auto_condor_${max}_$index.job').substitute(index=i, max=max))
                condor_file = open(condor_job_filename, 'w')
                condor_file.write(condor_job_string)
                condor_file.close()
                #Append a dict contining (job_filename, std_out, std_err, log_file, job_output)
                condor_jobs.append({
                    'spec_file': condor_job_filename,
                    'std_output_file': str(copasi_file) + '.out',
                    'std_error_file': str(copasi_file) + '.err',
                    'log_file': str(copasi_file) + '.log',
                    'job_output': max + '_' + str(i) + '.txt'
                })

        return condor_jobs
        
    def get_so_results(self, save=False):
        """Collate the output files from a successful sensitivity optimization run. Return a list of the results"""
        #Read through output files
        parameters=self.get_optimization_parameters(friendly=True)
        parameterRange = range(len(parameters))

        results = []

        for i in parameterRange:
            result = {
                'name': parameters[i][0],
                'max_result': '?',
                'max_evals' : '?',
                'max_cpu' : '?',
                'min_result' : '?',
                'min_evals' : '?',
                'min_cpu' : '?',
            }
            #Read min and max files
            for max in ['max', 'min']:
                iterator = 0
                
                try:
                    file = open(os.path.join(self.path, Template('${max}_$index.txt').substitute(index=i, max=max)),'r')
                    output=[None for r in range(4)]
                    for f in file.readlines():
                        value = f.rstrip('\n') #Read the file line by line.
                        #Line 0: seperator. Line 1: Evals. Line 2: Time. Line 3: result
                        index=parameterRange.index(i)
                        output[iterator] = value
                        iterator = (iterator + 1)%4
                    file.close()
                    evals = output[1].split(' ')[2]
                    cpu_time = output[2].split(' ')[2]
                    sens_result = output[3]
                    
                    result[max + '_result'] = sens_result
                    result[max + '_cpu'] = cpu_time
                    result[max + '_evals'] = evals
                    
                except:
                    raise
                    
            results.append(result)
            
        #Finally, if save==True, write these results to file results.txt
        if save:
            if not os.path.isfile(os.path.join(self.path, 'results.txt')):
                results_file = open(os.path.join(self.path, 'results.txt'), 'w')
                header_line = 'Parameter name\tMin result\tMax result\tMin CPU time\tMin Evals\tMax CPU time\tMax Evals\n'
                results_file.write(header_line)
                for result in results:
                    result_line = result['name'] + '\t' + result['min_result'] + '\t' + result['max_result'] + '\t' + result['min_cpu'] + '\t' + result['min_evals'] + '\t' + result['max_cpu'] + '\t' + result['max_evals'] + '\n'
                    results_file.write(result_line)
                results_file.close()
        return results



    def prepare_ss_task(self, runs):
        """Prepares the temp copasi files needed to run n stochastic simulation runs""" 
        #First clear the task list, to ensure that no tasks are set to run
        self.__clear_tasks()

        timeTask = self.__getTask('timeCourse')
        
        #And set it scheduled to run, and to update the model
        timeTask.attrib['scheduled'] = 'true'
        timeTask.attrib['updateModel'] = 'true'

        report = timeTask.find(xmlns + 'Report')

        #Generate a copasi file for each run
        for i in range(runs):
            report.set('append', '1')
            report.set('target', str(i) + '_out.txt')
            filename = os.path.join(self.path, 'auto_copasi_' + str(i) + '.cps')
            self.model.write(filename)
            
        return
            
    def prepare_ss_condor_jobs(self, runs):
        """Prepare the neccessary .job files to submit to condor for the stochastic simulation task"""
        ############
        #Build the appropriate .job files for the sensitivity optimization task, write them to disk, and make a note of their locations
        condor_jobs = []
                    
        for i in range(runs):
            copasi_file = os.path.join(self.path, Template('auto_copasi_$index.cps').substitute(index=i))
            condor_job_string = Template(raw_condor_job_string).substitute(copasiPath=self.binary_dir, copasiFile=copasi_file)
            condor_job_filename = os.path.join(self.path, Template('auto_condor_$index.job').substitute(index=i))
            condor_file = open(condor_job_filename, 'w')
            condor_file.write(condor_job_string)
            condor_file.close()
            #Append a dict contining (job_filename, std_out, std_err, log_file, job_output)
            condor_jobs.append({
                'spec_file': condor_job_filename,
                'std_output_file': str(copasi_file) + '.out',
                'std_error_file': str(copasi_file) + '.err',
                'log_file': str(copasi_file) + '.log',
                'job_output': str(i) + '_out.txt'
            })

        return condor_jobs
        
    def get_ss_output(self, runs):
        """Collate the results from the stochastic simulation task"""
        import numpy
        
        
        
        
#        files = []
#        for i in range(runs):
#            try:
#                file = open(os.path.join(self.path, str(i) + '_out.txt'), 'r')
#                files.append(file)
#            except:
#                raise
#        #Open the result file for writing
#        result = open(os.path.join(self.path, 'result.txt'), 'w')
#        #Copy the first output file to result
#        first = files.pop()
#        for line in first:
#            result.write(line)
#        first.close()
#        result.close()
#        
#        for file in files:
#            result = open(os.path.join(self.path, 'result.txt'), 'r')
#            file_lines = file.readlines()
#            result_lines = result.readlines()
#            result.close()
#            result = open(os.path.join(self.path, 'result.txt'), 'w')
#            for i in range(len(file_lines)):
#                if i==0:
#                    ##Header line
#                    result.write(result_lines[i])
#                else:
#                    file_line = file_lines[i]
#                    result_line = result_lines[i]
#                    
#                    result.write(file_line + result_line)
#            result.close()
#            file.close()
