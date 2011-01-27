#Script to run at set intervals to check on the status of condor jobs, submit them, and collate results if necessary
from web_frontend.condor_copasi_db import models
from web_frontend.copasi.model import CopasiModel
from web_frontend import settings
import subprocess, os, re, datetime

def condor_submit(condor_file):
    """Submit the .job file condor_file to the condor system using the condor_submit command"""
    #condor_file must be an absolute path to the condor job filename
    (directory, filename) = os.path.split(condor_file)
    
    p = subprocess.Popen(['condor_submit', condor_file],stdout=subprocess.PIPE, cwd=directory)
    process_output = p.communicate()[0]
    #Get condor_process number...
    process_id = int(process_output.splitlines()[2].split()[5].strip('.'))
    
    #TODO: Should we sleep here for a bit? 1s? 10s?
    
    return process_id

#Step one, load the jobs that have been confirmed, and need submitting to condor :

new_jobs = models.Job.objects.filter(status='N')

for job in new_jobs:
    try:
        #Load the model
        model = CopasiModel(job.get_filename())
        #Prepare the .job files
        if job.job_type == 'SO':
            condor_jobs = model.prepare_so_condor_jobs()
        elif job.job_type == 'SS':
            #Do 1000 runs per job. TODO: 'chunk' in a more intelligent manner
            max_runs_per_job = 1000
            import math
            #The number of jobs we need is the ceiling of the no of runs/max runs per job
            no_of_jobs = int(math.ceil(float(job.runs) / float(max_runs_per_job)))

            model.prepare_ss_task(job.runs, max_runs_per_job, no_of_jobs)
            condor_jobs = model.prepare_ss_condor_jobs(no_of_jobs)
            
        #elif job.job_type == 'PS':
        #   model.prepare_ps_jobs()
        
        else:
            continue
           
        for cj in condor_jobs:
            try:
                condor_job_id = condor_submit(cj['spec_file'])
                condor_job = models.CondorJob(parent=job, spec_file=cj['spec_file'], std_output_file=cj['std_output_file'], std_error_file = cj['std_error_file'], log_file=cj['log_file'], job_output=cj['job_output'], queue_status='Q', queue_id=condor_job_id)
                condor_job.save()
            except:
                print 'Error submitting to condor. Check the condor scheduler service is running.'#TODO: pass to log file
            
        job.status = 'S'
        job.last_update=datetime.datetime.today()
        job.save()
    except:
        raise
        job.status = 'E'
        job.last_update=datetime.datetime.today()
        job.finish_time=datetime.datetime.today()
        job.save()


############        

#Step two, go through the condor_q output and update the status of our condor jobs
try:
    condor_q_process = subprocess.Popen('condor_q', stdout=subprocess.PIPE)
    condor_q_output = condor_q_process.communicate()[0].splitlines()
    #Process the output using regexps. Example line is as follows:
    # ID      OWNER            SUBMITTED     RUN_TIME ST PRI SIZE CMD               
    #18756.0   ed              1/7  11:45   0+03:19:53 R  0   22.0 CopasiSE.$$(OpSys)
    condor_q=[]
    no_of_jobs = len(condor_q_output) - 6
    if no_of_jobs > 0:
        job_string = r'(?P<id>\d+)\.0\s+(?P<owner>\S+)\s+(?P<sub_date>\S+)\s+(?P<sub_time>\S+)\s+(?P<run_time>\S+)\s+(?P<status>\w)\s+(?P<pri>\d+)\s+(?P<size>\S+)\s+(?P<cmd>\S+)'
        job_re = re.compile(job_string)
        for job_listing in condor_q_output:
            match = job_re.match(job_listing)
            if match:
                id = match.group('id')
                status = match.group('status')
                condor_q.append((id,status))


    #Now, go through all jobs that, at the last update, had been submitted (status = 'Q'|'R'|'H'|'I')
    submitted_jobs = models.CondorJob.objects.filter(queue_status='Q') | models.CondorJob.objects.filter(queue_status='R') | models.CondorJob.objects.filter(queue_status='I') | models.CondorJob.objects.filter(queue_status='H')
    #Check to see if each of these jobs is in the condor_q output
    for submitted_job in submitted_jobs:
        found=False
        for id, status in condor_q:
            #if so, update the status
            if id == str(submitted_job.queue_id):
                found = True
                submitted_job.queue_status = status
                submitted_job.save()
                break
        #else, the job has gone from the queue, so assume it has finished, and update the status
        if not found:
            submitted_job.queue_status = 'F'
            submitted_job.save()            
except:
    print 'Error processing condor_q output. Ensure the condor scheduler service is running'#TODO:pass to log
############

#Go through each of the model.Jobs with status 'S' (submitted), and look at each of its child CondorJobs. If all have finished, mark the Job as 'F' (finished). If any CondorJobs have been held ('H'), mark the Job as Error ('E')

submitted_jobs = models.Job.objects.filter(status='S') | models.Job.objects.filter(status='X')

for job in submitted_jobs:
    try:
        condor_jobs = models.CondorJob.objects.filter(parent=job)
        error=False;
        still_running=False
        for condor_job in condor_jobs:
            if condor_job.queue_status != 'F':
                still_running = True
                break
            elif condor_job.queue_status == 'H':
                error = True
                break
        if error:
            job.status='E'
            job.finish_time=datetime.datetime.today()
            job.last_update=datetime.datetime.today()
            job.save()
        elif not still_running:
            if job.status == 'X':
                #If the second stage of condor processing has finished, mark the job as complete
                job.status='C'
                job.finish_time=datetime.datetime.today()
            else:
                #Otherwise mark it as waiting for local processing
                job.status = 'W'
            job.last_update=datetime.datetime.today()
            #job.finish_time=datetime.datetime.today()
            job.save()
        else:
            job.last_update=datetime.datetime.today()
            job.save()
    except:
        pass
############

#Collate the results

#Get the list of jobs marked as finished, waiting for processing
waiting = models.Job.objects.filter(status='W')
for job in waiting:
    try:
        model = CopasiModel(job.get_filename())
        if job.job_type == 'SO':
            #TODO: doesn't do validation step yet. This step should probably be condorised.
            #Mark the job as complete
            job.status='C'
            job.finish_time=datetime.datetime.today()
            job.last_update=datetime.datetime.today()
            job.save()
            model.get_so_results(save=True)
        elif job.job_type == 'SS':
            condor_jobs = models.CondorJob.objects.filter(parent=job)
            cj = model.prepare_ss_process_job(len(condor_jobs), job.runs)
            condor_job_id = condor_submit(cj['spec_file'])
            condor_job = models.CondorJob(parent=job, spec_file=cj['spec_file'], std_output_file=cj['std_output_file'], std_error_file = cj['std_error_file'], log_file=cj['log_file'], job_output=cj['job_output'], queue_status='Q', queue_id=condor_job_id)
            condor_job.save()
            job.status='X' # Set the job status as processing on condor

            job.last_update=datetime.datetime.today()
            job.save()
    except:
        job.status='E'
        job.finish_time=datetime.datetime.today()
        job.last_update=datetime.datetime.today()
        job.save()
        print 'Error processing job ' + str(job.name)
        raise
        
        
complete = models.Job.objects.filter(status='C')

for job in complete:
    model = CopasiModel(job.get_filename())
    
    
############
#Go through completed jobs, and remove anything older than settings.COMPLETED_JOB_DAYS
if settings.COMPLETED_JOB_REMOVAL_DAYS >0:
    pass
