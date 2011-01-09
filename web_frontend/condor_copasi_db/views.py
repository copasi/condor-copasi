from django.shortcuts import render_to_response, redirect
import datetime, os, shutil
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
import web_frontend.condor_copasi_db.views
from web_frontend import settings
from web_frontend.condor_copasi_db import models
from web_frontend import views as web_frontend_views
from web_frontend.copasi.model import CopasiModel

#Generic function for saving a django UploadedFile to a destination
def handle_uploaded_file(f,destination):
    destination = open(destination, 'wb+')
    for chunk in f.chunks():
        destination.write(chunk)
    destination.close()


@login_required
def tasks(request):
    if request.session.get('message', False):
        message = request.session['message']
        del request.session['message']
    pageTitle = 'Setup new task'
    return render_to_response('tasks/tasks.html', locals(), RequestContext(request))
    
class UploadModelForm(forms.Form):

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(UploadModelForm, self).__init__(*args, **kwargs)

    model_file = forms.FileField()
    job_name = forms.CharField(max_length=64, label='Job Name', help_text='For your reference, enter a name for this job', widget=forms.TextInput(attrs={'size':'40'}))
    
    def clean_job_name(self):
        job_name = self.cleaned_data['job_name']
        user = self.request.user
        try:
            jobs = models.Job.objects.filter(user=user, name=job_name)
            assert len(jobs)==0            
            return self.cleaned_data['job_name']
        except AssertionError:
            raise forms.ValidationError('A job with this name already exists.')
        

@login_required
def sensitivityOptimization(request):
    pageTitle = 'Optimization of Sensitivities'
    #Upload page for a new sensitvity optimization task
    if request.method == 'POST':
        form = UploadModelForm(request.POST, request.FILES, request=request)
        if form.is_valid():
            #file can be accessed by request.FILES['file']
            model_file = request.FILES['model_file']
            #Confirm model is valid by running a number of tests on it, e.g. valid xml, correct tasks set up properly etc.
            try:
                temp_file_path = model_file.temporary_file_path()
                m = CopasiModel(temp_file_path)
                if m.is_valid('SO') != True:
                    file_error = m.is_valid('SO')
                else:
                    #Otherwise add a new job as unconfirmed
                    job = models.Job(job_type='SO', user=request.user, model_name=model_file.name, status='U', name=form.cleaned_data['job_name'], submission_time=datetime.datetime.today())
                    job.save()
                    #And then create a new directory in the settings.USER_FILES dir
                    user_dir=os.path.join(settings.USER_FILES_DIR, str(request.user.username))
                    if not os.path.exists(user_dir):
                        os.mkdir(user_dir)
                    #Make a new unique directory for the file
                    job_dir = os.path.join(user_dir, str(job.id))
                    os.mkdir(job_dir)
                    #And set the new model filename as follows:
                    destination=os.path.join(job_dir, model_file.name)
                    handle_uploaded_file(model_file, destination)
                    return HttpResponseRedirect('/tasks/new/sensitivity_optimization/confirm/' + str(job.id))
            except:
                    file_error = 'The submitted file is not a valid Copasi xml file'
    else:
        form = UploadModelForm()
        file_error = False
        
    return render_to_response('tasks/sensitivity_optimization.html', locals(), RequestContext(request))
    
@login_required
def sensitivityOptimizationConfirm(request, job_id):
    #Prompt the user for confirmation that the job is set up properly
    #List: the optimization method, variables to be optimized etc.
    #On confirm, submit the job to the database
    try:
        job = models.Job.objects.get(user=request.user, id=job_id)
        assert job.status == 'U'
    except AssertionError:
        return web_frontend_views.handle_error(request, 'Error Confirming Job',['The current job has already been confirmed'])
    except:
        return web_frontend_views.handle_error(request, 'Error Confirming Job',['The current job could not be found. Plase try submitting again'])
    if request.method == 'POST':
        #Check if the request was confirmed or cancelled
        if 'confirm_job' in request.POST:
            #Prepare the temporary files for the senstivity optimization task
            model = CopasiModel(job.get_filename())
            model.prepare_sensitvity_optimizations()

            #Mark the job as confirmed
            job.status = 'N'
            job.save()

            #Store a message stating that the job was successfully confirmed
            request.session['message'] = 'Job succesfully sumbitted.'

            return HttpResponseRedirect('/tasks/')
        
        elif 'cancel_job' in request.POST:
            job.delete()
            return HttpResponseRedirect('/tasks/')
            
    pageTitle = 'Confirm Sensitivity Optimization Task'
    try:
        job = models.Job.objects.get(user=request.user, id=job_id)
    #TODO:exception handle here.
    except:
        pass
    
    job_filename = job.get_filename()
    
    model = CopasiModel(job_filename)    
    job_details = (
        ('Job Name', job.name),
        ('File Name', job.model_name),
        ('Model Name', model.get_name()),
        ('Optimization algorithm', model.get_optimization_method()),
        ('Sensitivities Object', model.get_sensitivities_object()),
        
    )
    parameters =  model.get_optimization_parameters(friendly=True)
    return render_to_response('tasks/sensitivity_optimization_confirm.html', locals(), RequestContext(request))
    
    
@login_required
def myAccount(request):
    pageTitle = 'My Account'
    submitted_job_count = len(models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='N'))
    completed_job_count = len(models.Job.objects.filter(user=request.user, status='C'))
    error_count = len(models.Job.objects.filter(user=request.user, status='E'))
    return render_to_response('my_account/my_account.html', locals(), RequestContext(request))
    
    
@login_required
def myAccountRunningJobs(request):
    pageTitle = 'Newly Submitted and Running Jobs'
    submitted_job_count = len(models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='N'))
    completed_job_count = len(models.Job.objects.filter(user=request.user, status='C'))
    error_count = len(models.Job.objects.filter(user=request.user, status='E'))
    
    new_jobs = models.Job.objects.filter(user=request.user, status = 'N')
    submitted_jobs= models.Job.objects.filter(user=request.user, status='S')
    
    jobs=[]
    
    for job in new_jobs:
        jobs.append((job, []))
    
    for job in submitted_jobs:
        condor_jobs = models.CondorJob.objects.filter(parent=job)
        jobs.append((job, condor_jobs))
        
    
    return render_to_response('my_account/running_jobs.html', locals(), RequestContext(request))
    
@login_required
def myAccountCompletedJobs(request):
    pageTitle = 'Completed Jobs'
    submitted_job_count = len(models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='N'))
    completed_job_count = len(models.Job.objects.filter(user=request.user, status='C'))
    error_count = len(models.Job.objects.filter(user=request.user, status='E'))
    
    completed_jobs = models.Job.objects.filter(user=request.user, status='C')
    
    jobs=[]
    
    for job in completed_jobs:
        condor_jobs = models.CondorJob.objects.filter(parent=job)
        jobs.append((job, condor_jobs))
        
    return render_to_response('my_account/completed_jobs.html', locals(), RequestContext(request))

@login_required
def myAccountJobErrors(request):
    pageTitle = 'Job Errors'
    submitted_job_count = len(models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='N'))
    completed_job_count = len(models.Job.objects.filter(user=request.user, status='C'))
    error_count = len(models.Job.objects.filter(user=request.user, status='E'))
    return render_to_response('my_account/errors.html', locals(), RequestContext(request))
    
    
@login_required
def jobDetails(request, job_name):
    pageTitle = 'Job Details'
    submitted_job_count = len(models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='N'))
    completed_job_count = len(models.Job.objects.filter(user=request.user, status='C'))
    error_count = len(models.Job.objects.filter(user=request.user, status='E'))
    try:
        job = models.Job.objects.get(user=request.user, name=job_name)
    except:
        return web_frontend_views.handle_error(request, 'Error Finding Job',['The requested job could not be found'])

    try:
        model = CopasiModel(job.get_filename())
    except:
        return web_frontend_views.handle_error(request, 'Error Loading Model',[])
    running_condor_jobs = len(models.CondorJob.objects.filter(parent=job, queue_status='R'))
    idle_condor_jobs = len(models.CondorJob.objects.filter(parent=job, queue_status='I'))
    finished_condor_jobs = len(models.CondorJob.objects.filter(parent=job, queue_status='F'))
    held_condor_jobs = len(models.CondorJob.objects.filter(parent=job, queue_status='H'))
    total_condor_jobs = running_condor_jobs + idle_condor_jobs + held_condor_jobs + finished_condor_jobs
    
    return render_to_response('my_account/job_details.html', locals(), RequestContext(request))
    
@login_required
def jobOutput(request, job_name):
    submitted_job_count = len(models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='N'))
    completed_job_count = len(models.Job.objects.filter(user=request.user, status='C'))
    error_count = len(models.Job.objects.filter(user=request.user, status='E'))    
    try:
        job = models.Job.objects.get(user=request.user, name=job_name)
    except:
        return web_frontend_views.handle_error(request, 'Error Finding Job',['The requested job could not be found'])
        
    if job.status != 'C':
        return web_frontend_views.handle_error(request, 'Cannot Display Output',['The requested job has not completed yet'])
        
    try:
        model = CopasiModel(job.get_filename())
        if job.job_type == 'SO':
            results = model.get_so_results()
    except:
        return web_frontend_views.handle_error(request, 'Error Finding Job',['The requested job could not be found'])
    pageTitle = 'Job Output: ' + str(job.name)
    return render_to_response('my_account/job_output.html', locals(), RequestContext(request))
    
@login_required
def jobDownload(request, job_name):
    """Generate a tar.gz file of the results directory, and return it"""
    #Check to see if the tar.gz file exists already, if not create it
    try:
        job = models.Job.objects.get(user=request.user, name=job_name)
    except:
        return web_frontend_views.handle_error(request, 'Error Finding Job',['The requested job could not be found'])
    try:
        model = CopasiModel(job.get_filename())
    except:
        return web_frontend_views.handle_error(request, 'Error Loading Model',[])
    filename = os.path.join(model.path, str(job.name) + '.tar.gz')
    if not os.path.isfile(filename) or True:
        import tarfile
        tar = tarfile.open(name=filename, mode='w:gz')
        tar.add(model.path, 'Results')
        tar.close()
    result_file = open(filename, 'r')
    response = HttpResponse(result_file, content_type='application/x-gzip')
    response['Content-Disposition'] = 'attachment; filename=' + job.name + '.tar.gz'
    response['Content-Length'] = os.path.getsize(filename)




    return response
