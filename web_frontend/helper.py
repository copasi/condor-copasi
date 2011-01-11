#Script to run at set intervals to check on the status of condor jobs, submit them, and collate results if necessary
from web_frontend.condor_copasi_db import models
from web_frontend.copasi.model import CopasiModel
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
    #Load the model
    model = CopasiModel(job.get_filename())
    #Prepare the .job files
    if job.job_type == 'SO':
        condor_jobs = model.prepare_so_condor_jobs()
    elif job.job_type == 'SS':
        model.prepare_ss_task(job.runs)
        condor_jobs = model.prepare_ss_condor_jobs(job.runs)
    
    for cj in condor_jobs:
        condor_job_id = condor_submit(cj['spec_file'])
        condor_job = models.CondorJob(parent=job, spec_file=cj['spec_file'], std_output_file=cj['std_output_file'], std_error_file = cj['std_error_file'], log_file=cj['log_file'], job_output=cj['job_output'], queue_status='Q', queue_id=condor_job_id)
        condor_job.save()
        
    job.status = 'S'
    job.save()

############        

#Step two, go through the condor_q output and update the status of our condor jobs
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
            
############

#Go through each of the model.Jobs with status 'S' (submitted), and look at each of its child CondorJobs. If all have finished, mark the Job as 'F' (finished). If any CondorJobs have been held ('H'), mark the Job as Error ('E')

submitted_jobs = models.Job.objects.filter(status='S')

for job in submitted_jobs:
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
        job.save()
    elif not still_running:
        #Mark the job as finished, waiting for validation
        job.status='W'
        #job.finish_time=datetime.datetime.today()
        job.save()

############

#Collate the results

#Get the list of jobs marked as finished, waiting for validation
waiting = models.Job.objects.filter(status='W')
for job in waiting:
    try:
        model = CopasiModel(job.get_filename())
        if job.job_type == 'SO':
            #TODO: doesn't do validation step yet. This step should probably be condorised.
            #Mark the job as complete
            job.status='C'
            job.finish_time=datetime.datetime.today()
            job.save()
            model.get_so_results(save=True)
        elif job.job_type == 'SS':
            model.get_ss_output(job.runs)
            
    except:
        raise
        job.status='E'
        job.save()
        
complete = models.Job.objects.filter(status='C')

for job in complete:
    model = CopasiModel(job.get_filename())

