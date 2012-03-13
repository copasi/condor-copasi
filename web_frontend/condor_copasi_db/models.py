from django.db import models
from django.contrib.auth.models import User
from web_frontend import settings
import os, shutil

class Job(models.Model):
    JOB_TYPE_CHOICES = (
        ('SO', 'Sensitivity Optimization'),
        ('SS', 'Stochastic Simulation'),
        ('PS', 'Scan in Parallel'),
        ('OR', 'Optimization Repeat'),
        ('PR', 'Parameter Estimation Repeat'),
        ('OD', 'Optimization Repeat with Different Algorithms'),
        ('RW', 'Raw mode'),
    )
    #The type of job, e.g. sensitivity optimization
    job_type = models.CharField(max_length=2, choices=JOB_TYPE_CHOICES)
    #The user who submitted the job
    user = models.ForeignKey(User)
    #The directory containing the Copasi model and all associated files
#    directory = models.CharField(max_length=255)
    #The filename of the copasi model
    model_name = models.CharField(max_length=255)
    #The filename of the results file/directory (needed?)
    #results = models.CharField(max_length=255, null=True)
    STATUS_CHOICES = (
        ('U', 'Unconfirmed'),
        ('N', 'New, waiting for Condor submission'),
        ('S', 'Submitted to Condor'),
        ('W', 'Finished, processing data locally'),
        ('X', 'Finished, processing data on condor'),
        ('C', 'Complete'),
        ('E', 'Error'),
    )
    #The status of the whole job
    status = models.CharField(max_length=1, choices=STATUS_CHOICES)
    #The user-assigned name of the job
    name = models.CharField(max_length=64)
    #The time the job was submitted
    submission_time = models.DateTimeField()
    #The time the job was marked as finished
    finish_time=models.DateTimeField(null=True, blank=True)
    #The time information about this job was last updated
    last_update = models.DateTimeField()
    #The number of runs to do. Only required for some jobs
    runs = models.IntegerField(null=True, blank=True)
    
    #Set to true after the model has been (un?)successfully submitted.
    #May seem redundant, but exists to allow multiple unconfirmed jobs with the same name
    submitted = models.NullBooleanField(null=True)
    
    #Added in version 0.2.2 - set option to automatically skip load balancing step, and instead run largest number of parallel jobs possible
    #Update the table condor_copasi_db_job as follows in psql:
    #ALTER TABLE condor_copasi_db_job ADD COLUMN skip_load_balancing boolean;
    skip_load_balancing = models.NullBooleanField(null=True)

    #Added in version 0.3.2 - set option to skip the generation of model files after a parameter estimation or optimization repeat task
    #ALTER TABLE condor_copasi_db_job ADD COLUMN skip_model_generation boolean;
    skip_model_generation = models.NullBooleanField(null=True)


    #Added in version 0.2.2 - set option to flag that a custom report is to be used. At present this only applies to the PR task, since all other tasks can be recreated as a paramter scan
    #Update the table condor_copasi_db_job as follows in psql:
    #ALTER TABLE condor_copasi_db_job ADD COLUMN custom_report boolean;
    custom_report = models.NullBooleanField(null=True)
    
    #String containing custom arguments for the raw mode task
    raw_mode_args = models.CharField(max_length=128, null=True, blank=True)
    
    
    class Meta:
        unique_together = ('user', 'name', 'submitted')
        ordering = ['-last_update']

    def __unicode__(self):
        return u'%s: %s' % (self.job_type, self.name)
    
    def get_path(self):
        return os.path.join(settings.USER_FILES_DIR, str(self.user.username), str(self.id))
    def get_filename(self):
        return os.path.join(settings.USER_FILES_DIR, str(self.user.username), str(self.id), self.model_name)
        
    def delete(self, *args, **kwargs):
        """Override the build-in delete. First remove all child jobs and call call super.delete. finally, remove the directory"""
        try:
            shutil.rmtree(self.get_path())
        except:
            pass
        super(Job, self).delete(*args, **kwargs)
class CondorJob(models.Model):
    #The parent job
    parent = models.ForeignKey(Job)
    #The .job condor specification file
    spec_file = models.CharField(max_length=255)
    #The std output file for the job
    std_output_file = models.CharField(max_length=255)
    #The log file for the job
    log_file = models.CharField(max_length=255)
    #The error file for the job
    std_error_file = models.CharField(max_length=255)
    #The output file created by the job
    job_output = models.CharField(max_length=255)
    #The status of the job in the queue
    QUEUE_CHOICES = (
        ('N', 'Not queued'),
        ('Q', 'Queued'),
        ('I', 'Idle'),
        ('R', 'Running'),
        ('H', 'Held'),
        ('F', 'Finished'),
        ('D', 'Mark for deletion'),
        ('U', 'Unknown'),
        ('E', 'Error'),
    )
    queue_status = models.CharField(max_length=1, choices=QUEUE_CHOICES)
    #The id of the job in the queue. Only set once the job has been queued
    queue_id = models.IntegerField(null=True, unique=True)
    #The amount of computation time in seconds that the condor job took to finish. Note, this does not include any interrupted runs. Will not be set until the condor job finishes.
    run_time = models.FloatField(null=True)
    
    def __unicode__(self):
        return unicode(self.queue_id)
        
    def delete(self, *args, **kwargs):
        """Override the build-in delete."""
        super(CondorJob, self).delete(*args, **kwargs)
