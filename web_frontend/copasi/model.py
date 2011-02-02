import subprocess, os, re, math, time
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
            return True
        
        elif job_type == 'PS':
            scanTask = self.__getTask('scan')
            problem = scanTask.find(xmlns+'Problem')
            scanItems = problem.find(xmlns + 'ParameterGroup')
            if len(scanItems) == 0:
                return 'At least one scan must have been set'
            #Extract some details about the scan task
            firstScan = scanItems[0]
            for parameter in firstScan:
                if parameter.attrib['name'] == 'Type':
                    scan_type = parameter
                if parameter.attrib['name'] == 'Number of steps':
                    no_of_steps = parameter
            #Check that the first scan item is either a scan or a repeat
            if not (scan_type.attrib['value'] == '1' or scan_type.attrib['value'] == '0'):
                return 'The first item in the scan task must be either a Parameter Scan or a repeat'
            #Check that, if the first scan item is a parameter scan, there is at least 1 interval
            if scan_type.attrib['value'] == '1' and int(no_of_steps.attrib['value']) < 1:
                return 'The first-level Parameter Scan must have at least one interval. If only one repeat is required, consider replacing the Parameter Scan with a Repeat'
            report = scanTask.find(xmlns + 'Report')
            if report == None or report.attrib['reference'] == '':
                return 'A report must be set for the scan task'
            return True
            
        else:
            return True
        
    def __copasiExecute(self, filename, tempdir, timeout=-1):
        """Private function to run Copasi locally in a temporary folder."""
        import process
        returncode, stdout, stderr = process.run([self.binary, '--nologo',  '--home', tempdir, filename], cwd=tempdir, timeout=timeout)
        return returncode, stdout, stderr
        
   
    def __getTask(self,task_type, model=None):
        """Get the XML tree representing a task with type: 'type'"""
        if model == None:
            model = self.model
        #Get the task list
        try:
            listOfTasks = model.find(xmlns + 'ListOfTasks')
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
    
    def __get_compartment_name(self, key):
        """Go through the list of compartments and return the name of the compartment with a given key"""
        model = self.model.find(xmlns + 'Model')
        compartments = model.find(xmlns + 'ListOfCompartments')
        for compartment in compartments:
            if compartment.attrib['key'] == key:
                name = compartment.attrib['name']
                break
        assert name != None
        return name
    
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
    
    def get_ps_number(self):
        """Returns the number of runs set up for the parameter scan task"""
        scanTask = self.__getTask('scan')
        problem = scanTask.find(xmlns+'Problem')
        #scanItems contains a list of parameter groups, each of which represents a scan
        scanItems = problem.find(xmlns + 'ParameterGroup')
        #Now, go through each parameter group and get

        
        scan_number = 0
        for parameterGroup in scanItems:
            for parameter in parameterGroup:
                if parameter.attrib['name'] == 'Number of steps':
                    no_of_steps = int(parameter.attrib['value'])
                if parameter.attrib['name'] == 'Type':
                    type = int(parameter.attrib['value'])
             
            if type == 0:
                #Repeat task. Number of steps is simply the value of no_of_steps
                if scan_number == 0:
                    #If this is the first level of scans
                    scan_number += no_of_steps
                else:
                    scan_number *= no_of_steps
            elif type == 1:
                #Parameter scan task - no of steps is actually given in intervals, so add 1
                if scan_number == 0:
                    scan_number += no_of_steps + 1
                else:
                    scan_number *= no_of_steps + 1
            elif type == 2:
                #Random distribution, do nothing
                pass
        
        return scan_number
        
    
    def __create_report(self, report_type, report_key):
        """Create a report for a particular task, e.g. sensitivity optimization, with key report_key
        
        report_type: a string representing the job type, e.g. SO for sensitivity optimization"""

        listOfReports = self.model.find(xmlns + 'ListOfReports')
        
        #Check a report with the current key doesn't already exist. If it does, delete it
        foundReport = False
        for report in listOfReports:
            if report.attrib['key'] == report_key:
                foundReport = report
        if foundReport:
            listOfReports.remove(foundReport)

        if report_type == 'SO':

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
        
        
        elif report_type == 'SS':
            #Use the following xml string as a template
            report_string = Template(
            """<Report xmlns="http://www.copasi.org/static/schema" key="${report_key}" name="auto_ss_report" taskType="timeCourse" separator="&#x09;" precision="6">
      <Comment>
        A table of time, variable species particle numbers, variable compartment volumes, and variable global quantity values.
      </Comment>
      <Table printTitle="1">
        
      </Table>
    </Report>"""
            ).substitute(report_key=report_key)
            report = etree.XML(report_string)
            model_name = self.get_name()
            
            table = report.find(xmlns + 'Table')
            time_object = etree.SubElement(table, xmlns + 'Object')
            time_object.set('cn', 'Model=' + model_name + ',Reference=Time')
            
            for variable in self.get_variables():
                row = etree.SubElement(table, xmlns + 'Object')
                row.set('cn', variable) 
            
            listOfReports.append(report)
        
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



    def prepare_ss_task(self, runs, max_runs_per_job, no_of_jobs):
        """Prepares the temp copasi files needed to run n stochastic simulation runs
        
        First sets up the scan task with a repeat, and sets each repeat to run i times. 
        Uses a the chiunking algorithm to determine how many repeats to run for each scan.
        """ 
        #First clear the task list, to ensure that no tasks are set to run
        self.__clear_tasks()

        scanTask = self.__getTask('scan')
        
        #And set it scheduled to run, and to not update the model
        scanTask.attrib['scheduled'] = 'true'
        scanTask.attrib['updateModel'] = 'false'
 
        ############
        #Create a new report for the ss task
        report_key = 'condor_copasi_stochastic_simulation_report'
        self.__create_report('SS', report_key)
        
        #And set the new report for the ss task
        report = scanTask.find(xmlns + 'Report')
    
        #If no report has yet been set, report == None. Therefore, create new report
        if report == None:
            report = etree.Element(xmlns + 'Report')
            scanTask.insert(0,report)
        
        report.set('reference', report_key)
        report.set('append', '1')

        #Set the XML for the problem task as follows:
#        """<Parameter name="Subtask" type="unsignedInteger" value="1"/>
#        <ParameterGroup name="ScanItems">
#          <ParameterGroup name="ScanItem">
#            <Parameter name="Number of steps" type="unsignedInteger" value="10"/>
#            <Parameter name="Type" type="unsignedInteger" value="0"/>
#            <Parameter name="Object" type="cn" value=""/>
#          </ParameterGroup>
#        </ParameterGroup>
#        <Parameter name="Output in subtask" type="bool" value="1"/>
#        <Parameter name="Adjust initial conditions" type="bool" value="0"/>"""

        #Open the scan problem, and clear any subelements
        scan_problem = scanTask.find(xmlns + 'Problem')
        scan_problem.clear()
        
        #Add a subtask parameter (value 1 for timecourse)
        subtask_parameter = etree.SubElement(scan_problem, xmlns + 'Parameter')
        subtask_parameter.attrib['name'] = 'Subtask'
        subtask_parameter.attrib['type'] = 'unsignedInteger'
        subtask_parameter.attrib['value'] = '1'
        
        #Add a single ScanItem for the repeats
        subtask_pg = etree.SubElement(scan_problem, xmlns + 'ParameterGroup')
        subtask_pg.attrib['name'] = 'ScanItems'
        subtask_pg_pg = etree.SubElement(subtask_pg, xmlns + 'ParameterGroup')
        subtask_pg_pg.attrib['name'] = 'ScanItem'
        
        p1 = etree.SubElement(subtask_pg_pg, xmlns+'Parameter')
        p1.attrib['name'] = 'Number of steps'
        p1.attrib['type'] = 'unsignedInteger'
        p1.attrib['value'] = '0'# Assign this later

        
        p2 = etree.SubElement(subtask_pg_pg, xmlns+'Parameter')
        p2.attrib['name'] = 'Type'
        p2.attrib['type'] = 'bool'
        p2.attrib['value'] = '0'
        
        p3 = etree.SubElement(subtask_pg_pg, xmlns+'Parameter')
        p3.attrib['name'] = 'Object'
        p3.attrib['type'] = 'cn'
        p3.attrib['value'] = ''
        
        p4 = etree.SubElement(scan_problem, xmlns+'Parameter')
        p4.attrib['name'] = 'Output in subtask'
        p4.attrib['type'] = 'bool'
        p4.attrib['value'] = '1'
        
        p5 = etree.SubElement(scan_problem, xmlns+'Parameter')
        p5.attrib['name'] = 'Adjust initial conditions'
        p5.attrib['type'] = 'bool'
        p5.attrib['value'] = '0'
        

        
      
        
        runs_left=runs # Decrease this value as we generate the jobs
        
        for i in range(no_of_jobs):
            #Calculate the number of runs per job. This will either be max_runs_per_job, or if this is the last job, runs_left
            job_runs = min(max_runs_per_job, runs_left)
            no_of_steps = str(job_runs)
            p1.attrib['value'] = no_of_steps
            runs_left -= job_runs
            
            report.set('target', str(i) + '_out.txt')
            filename = os.path.join(self.path, 'auto_copasi_' + str(i) + '.cps')
            self.model.write(filename)
            
        return
            
    def prepare_ss_condor_jobs(self, jobs):
        """Prepare the neccessary .job files to submit to condor for the stochastic simulation task"""
        ############
        #Build the appropriate .job files for the sensitivity optimization task, write them to disk, and make a note of their locations
        condor_jobs = []
                    
        for i in range(jobs):
            copasi_file = Template('auto_copasi_$index.cps').substitute(index=i)
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
        
    def prepare_ss_process_job(self, jobs, runs):
        """Collate the results from the stochastic simulation task"""
        #First, read through the various output files, and concatenate into a single file raw_results.txt
        assert jobs >0
        #Copy the whole of the first file
        output = open(os.path.join(self.path, 'raw_results.txt'), 'w')
        
        file0 = open(os.path.join(self.path, '0_out.txt'), 'r')
        for line in file0:
            output.write(line)
        file0.close()       
        output.flush()
        #Now, copy over all but the first line of the other files
        for i in range(jobs)[1:]:

            file = open(os.path.join(self.path, str(i) + '_out.txt'), 'r')
            firstline = True
            for line in file:
                if not firstline:
                    output.write(line)
                firstline = False
            file.close()
            output.flush()
        output.close()
                
     
        ############
        #The rest of the processing is moved to condor, by the file ss_results_process.py
        ############
        
        #Prepare the condor job file
        script = os.path.join(settings.MEDIA_ROOT, 'ss_results_process.py')
        raw_results = os.path.join(self.path, 'raw_results.txt')

        job_template = Template("""#Condor job
executable = ${script}
universe       = vanilla 
arguments = 
transfer_input_files = ${raw_results}
log =  results.log  
error = results.err
output = results.out
Requirements = ( OpSys == "LINUX" && HAS_PYTHON26 == True) 
should_transfer_files = YES
when_to_transfer_output = ON_EXIT
queue\n""")

        job_string = job_template.substitute(script=script, raw_results=raw_results)
        job_file = open(os.path.join(self.path, 'results.job'), 'w')
        job_file.write(job_string)
        job_file.close()
        
        return {
            'spec_file': os.path.join(self.path, 'results.job'),
            'std_output_file': os.path.join(self.path, 'results.out'),
            'std_error_file': os.path.join(self.path, 'results.err'),
            'log_file': os.path.join(self.path, 'results.log'),
            'job_output': os.path.join(self.path, 'results.txt'),
        }
        
    def get_variables(self, pretty=False):
        """Returns a list of all variable metabolites, compartments and global quantities in the model.
        
        By default, returns the internal string representation, e.g. CN=Root,Model=Kummer calcium model,Vector=Compartments[compartment],Vector=Metabolites[a],Reference=ParticleNumber. Running pretty=True will parse the string and return a user-friendly version of the names.
        """
        
        output = []
        #Get the model XML tree
        model = self.model.find(xmlns + 'Model')
        #Get list of metabolites
        metabolites = model.find(xmlns + 'ListOfMetabolites')
        
        for metabolite in metabolites:
            name = metabolite.attrib['name']
            simulationType = metabolite.attrib['simulationType']
            compartment_key = metabolite.attrib['compartment']
            
            if simulationType != 'fixed':
                if pretty:
                    output.append(name + ' (Particle Number)')
                else:
                    #Format the metabolite string as: CN=Root,Model=modelname,Vector=Compartments[compartment],Vector=Metabolites[a],Reference=ParticleNumber
                    compartment_name = self.__get_compartment_name(compartment_key)
                    model_name = self.get_name()
                    
                    output_template = Template('CN=Root,Model=${model_name},Vector=Compartments[${compartment_name}],Vector=Metabolites[${name}],Reference=ParticleNumber')
                    
                    output_string = output_template.substitute(model_name=model_name, compartment_name=compartment_name, name=name)
                    output.append(output_string)
        #Next, get list of non-fixed compartments:
        compartments = model.find(xmlns + 'ListOfCompartments')
        for compartment in compartments:
            name = compartment.attrib['name']
            simulationType = compartment.attrib['simulationType']
            
            if simulationType != 'fixed':
                if pretty:
                    output.append(name + ' (' + model.attrib['volumeUnit'] + ')')
                else:
                    #format the compartment string as: "CN=Root,Model=Kummer calcium model,Vector=Compartments[compartment_2],Reference=Volume"
                    model_name = self.get_name()
                    output_template = Template('CN=Root,Model=${model_name},Vector=Compartments[${name}],Reference=Volume')
                    output_string = output_template.substitute(model_name=model_name, name=name)
                    output.append(output_string)
                    
        #Finally, get non-fixed global quantities
        values = model.find(xmlns + 'ListOfModelValues')
        #Hack - If no values have been set in the model, use the empty list to avoid a NoneType error
        if values == None:
            values = []
        for value in values:
            name = value.attrib['name']
            simulationType = value.attrib['simulationType']
            
            if simulationType != 'fixed':
                if pretty:
                    output.append(name + ' (Value)')
                else:
                    #format as: CN=Root,Model=Kummer calcium model,Vector=Values[quantity_1],Reference=Value"
                    model_name = self.get_name()
                    output_template = Template('CN=Root,Model=${model_name},Vector=Values[${name}],Reference=Value')
                    output_string = output_template.substitute(model_name=model_name, name=name)
                    output.append(output_string)
                    
        return output
        
    def prepare_ps_jobs(self):
        """Prepare the parallel scan task
        
        Efficiently splitting multiple nested scans is a hard problem, and currently beyond the scope of this project.
        As such, we simplify the problem by only splitting along the first scan task. It is the user's prerogative to ensure the scan task is set up in a way that enables the scan task to be efficiently split.
        Because of a limitation with the Copasi scan task -- that there must be at least two parameters for each scan, i.e. min and max, we set the requirement that the first scan must have at least one interval (corresponding to two parameter values), and that when splitting, each new scan must also have a minimum of at least one interval.
        """
        
        def get_range(min, max, intervals, log):
            """Get the range of parameters for a scan."""
            if not log:
                min = float(min)
                max = float(max)
                difference = max-min
                step_size = difference/intervals
                output = [min + i*step_size for i in range(intervals+1)]
                return output
            else:
                from math import log10 as log
                log_min = log(min)
                log_max = log(max)
                log_difference = log_max - log_min
                step_size = log_difference/intervals
                output = [pow(10, log_min + i*step_size) for i in range(intervals+1)]
                return output
                
        
        #First, read in the task
        scanTask = self.__getTask('scan')
        self.__clear_tasks()
        scanTask.attrib['scheduled'] = 'true'
        problem = scanTask.find(xmlns+'Problem')
        scanTasks = problem.find(xmlns + 'ParameterGroup')
        
        #Find the report for the scan task and store as a variable the node containing it's output
        report = scanTask.find(xmlns+'Report')
        assert report != None
        
        
        #Get the first scan in the list
        firstScan = scanTasks[0]
        
        parameters = {} #Dict to store the parameters that we're interested in reading/changing
        for parameter in firstScan:
            if parameter.attrib['name'] == 'Number of steps':
                parameters['no_of_steps'] = parameter
            if parameter.attrib['name'] == 'Type':
                parameters['type'] = parameter
            if parameter.attrib['name'] == 'Maximum':
                parameters['max'] = parameter
            if parameter.attrib['name'] == 'Minimum':
                parameters['min'] = parameter
            if parameter.attrib['name'] == 'log':
                parameters['log'] = parameter
                    
        #Read the values of these parameters before we go about changing them
        no_of_steps = int(parameters['no_of_steps'].attrib['value'])
        assert no_of_steps > 0
        task_type = int(parameters['type'].attrib['value'])
        if task_type == 1:
            max_value = float(parameters['max'].attrib['value'])
            min_value = float(parameters['min'].attrib['value'])
            if parameters['log'].attrib['value'] == '0':
                log = False
            else:
                log = True
            no_of_steps += 1 #Parameter scans actually consider no of intervals, which is one less than the number of steps, or actual parameter values. We will work with the number of discrete parameter values, and will decrement this value when saving new files
        
        ############
        #Benchmarking
        ############
        #Measure the time taken to run a single run of the first-level scan
        import tempfile
        #Set the number of steps as 1, and write a temp XML file
        
        #Do this 5 times, and take the average
        
        run_times = []
        for i in range(5):
            temp_file, temp_filename = tempfile.mkstemp(prefix='condor_copasi_', suffix='.cps')
            tempdir, rel_filename = os.path.split(temp_filename)

            parameters['no_of_steps'].attrib['value'] = '1'
            
            self.model.write(temp_filename)
            
            #Note the start time
            start_time = time.time()
            self.__copasiExecute(temp_filename, tempdir, timeout=600)
            finish_time = time.time()
            run_time = finish_time - start_time
            run_times.append(run_time)
            
            os.remove(temp_filename)
            #If running for >10 seconds, assume this is a good enough measure, and don't take any more averages to save time
            if run_time > 10:
                break
        #Calculate the mean
        time_per_step = sum(run_times)/len(run_times)
        
        #If this was a scan task, not a repeat, then we'll have actually run two steps, not one. Adjust the time accordingly
        if task_type == 1:
            time_per_step = time_per_step/2
        
        #We want to split the scan task up into subtasks of time ~= 10 mins (600 seconds)
        #time_per_job = no_of_steps * time_per_step => no_of_steps = time_per_job/time_per_step
        
        time_per_job = settings.IDEAL_JOB_TIME * 60
        
        #Calculate the number of steps for each job. If this has been calculated as more than the total number of steps originally specified, use this value instead
        no_of_steps_per_job = min(int(round(float(time_per_job) / time_per_step)), no_of_steps)


        #Because of a limitation of Copasi, each parameter must have at least one interval, or two steps per job - corresponding to the max and min parameters
        #Force this limitation:
        if task_type == 1:
            if no_of_steps_per_job < 2:
                no_of_steps_per_job = 2
        
        no_of_jobs = int(math.ceil(float(no_of_steps) / no_of_steps_per_job))
        
        print 'Benchmarking complete'
        print '%s steps in total' %no_of_steps
        print 'Estimated time per step: %s' % time_per_step
        print 'No of steps per job: %s' % no_of_steps_per_job
        
        ##############
        #Job preparation
        ##############
        
        #First, deal with the easy case -- where the top-level item is a repeat.

        if task_type == 0:
            step_count = 0
            for i in range(no_of_jobs):
                if no_of_steps_per_job + step_count > no_of_steps:
                    steps = no_of_steps - step_count
                else:
                    steps = no_of_steps_per_job
                step_count += steps
                
                if steps > 0:
                    parameters['no_of_steps'].attrib['value'] = str(steps)
                    report.attrib['target'] = str(i) + '_out.txt'
                    filename = os.path.join(self.path, 'auto_copasi_' + str(i) + '.cps')
                    self.model.write(filename)
                
            
        
        
        #Then, deal with the case where we actually scan a parameter
        #Example: parameter range = [1,2,3,4,5,6,7,8,9,10] - min 1, max 10, 9 intervals => 10 steps
        #Split into 3 jobs of ideal length 3, min length 2
        #We want [1,2,3],[4,5,6],[7,8,9,10]
        elif task_type == 1:
            scan_range = get_range(min_value, max_value, no_of_steps-1, log)
            job_scans = []
            for i in range(no_of_jobs):
                #Go through the complete list of parameters, and split into jobs of size no_of_steps_per_job
                job_scans.append(scan_range[i*no_of_steps_per_job:(i+1)*no_of_steps_per_job]) #No need to worry about the final index being outside the list range - python doesn't mind
            
            #If the last job is only of length 1, merge it with the previous job
            assert no_of_jobs == len(job_scans)
            if len(job_scans[no_of_jobs-1]) ==1:
                job_scans[no_of_jobs-2] = job_scans[no_of_jobs-2] + job_scans[no_of_jobs-1]
                del job_scans[no_of_jobs-1]
                no_of_jobs -= 1
            
            #Write the Copasi XML files
            for i in range(no_of_jobs):
                job_scan_range = job_scans[i]
                job_min_value = job_scan_range[0]
                job_max_value = job_scan_range[-1]
                job_no_of_intervals = len(job_scan_range)-1
                
                parameters['min'].attrib['value'] = str(job_min_value)
                parameters['max'].attrib['value'] = str(job_max_value)
                parameters['no_of_steps'].attrib['value'] = str(job_no_of_intervals)
                
                #Set the report output
                report.attrib['target'] = str(i) + '_out.txt'
                
                filename = os.path.join(self.path, 'auto_copasi_' + str(i) + '.cps')
                self.model.write(filename)
        return no_of_jobs
        
    def prepare_ps_condor_jobs(self, jobs):
        """Prepare the condor jobs for the parallel scan task"""
                ############
        #Build the appropriate .job files for the sensitivity optimization task, write them to disk, and make a note of their locations
        condor_jobs = []
                    
        for i in range(jobs):
            copasi_file = Template('auto_copasi_$index.cps').substitute(index=i)
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
        
    def process_ps_results(self, jobs):
        output_file = open(os.path.join(self.path, 'results.txt'), 'w')
        
        #Copy the contents of the first file to results.txt
        for line in open(os.path.join(self.path, '0_out.txt'), 'r'):
            output_file.write(line)
            
        #And for all other files, copy everything but the last line
        for i in range(jobs)[1:]:
            firstLine = True
            for line in open(os.path.join(self.path, str(i) + '_out.txt'), 'r'):
                if not firstLine:
                    output_file.write(line)
                firstLine = False
                
        output_file.close()
