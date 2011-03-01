#Script to run at set intervals to check on the status of condor jobs, submit them, and collate results if necessary
from web_frontend.condor_copasi_db import models
from web_frontend.copasi.model import CopasiModel
from web_frontend import settings, condor_log, condor_status
import subprocess, os, re, datetime
import logging

def condor_submit(condor_file, username=None, results=False):
    """Submit the .job file condor_file to the condor system using the condor_submit command"""
    #condor_file must be an absolute path to the condor job filename
    (directory, filename) = os.path.split(condor_file)
    if not settings.SUBMIT_WITH_USERNAMES:
        p = subprocess.Popen(['condor_submit', condor_file],stdout=subprocess.PIPE, cwd=directory)
    else:
        #Use sudo to submit with the job's user as username instead of condor-copasi-daemon username
        #First, though, we need to change the ownership of the copasi file we're submitting along with the job
        #We can't use chown, because we're not superuser
        #Instead, because we have write access to the file, we can copy it, delete the original, and move the copy back to the original filename
        #First, work out the name of the copasi file
        #If the job is auto_condor_0.job, the corresponding copasi file will be auto_copasi_0.cps
        #If we're processing the SS results file, skip this step.
        if not results:
            job_re = re.compile(r'auto_condor_(?P<name>.+).job')
            name = job_re.match(filename).group('name')
            copasi_filename = 'auto_copasi_' + name + '.cps'
            
            
            
            #Copy the copasi filename to a temp file
            subprocess.check_call(['sudo', '-n', '-u', username, '/bin/cp', '--preserve=mode', os.path.join(directory, copasi_filename), os.path.join(directory, copasi_filename + '.tmp')])      
            
            #Remove the original copasi file
            subprocess.check_call(['sudo', '-n', '-u', username, '/bin/rm', '-f', os.path.join(directory, copasi_filename)])
            
            #Rename the temp file back to the original name
            subprocess.check_call(['sudo', '-n', '-u', username, '/bin/mv', os.path.join(directory, copasi_filename + '.tmp'), os.path.join(directory, copasi_filename)])
            
            #Doublecheck we have group write permissions
            subprocess.check_call(['sudo', '-n', '-u', username, '/bin/chmod', 'g+w', os.path.join(directory, copasi_filename)])
        
        #Finally, we can run condor_submit
        p = subprocess.Popen(['sudo', '-n', '-u', username, '/usr/bin/condor_submit', condor_file],stdout=subprocess.PIPE, cwd=directory)
        
    process_output = p.communicate()[0]
    #Get condor_process number...
    process_id = int(process_output.splitlines()[2].split()[5].strip('.'))
    
    #TODO: Should we sleep here for a bit? 1s? 10s?
    
    return process_id

def condor_rm(queue_id, username=None):
    if not settings.SUBMIT_WITH_USERNAMES:
        p = subprocess.Popen(['condor_rm', str(queue_id)])
        p.communicate()
    else:
        subprocess.check_call(['sudo', '-n', '-u', username, '/usr/bin/condor_rm', str(queue_id)])
        #p.communicate()
        

def run():
    #Set up logging, with the appropriate log level
    logging.basicConfig(filename=settings.LOG_FILE,level=settings.LOG_LEVEL, format='%(asctime)s::%(levelname)s::%(message)s', datefmt='%Y-%m-%d, %H:%M:%S')

    #Step one, load the jobs that have been confirmed, and need submitting to condor :

    new_jobs = models.Job.objects.filter(status='N')

    for job in new_jobs:
        logging.debug('New job found: ' + str(job.id) + ', user: ' + str(job.user))
        try:
            #Load the model
            model = CopasiModel(job.get_filename())
            #Prepare the .job files
            if job.job_type == 'SO':
                condor_jobs = model.prepare_so_condor_jobs()
            elif job.job_type == 'SS':
                no_of_jobs = model.prepare_ss_task(job.runs)
                condor_jobs = model.prepare_ss_condor_jobs(no_of_jobs)
                
            elif job.job_type == 'PS':
                no_of_jobs = model.prepare_ps_jobs()
                condor_jobs = model.prepare_ps_condor_jobs(no_of_jobs)
                
            elif job.job_type == 'OR':
                no_of_jobs = model.prepare_or_jobs(job.runs)
                condor_jobs = model.prepare_or_condor_jobs(no_of_jobs)
                
            elif job.job_type == 'PR':
                no_of_jobs = model.prepare_pr_jobs(job.runs)
                condor_jobs = model.prepare_pr_condor_jobs(no_of_jobs)
            elif job.job_type == 'OD':
                #No need to prepare the job. This was done as the job was submitted
                condor_jobs = model.prepare_od_condor_jobs()           
            else:
                continue
               
            for cj in condor_jobs:
                try:
                    condor_job_id = condor_submit(cj['spec_file'], username=str(job.user.username))
                    condor_job = models.CondorJob(parent=job, spec_file=cj['spec_file'], std_output_file=cj['std_output_file'], std_error_file = cj['std_error_file'], log_file=cj['log_file'], job_output=cj['job_output'], queue_status='Q', queue_id=condor_job_id)
                    condor_job.save()
                except:
                    logging.exception('Error submitting job(s) to Condor; ensure condor scheduler service is running. Job: ' + str(job.id)  + ', User: ' + str(job.user))
            logging.debug('Submitted ' + str(len(condor_jobs)) + ' to Condor')
            job.status = 'S'
            job.last_update=datetime.datetime.today()
            job.save()
        except Exception, e:
            logging.warning('Error preparing job for condor submission. Job: ' + str(job.id) + ', User: ' + str(job.user))
            logging.exception('Exception: ' + str(e))

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

        if len(submitted_jobs) > 0:
            logging.debug('Checking condor_q status. ' + str(len(submitted_jobs)) + ' running jobs may be in queue')
        
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
    except Exception, e:
        logging.error('Error processing condor_q output. Ensure the condor scheduler service is running')
        logging.error('Exception: ' + str(e))
    ############

    #Go through each of the model.Jobs with status 'S' (submitted) or 'X'(processing data on condor), and look at each of its child CondorJobs. If all have finished, mark the Job as 'W' (finished, waiting for processing). If any CondorJobs have been held ('H'), mark the Job as Error ('E')

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
                    logging.warning('Condor job id ' + str(condor_job.queue_id) + ' held')
                    error = True
                    break
            if error:
                logging.warning('Job: ' + str(job.id) + ', User: ' + str(job.user) + ' did not complete successfully')
                job.status='E'
                job.finish_time=datetime.datetime.today()
                job.last_update=datetime.datetime.today()
                job.save()
            elif not still_running:
                logging.debug('Job ' + str(job.id) + ', User: ' + str(job.user) + ' finished processing on condor')
                
                #Open the log file and check the exit status
                failed_job_count = 0
                for condor_job in condor_jobs:
                    try:
                        filename=os.path.join(job.get_path(), condor_job.log_file)
                        log = condor_log.Log(filename)
                        assert log.termination_status == 0
                    except:
                        failed_job_count += 1
                    
                #Now, depending on the type of job, mark it as either 'error' nor not.
                #For SS task, we require all jobs to have finished successfully
                if failed_job_count > 0 and job.job_type == 'SS':
                    logging.exception('Condor job exited with nonzero return value. Condor Job: ' + str(condor_job.queue_id) + ', Job: ' + str(job.id) + ', User: ' + str(job.user))
                    job.status = 'E'
                    job.finish_time=datetime.datetime.today()
                    job.last_update=datetime.datetime.today()
                    job.save()
                #TODO: what about other jobs?
                    
                if job.status == 'X':
                    #If the second stage of condor processing has finished, mark the job as complete
                    job.status='C'
                    job.finish_time=datetime.datetime.today()
                elif job.status != 'E':
                    #Otherwise mark it as waiting for local processing
                    job.status = 'W'
                job.last_update=datetime.datetime.today()
                #job.finish_time=datetime.datetime.today()
                job.save()
            else:
                job.last_update=datetime.datetime.today()
                job.save()
        except Exception, e:
            logging.warning('Error preparing job for condor submission. Job: ' + str(job.id) + ', User: ' + str(job.user))
            logging.warning('Exception: ' + str(e))
    ############

    #Collate the results

    #Get the list of jobs marked as finished, waiting for processing
    waiting = models.Job.objects.filter(status='W')
    for job in waiting:
        logging.debug('Processing results for complete job ' + str(job.id) + ', User: ' + str(job.user))
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
                #Collate the results, and ship them off in a new condor job to be averaged
                #Use this to keep track of the number of jobs we split the task in to
                condor_jobs = models.CondorJob.objects.filter(parent=job)
                cj = model.prepare_ss_process_job(len(condor_jobs), job.runs)
                #Submit the new job to condor
                condor_job_id = condor_submit(cj['spec_file'], username=str(job.user.username), results=True)
                #And store a new condor job in the database
                condor_job = models.CondorJob(parent=job, spec_file=cj['spec_file'], std_output_file=cj['std_output_file'], std_error_file = cj['std_error_file'], log_file=cj['log_file'], job_output=cj['job_output'], queue_status='Q', queue_id=condor_job_id)
                condor_job.save()
                job.status='X' # Set the job status as processing on condor

                job.last_update=datetime.datetime.today()
                job.save()
                
            elif job.job_type == 'PS':
                condor_jobs = models.CondorJob.objects.filter(parent=job)
                no_of_jobs = len(condor_jobs)
                model.process_ps_results(no_of_jobs)
                job.status = 'C'
                job.last_update = datetime.datetime.today()
                job.finish_time = datetime.datetime.today()
                job.save()
            elif job.job_type == 'OR':
                condor_jobs = models.CondorJob.objects.filter(parent=job)
                no_of_jobs = len(condor_jobs)
                #TODO: Do we need to collate any output files?
                model.process_or_results(no_of_jobs)
                job.status = 'C'
                job.last_update = datetime.datetime.today()
                job.finish_time = datetime.datetime.today()
                job.save()
                
            elif job.job_type == 'PR':
                condor_jobs = models.CondorJob.objects.filter(parent=job)
                no_of_jobs = len(condor_jobs)
                model.process_pr_results(no_of_jobs)
                job.status = 'C'
                job.last_update = datetime.datetime.today()
                job.finish_time = datetime.datetime.today()
                job.save()
            elif job.job_type == 'OD':
                condor_jobs = models.CondorJob.objects.filter(parent=job)
                output_files = [cj.job_output for cj in condor_jobs]
                model.process_od_results(output_files)
                job.status = 'C'
                job.last_update = datetime.datetime.today()
                job.finish_time = datetime.datetime.today()
                job.save()
        except Exception, e:
            logging.warning('Error processing results for job ' + str(job.id) + ', User: ' + str(job.user))
            logging.warning('Exception: ' + str(e))
            job.status='E'
            job.finish_time=datetime.datetime.today()
            job.last_update=datetime.datetime.today()
            job.save()

            
            

        
        
    ############
    #Go through completed jobs or jobs with errors, and remove anything older than settings.COMPLETED_JOB_REMOVAL_DAYS
    complete = models.Job.objects.filter(status='C') | models.Job.objects.filter(status='E')
    if settings.COMPLETED_JOB_REMOVAL_DAYS >0:
        for job in complete:
            try:
                if datetime.datetime.today() - job.finish_time > datetime.timedelta(days=settings.COMPLETED_JOB_REMOVAL_DAYS):
                    logging.debug('Removing old job ' + str(job.id) + ', User: ' + str(job.user))
                    job.delete()
            except Exception, e:
                logging.warning('Error removing old job ' + str(job.id) + ', User: ' + str(job.user))
                logging.warning('Exception: ' + str(e))
        
    ########
    #Remove any unconfirmed jobs older than 30 mins
    unconfirmed = models.Job.objects.filter(status='U')

    for job in unconfirmed:
        if datetime.datetime.today() - job.submission_time > datetime.timedelta(minutes=30):
            logging.debug('Removing old unconfirmed job ' + str(job.id) + ', User: ' + str(job.user))
            job.delete()
            
    ##########
    #Remove any jobs marked for deletion
    deletion = models.Job.objects.filter(status='D')
    for job in deletion:
        try:
            #First remove any condor jobs associated with the job
            condor_jobs = models.CondorJob.objects.filter(parent=job)
            for cj in condor_jobs:
                if cj.queue_status == 'Q' or cj.queue_status == 'R' or cj.queue_status == 'I' or cj.queue_status == 'H':
                    condor_rm(cj.queue_id, job.user.username)
                logging.debug('Removing condor job ' + str(cj.queue_id) + ', User: ' + str(job.user))
                cj.delete()
            logging.debug('Removing job marked for deletion: ' + str(job.id) + ', User: ' + str(job.user))    
            job.delete()
        except:
            logging.exception('Error removing marked for deletion job ' + str(job.id))

    ###########
    #Update the condor status
    try:
        condor_status.run()
        logging.debug('Updated Condor status')
    except:
        logging.exception('Error updating the condor status')

if __name__ == '__main__':
    run()
