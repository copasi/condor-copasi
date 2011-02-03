from django.shortcuts import render_to_response, redirect
import datetime, os, shutil, re
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

class StochasticUploadModelForm(UploadModelForm):
    runs = forms.IntegerField(label='Repeats', help_text='The number of repeats to perform')        
    
    def clean_runs(self):
        runs = self.cleaned_data['runs']
        try:
            assert runs > 0
            return runs
        except AssertionError:
            raise forms.ValidationError('There must be at least one run')


class ParameterEstimationUploadModelForm(StochasticUploadModelForm):
    parameter_estimation_data = forms.FileField(help_text='Select either a single data file, or if more than one data file is required, upload a .zip file containing multiple data files')

class PlotUpdateForm(forms.Form):
    """Form containing controls to update plots"""
    
    def __init__(self, *args, **kwargs):
        variables = kwargs.pop('variable_choices', None)
        variable_choices = []
        for i in range(len(variables)):
            variable_choices.append((i, variables[i]))

        super(PlotUpdateForm, self).__init__(*args, **kwargs)
        self.fields['variables'].choices = variable_choices
        
    legend = forms.BooleanField(label='Show figure legend', required=False, initial=True)
    stdev = forms.BooleanField(label='Show standard deviations', required=False, initial=True)
    grid = forms.BooleanField(label='Show grid', required=False, initial=True)
    logarithmic = forms.BooleanField(label='Logarithmic scale', required=False)
    variables = forms.MultipleChoiceField(choices=(), widget=forms.CheckboxSelectMultiple(), required=True)

@login_required
def newTask(request, type):
    """Upload page for new tasks"""
    
    if type == 'SO':
        pageTitle = 'Optimization of Sensitivities'
        Form = UploadModelForm
    elif type == 'SS':
        pageTitle = 'Stochastic Simulation'
        Form = StochasticUploadModelForm
    elif type == 'PS':
        pageTitle = 'Scan in Parallel'
        Form = UploadModelForm
    elif type == 'OR':
        pageTitle = 'Optimization Repeat'
        Form = StochasticUploadModelForm
    elif type == 'PR':
        pageTitle = 'Parameter Estimation Repeat'
        #Will need new form
        Form = ParameterEstimationUploadModelForm
    elif type == 'OD':
        pageTitle = 'Optimization Repeat with Different Algorithms'
        #Will need mega new form
        Form = StochasticUploadModelForm
    else:
        return web_frontend_views.handle_error(request, 'Unknown job type')    
    if request.method == 'POST':
        form = Form(request.POST, request.FILES, request=request)
        if form.is_valid():
            #file can be accessed by request.FILES['file']
            model_file = request.FILES['model_file']
            
            #Confirm model is valid by running a number of tests on it, e.g. valid xml, correct tasks set up properly etc.
            try:
                temp_file_path = model_file.temporary_file_path()
                m = CopasiModel(temp_file_path)
                if m.is_valid(type) != True:
                    file_error = m.is_valid(type)
                else:
                    #Otherwise add a new job as unconfirmed
                    if type == 'SS' or type == 'OR' or type=='PR':
                        runs=int(form.cleaned_data['runs'])
                    else:
                        runs = None
                    job = models.Job(job_type=type, user=request.user, model_name=model_file.name, status='U', name=form.cleaned_data['job_name'], submission_time=datetime.datetime.today(), runs = runs, last_update=datetime.datetime.today())
                    job.save()
                    #And then create a new directory in the settings.USER_FILES dir
                    user_dir=os.path.join(settings.USER_FILES_DIR, str(request.user.username))
                    if not os.path.exists(user_dir):
                        os.mkdir(user_dir)
                    #Make a new unique directory for the file
                    job_dir = os.path.join(user_dir, str(job.id))
                    #If the dir already exists, rename it
                    if os.path.exists(job_dir):
                        os.rename(job_dir, job_dir + '.old')
                    os.mkdir(job_dir)
                    #And set the new model filename as follows:
                    destination=os.path.join(job_dir, model_file.name)
                    handle_uploaded_file(model_file, destination)
                    #If this is a parameter estimation job, handle the parameter estimation data
                    if type == 'PR':
                        data_file = request.FILES['parameter_estimation_data']
                        filename = data_file.name
                        data_destination = os.path.join(job_dir, filename)
                        handle_uploaded_file(data_file, data_destination)
                        
                        #Next, attempt to extract the file
                        #If this fails, assume the file is an ASCII data file, not a zip file
                        import zipfile
                        try:
                            z = zipfile.ZipFile(data_destination)
                            #Write the name of each file in the zipfile to data_files_list.txt
                            data_files_list = open(os.path.join(job_dir, 'data_files_list.txt'), 'w')
                            for name in  z.namelist():
                                data_files_list.write(name + '\n')
                            data_files_list.close()
                            
                            z.extractall(job_dir)
                        except zipfile.BadZipfile:
                            #Assume instead that, if not a zip file, the file must be a data file, so leave it be.
                            #Write the name of the data file to data_files_list
                            data_files_list=open(os.path.join(job_dir, 'data_files_list.txt'), 'w')
                            data_files_list.write(filename + '\n')
                            data_files_list.close()
                            
                    return HttpResponseRedirect('/tasks/new/confirm/' + str(job.id))
            except:
                raise
                file_error = 'The submitted file is not a valid Copasi xml file'
                    
    else:
        form = Form()
        file_error = False
        
    return render_to_response('tasks/new_task.html', locals(), RequestContext(request))
    
@login_required
def taskConfirm(request, job_id):
    #Prompt the user for confirmation that the job is set up properly
    #On confirm, submit the job to the database
    try:
        job = models.Job.objects.get(user=request.user, id=job_id)
        assert job.status == 'U'
    except AssertionError:
        return web_frontend_views.handle_error(request, 'Error Confirming Job',['The current job has already been confirmed'])
    except:
        return web_frontend_views.handle_error(request, 'Error Confirming Job',['The current job could not be found. Plase try submitting again'])
        
    type = job.job_type
    if request.method == 'POST':
        #Check if the request was confirmed or cancelled
        if 'confirm_job' in request.POST:
            try:
                #Prepare the temporary files for the senstivity optimization task
                model = CopasiModel(job.get_filename())
                if job.job_type == 'SO':
                    model.prepare_so_task()
                elif job.job_type == 'SS':
                    pass
                    #model.prepare_ss_task(job.runs)

                #Mark the job as confirmed
                job.status = 'N'
                job.last_update = datetime.datetime.today()
                job.save()

                #Store a message stating that the job was successfully confirmed
                request.session['message'] = 'Job succesfully sumbitted.'

                return HttpResponseRedirect('/tasks/')
            except:
                raise
                job.delete()
                return web_frontend_views.handle_error(request, 'An error occured preparing temporary files',['The job was not submitted to condor'])
                
        
        elif 'cancel_job' in request.POST:
            job.delete()
            return HttpResponseRedirect('/tasks/')
            
    pageTitle = 'Confirm Sensitivity Optimization Task'
    
    job_filename = job.get_filename()
    
    model = CopasiModel(job_filename)  
    if job.job_type == 'SO':
        job_details = (
            ('Job Name', job.name),
            ('File Name', job.model_name),
            ('Model Name', model.get_name()),
            ('Optimization algorithm', model.get_optimization_method()),
            ('Sensitivities Object', model.get_sensitivities_object()),    
        )
        parameters =  model.get_optimization_parameters(friendly=True)
        return render_to_response('tasks/sensitivity_optimization_confirm.html', locals(), RequestContext(request))
        
    elif job.job_type == 'SS':
        job_details = (
            ('Job Name', job.name),
            ('File Name', job.model_name),
            ('Model Name', model.get_name()),
            ('Time course algorithm', model.get_timecourse_method()),
            ('Number of runs', job.runs)
        )
        return render_to_response('tasks/task_confirm.html', locals(), RequestContext(request))
    elif job.job_type == 'PS':
        job_details = (
            ('Job Name', job.name),
            ('File Name', job.model_name),
            ('Model Name', model.get_name()),
            ('Total number of scans', model.get_ps_number())
        )
        return render_to_response('tasks/task_confirm.html', locals(), RequestContext(request))
        
    elif job.job_type == 'OR':
        job_details = (
            ('Job Name', job.name),
            ('File Name', job.model_name),
            ('Model Name', model.get_name()),
            ('Number of runs', job.runs),
        )
        return render_to_response('tasks/task_confirm.html', locals(), RequestContext(request))
        
    elif job.job_type == 'PR':
        job_details = (
            ('Job Name', job.name),
            ('File Name', job.model_name),
            ('Model Name', model.get_name()),
            ('Number of Repeats', job.runs),
        )
        return render_to_response('tasks/task_confirm.html', locals(), RequestContext(request))
    
@login_required
def myAccount(request):
    pageTitle = 'My Account'
    submitted_job_count = len(models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='N') | models.Job.objects.filter(user=request.user, status='W') | models.Job.objects.filter(user=request.user, status='X'))
    completed_job_count = len(models.Job.objects.filter(user=request.user, status='C'))
    error_count = len(models.Job.objects.filter(user=request.user, status='E'))
    if request.session.get('message', False):
        message = request.session['message']
        del request.session['message']
    return render_to_response('my_account/my_account.html', locals(), RequestContext(request))
    
    
@login_required
def myAccountRunningJobs(request):
    pageTitle = 'Running Jobs'
    submitted_job_count = len(models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='N') | models.Job.objects.filter(user=request.user, status='W') | models.Job.objects.filter(user=request.user, status='X'))
    completed_job_count = len(models.Job.objects.filter(user=request.user, status='C'))
    error_count = len(models.Job.objects.filter(user=request.user, status='E'))
    
    new_jobs = models.Job.objects.filter(user=request.user, status = 'N')
    submitted_jobs= models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='X')
    processing_jobs = models.Job.objects.filter(user=request.user, status='W')
    
    jobs=[]
    
    for job in new_jobs:
        jobs.append((job, []))
    
    for job in submitted_jobs:
        condor_jobs = models.CondorJob.objects.filter(parent=job)
        jobs.append((job, condor_jobs))
    
    for job in processing_jobs:
        jobs.append((job, []))    
    
    return render_to_response('my_account/running_jobs.html', locals(), RequestContext(request))
    
@login_required
def myAccountCompletedJobs(request):
    pageTitle = 'Completed Jobs'
    submitted_job_count = len(models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='N') | models.Job.objects.filter(user=request.user, status='W') | models.Job.objects.filter(user=request.user, status='X'))
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
    submitted_job_count = len(models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='N') | models.Job.objects.filter(user=request.user, status='W') | models.Job.objects.filter(user=request.user, status='X'))
    completed_job_count = len(models.Job.objects.filter(user=request.user, status='C'))
    error_count = len(models.Job.objects.filter(user=request.user, status='E'))
    
    error_jobs = models.Job.objects.filter(user=request.user, status='E')
    jobs = []
    for job in error_jobs:
        condor_jobs = models.CondorJob.objects.filter(parent=job)
        jobs.append((job, condor_jobs))
        
    return render_to_response('my_account/errors.html', locals(), RequestContext(request))
    
    
@login_required
def jobDetails(request, job_name):
    submitted_job_count = len(models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='N') | models.Job.objects.filter(user=request.user, status='W') | models.Job.objects.filter(user=request.user, status='X'))
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
    pageTitle = 'Job Details: ' + job.name
    running_condor_jobs = len(models.CondorJob.objects.filter(parent=job, queue_status='R'))
    idle_condor_jobs = len(models.CondorJob.objects.filter(parent=job, queue_status='I'))
    finished_condor_jobs = len(models.CondorJob.objects.filter(parent=job, queue_status='F'))
    held_condor_jobs = len(models.CondorJob.objects.filter(parent=job, queue_status='H'))
    total_condor_jobs = running_condor_jobs + idle_condor_jobs + held_condor_jobs + finished_condor_jobs
    

    job_removal_days = settings.COMPLETED_JOB_REMOVAL_DAYS
    if job.finish_time != None:
        job_removal_date = job.finish_time + datetime.timedelta(days=job_removal_days)
    
    return render_to_response('my_account/job_details.html', locals(), RequestContext(request))
    
@login_required
def jobRemove(request, job_name):
    submitted_job_count = len(models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='N') | models.Job.objects.filter(user=request.user, status='W') | models.Job.objects.filter(user=request.user, status='X'))
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
    pageTitle = 'Remove Job: ' + job.name
    running_condor_jobs = len(models.CondorJob.objects.filter(parent=job, queue_status='R'))
    idle_condor_jobs = len(models.CondorJob.objects.filter(parent=job, queue_status='I'))
    finished_condor_jobs = len(models.CondorJob.objects.filter(parent=job, queue_status='F'))
    held_condor_jobs = len(models.CondorJob.objects.filter(parent=job, queue_status='H'))
    total_condor_jobs = running_condor_jobs + idle_condor_jobs + held_condor_jobs + finished_condor_jobs
    

    if request.method == 'POST':
        if 'remove_job' in request.POST:
            try:
                job_name = job.name
                job.delete()
                request.session['message'] = 'Job ' + str(job_name) + ' removed.'
                return HttpResponseRedirect('/my_account/')
            except:
                return web_frontend_views.handle_error(request, 'Error Removing Job',[])
        else:
            return HttpResponseRedirect('/my_account/jobs/details/' + str(job.name))
        
    return render_to_response('my_account/job_remove.html', locals(), RequestContext(request))
    
    
@login_required
def jobOutput(request, job_name):
    submitted_job_count = len(models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='N') | models.Job.objects.filter(user=request.user, status='W') | models.Job.objects.filter(user=request.user, status='X'))
    completed_job_count = len(models.Job.objects.filter(user=request.user, status='C'))
    error_count = len(models.Job.objects.filter(user=request.user, status='E'))
    job_remove_removal_days = settings.COMPLETED_JOB_REMOVAL_DAYS
    
    try:
        job = models.Job.objects.get(user=request.user, name=job_name)
    except:
        return web_frontend_views.handle_error(request, 'Error Finding Job',['The requested job could not be found'])
        
    if job.status != 'C':
        return web_frontend_views.handle_error(request, 'Cannot Display Output',['The requested job has not completed yet'])
        
    try:
        model = CopasiModel(job.get_filename())
    except:
        return web_frontend_views.handle_error(request, 'Error Finding Job',['The requested job could not be found'])
    
    if job.job_type == 'SO':
        results = model.get_so_results()
        
    #If displaying a plot, check for GET options
    if job.job_type == 'SS':
        try:
            variable_choices = model.get_variables(pretty=True)
        except:
            raise
            return web_frontend_views.handle_error(request, 'Error Reading Results',['An error occured while trying to processs the job output'])
        
        #If the variables GET field hasn't been set, preset it to all variables
        
        try:
            assert request.GET.get('custom') == 'true'
            form=PlotUpdateForm(request.GET, variable_choices=variable_choices)
        except:
            form=PlotUpdateForm(variable_choices=variable_choices, initial={'variables' : range(len(variable_choices))})
        
        if form.is_valid():
            variables = map(int,form.cleaned_data['variables'])
            log = form.cleaned_data['logarithmic']
            stdev = form.cleaned_data['stdev']
            legend = form.cleaned_data['legend']
            grid = form.cleaned_data['grid']
        else:
            variables=range(len(variable_choices))
            log=False
            stdev = True
            legend=True
            grid=True
            
        #construct the string to load the image file
        img_string = '?variables=' + str(variables).strip('[').rstrip(']').replace(' ', '')
        if log:
            img_string += '&log=true'
        if stdev:
            img_string += '&stdev=true'
        if legend:
            img_string += '&legend=true'
        if grid:
            img_string += '&grid=true'
            
    pageTitle = 'Job Output: ' + str(job.name)
    return render_to_response('my_account/job_output.html', locals(), RequestContext(request))
  
  
@login_required
def jobResultDownload(request, job_name):
    """Return the file containing the job results file"""
    try:
        job = models.Job.objects.get(user=request.user, name=job_name)
    except:
        return web_frontend_views.handle_error(request, 'Error Finding Job',['The requested job could not be found'])
    try:
        model = CopasiModel(job.get_filename())
    except:
        return web_frontend_views.handle_error(request, 'Error Loading Model',[])
    filename = os.path.join(model.path, 'results.txt')
    if not os.path.isfile(filename):
        return web_frontend_views.handle_error(request, 'Cannot Return Output',['There was an internal error processing the results file'])
    result_file = open(filename, 'r')
    response = HttpResponse(result_file, content_type='text/tab-separated-values')
    response['Content-Disposition'] = 'attachment; filename=' + job.name + '_results.txt'
    response['Content-Length'] = os.path.getsize(filename)
    
    return response
    
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
        tar.add(model.path, job.name)
        tar.close()
    result_file = open(filename, 'r')
    response = HttpResponse(result_file, content_type='application/x-gzip')
    response['Content-Disposition'] = 'attachment; filename=' + job.name + '.tar.gz'
    response['Content-Length'] = os.path.getsize(filename)

    return response
    
@login_required
def ss_plot(request, job_name):
    """Return the plot image for the results from a stochastic simulation"""
    import numpy as np
    try:
        job = models.Job.objects.get(user=request.user, name=job_name)
    except:
        return web_frontend_views.handle_error(request, 'Error Finding Job',['The requested job could not be found'])
    try:
        model = CopasiModel(job.get_filename())
    except:
        return web_frontend_views.handle_error(request, 'Error Loading Model',[])
    
    try:
        assert job.status == 'C'
        results = np.loadtxt(os.path.join(job.get_path(), 'results.txt'), skiprows=1, delimiter='\t', unpack=True)
        variable_list = model.get_variables(pretty=True)
        
    except:
        raise
        return web_frontend_views.handle_error(request, 'Error reading results',['The requested job output could not be read'])
    try:
        import matplotlib
        matplotlib.use('Agg') #Use this so matplotlib can be used on a headless server. Otherwise requires DISPLAY env variable to be set.
        import matplotlib.pyplot as plt

        #Look at the GET data to see what chart options have been set:
        get_variables = request.GET.get('variables')
        log = request.GET.get('log', 'false')
        stdev=request.GET.get('stdev', 'false')
        legend = request.GET.get('legend', 'false')
        grid = request.GET.get('grid', 'false')
        
        #Check to see if we should return as an attachment in .png or .svg or .eps
        download_png = 'download_png' in request.POST
        download_svg = 'download_svg' in request.POST
        download_eps = 'download_eps' in request.POST
        try:
            variables = map(int, get_variables.split(','))
            assert max(variables) < ((len(results)-1)/2)
        except:
            variables = range((len(results) - 1)/2)
        
        matplotlib.rc('font', size=8)
        fig = plt.figure()
        plt.title(job.name + ' (' + str(job.runs) + ' repeats)', fontsize=12, fontweight='bold')
        plt.xlabel('Time')
        
        color_list = ['red', 'blue', 'green', 'cyan', 'magenta', 'yellow', 'black']
#        import random
#        random.shuffle(color_list)
        #Regex for extracting the variable name from the results file.
        label_str = r'(?P<name>.+)\[.+\] (mean|stdev)$'
        label_re = re.compile(label_str)
        
        
        j=0 #used to keep cycle through colors in order
        for i in variables:
            #Go through each result and plot mean and stdev against time
            label = variable_list[i]
            

            #Plot the means
            plt.plot(results[0], results[2*i + 1], lw=2, label=label, color=color_list[j%7])
            
            if stdev == 'true':
                #Calculate stdev upper and lower bounds (mean +/- stdev) and shade the stdevs if requested
                upper_bound = results[2*i + 1] + results[2*i+2]
                lower_bound = results[2*i + 1] - results[2 * i +2]
                plt.fill_between(results[0], upper_bound, lower_bound, alpha=0.2, color=color_list[j%7])
            j+=1
        #Set a logarithmic scale if requested
        if log != 'false':
            plt.yscale('log')
        if legend != 'false':
            plt.legend(loc=0, )
        if grid != 'false':
            plt.grid(True)
            
        if download_png:    
            response = HttpResponse(mimetype='image/png', content_type='image/png')
            fig.savefig(response, format='png', transparent=False, dpi=120)
            response['Content-Disposition'] = 'attachment; filename=' + job.name + '.png'
        elif download_svg:
            response = HttpResponse(mimetype='image/svg', content_type='image/svg')
            fig.savefig(response, format='svg', transparent=False, dpi=120)
            response['Content-Disposition'] = 'attachment; filename=' + job.name + '.svg'
        elif download_eps:
            response = HttpResponse(mimetype='image/eps', content_type='image/eps')
            fig.savefig(response, format='eps', transparent=False, dpi=120)
            response['Content-Disposition'] = 'attachment; filename=' + job.name + '.eps'
        else:    
            response = HttpResponse(mimetype='image/png', content_type='image/png')
            fig.savefig(response, format='png', transparent=False, dpi=120)
        return response
    except:
        raise

