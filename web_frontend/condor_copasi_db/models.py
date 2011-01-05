from django.db import models
from django.contrib.auth.models import User
from web_frontend import settings
import os

class Job(models.Model):
    JOB_TYPE_CHOICES = (('SO', 'Sensitivity Optimization'),)
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
        ('N', 'New'),
        ('S', 'Submitted'),
        ('F', 'Finished'),
        ('E', 'Error'),
    )
    #The status of the whole job
    status = models.CharField(max_length=1, choices=STATUS_CHOICES)
    #The user-assigned name of the job
    name = models.CharField(max_length=64)
    #The time the job was submitted
    submission_time = models.DateField()
    
    class Meta:
        unique_together = ('user', 'name')
    
    def __unicode__(self):
        return u'%s: %s' % (self.job_type, self.name)
        
    def get_filename(self):
        return os.path.join(settings.USER_FILES_DIR, str(self.user.username), str(self.id), self.model_name)
        
class CondorJob(models.Model):
    #The parent job
    parent = models.ForeignKey(Job)
    #The .job condor specification file
    spec_file = models.CharField(max_length=255)
    #The output file for the job
    output_file = models.CharField(max_length=255)
    #The log file for the job
    log_file = models.CharField(max_length=255)
    #The status of the job in the queue
    QUEUE_CHOICES = (
        ('N', 'Not queued'),
        ('Q', 'Queuing'),
        ('I', 'Idle'),
        ('R', 'Running'),
        ('H', 'Held'),
        ('F', 'Finished'),
    )
    queue_status = models.CharField(max_length=1, choices=QUEUE_CHOICES)
    #The id of the job in the queue. Only set once the job has been queued
    queue_id = models.IntegerField(null=True, unique=True)
    #The amount of computation time in seconds that the condor job took to finish. Note, this does not include any interrupted runs. Will not be set until the condor job finishes.
    run_time = models.FloatField(null=True)
    
    def __unicode__(self):
        return unicode(self.queue_id)
