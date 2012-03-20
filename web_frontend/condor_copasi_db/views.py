from django.shortcuts import render_to_response, redirect
import datetime, os, shutil, re, math
from django import forms
from django.db import IntegrityError
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.contrib.admin import widgets                                       
import web_frontend.condor_copasi_db.views
from web_frontend import settings, condor_log, motionchart
from web_frontend.condor_copasi_db import models
from web_frontend import views as web_frontend_views
from web_frontend.copasi.model import CopasiModel
from django.core.urlresolvers import reverse
from django.core.files.uploadedfile import TemporaryUploadedFile
from web_frontend.condor_copasi_db.web_forms import *
from math import cos, pi, sin

os.environ['HOME'] = settings.USER_FILES_DIR #This needs to be set to a writable directory
import matplotlib
matplotlib.use('Agg') #Use this so matplotlib can be used on a headless server. Otherwise requires DISPLAY env variable to be set.
import matplotlib.pyplot as plt
from matplotlib.pyplot import annotate




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
    

@login_required
def change_password(request):
    """Displays a form to allow the user to change their password."""
    user = request.user
    pageTitle = 'Change Password'
    submitted_job_count = len(models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='N') | models.Job.objects.filter(user=request.user, status='W') | models.Job.objects.filter(user=request.user, status='X'))
    completed_job_count = len(models.Job.objects.filter(user=request.user, status='C'))
    error_count = len(models.Job.objects.filter(user=request.user, status='E'))
    
    new_jobs = models.Job.objects.filter(user=request.user, status = 'N')
    submitted_jobs= models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='X')
    processing_jobs = models.Job.objects.filter(user=request.user, status='W')
    if request.method == 'POST':
        form = ChangePasswordForm(request.POST, request=request)
        if form.is_valid():
            user.set_password(form.cleaned_data['new_password_1'])
            user.save()
            request.session['message'] = 'Password successfully changed'
            return HttpResponseRedirect(reverse('my_account'))
    else:
        form = ChangePasswordForm(request=request)
    return render_to_response('my_account/change_password.html', locals(), context_instance=RequestContext(request))


@login_required
def newTask(request, type):
    """Upload page for new tasks"""
    
    if type == 'SO':
        pageTitle = 'Sensitivity Optimization / Global Sensitivity Analysis' 
        Form = SOUploadModelForm
    elif type == 'SS':
        pageTitle = 'Stochastic Simulation'
        Form = StochasticUploadModelForm
    elif type == 'PS':
        pageTitle = 'Scan in Parallel'
        Form = ParallelScanForm
    elif type == 'OR':
        pageTitle = 'Optimization Repeat'
        Form = OptimizationRepeatForm
    elif type == 'PR':
        pageTitle = 'Parameter Estimation Repeat'
        #Will need new form
        Form = ParameterEstimationUploadModelForm
        
    elif type == 'RW':
        pageTitle = 'Raw Mode'
        Form = RawUploadModelForm
    elif type == 'OD':
        pageTitle = 'Optimization Repeat with Different Algorithms'
        #Will need mega new form
        Form = ODUploadModelForm
        
        #Load the forms for the various different optimization algorithms
        algorithms = []
        #Store each algorithm as a dict, containing the form, prefix and algorithm name
        algorithms.append({
            'form': CurrentSolutionStatisticsForm,
            'prefix': 'current_solution_statistics',
            'name': 'Current Solution Statistics',
            'form_instance': None,
        })
        
        algorithms.append({
            'form': GeneticAlgorithmForm,
            'prefix': 'genetic_algorithm',
            'name': 'Genetic Algorithm',
            'form_instance': None,
        })
        algorithms.append({
            'form': GeneticAlgorithmSRForm,
            'prefix': 'genetic_algorithm_sr',
            'name': 'Genetic Algorithm SR',
            'form_instance': None,
        })
        algorithms.append({
            'form': HookeAndJeevesForm,
            'prefix': 'hooke_and_jeeves',
            'name': 'Hooke & Jeeves',
            'form_instance': None,
        })
        algorithms.append({
            'form': LevenbergMarquardtForm,
            'prefix': 'levenberg_marquardt',
            'name': 'Levenberg-Marquardt',
            'form_instance': None,
        })
        algorithms.append({
            'form': EvolutionaryProgrammingForm,
            'prefix': 'evolutionary_programming',
            'name': 'Evolutionary Programming',
            'form_instance': None,
        })
        algorithms.append({
            'form': RandomSearchForm,
            'prefix': 'random_search',
            'name': 'Random Search',
            'form_instance': None,
        })
        algorithms.append({
            'form': NelderMeadForm,
            'prefix': 'nelder_mead',
            'name': 'Nelder-Mead',
            'form_instance': None,
        })
        algorithms.append({
            'form': ParticleSwarmForm,
            'prefix': 'particle_swarm',
            'name': 'Particle Swarm',
            'form_instance': None,
        })
        algorithms.append({
            'form': PraxisForm,
            'prefix': 'praxis',
            'name': 'Praxis',
            'form_instance': None,
        })
        algorithms.append({
            'form': TruncatedNewtonForm,
            'prefix': 'truncated_newton',
            'name': 'Truncated Newton',
            'form_instance': None,
        })
        algorithms.append({
            'form': SimulatedAnnealingForm,
            'prefix': 'simulated_annealing',
            'name': 'Simulated Annealing',
            'form_instance': None,
        })
        algorithms.append({
            'form': EvolutionStrategyForm,
            'prefix': 'evolution_strategy',
            'name': 'Evolution Strategy',
            'form_instance': None,
        })
        algorithms.append({
            'form': SteepestDescentForm,
            'prefix': 'steepest_descent',
            'name': 'Steepest Descent',
            'form_instance': None,
        })
    else:
        return web_frontend_views.handle_error(request, 'Unknown job type')    
        
    try:
        #For the rank field, if we can, then get the most recently submitted job
        last_job = models.Job.objects.filter(user=request.user).latest('id')
        last_job_rank = last_job.rank
        #assert last_job_rank != None
        last_job_id = last_job.id
    except:
        last_job_rank = False
        last_job_id = 'not found'
        
    if request.method == 'POST':
        form = Form(request.POST, request.FILES, request=request, last_rank=last_job_rank)

        if type == 'OD':
            #Load instances of all forms
            for algorithm in algorithms:
                algorithm['form_instance'] = algorithm['form'](request.POST, request.FILES, prefix=algorithm['prefix'])
                
            all_forms_valid = True
            algorithms_selected = 0
            for algorithm in algorithms:
                if not algorithm['form_instance'].is_valid():
                    all_form_valid = False
                if algorithm['form_instance'].cleaned_data['enabled'] == True:
                    algorithms_selected += 1
                    
            if algorithms_selected == 0:
                all_forms_valid = False
                error = 'You must select at least one algorithm'
        else:
            all_forms_valid = True
            
        if form.is_valid() and all_forms_valid:
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
                    #Extract the information we need from each job
                    
                    if type == 'SO':
                        name = form.cleaned_data['job_name']
                        runs = None
                        skip_load_balancing = None
                        skip_model_generation = None
                        custom_report = None
                        raw_mode_args = None
                        rank = form.cleaned_data['rank']
                        
                    elif type == 'SS':
                        name = form.cleaned_data['job_name']
                        runs = int(form.cleaned_data['runs'])
                        skip_load_balancing = form.cleaned_data['skip_load_balancing']
                        skip_model_generation = None
                        custom_report = None
                        raw_mode_args = None
                        rank = form.cleaned_data['rank']
                        
                    elif type == 'PS':
                        name = form.cleaned_data['job_name']
                        runs = None
                        skip_load_balancing = form.cleaned_data['skip_load_balancing']
                        skip_model_generation = None
                        custom_report = None
                        raw_mode_args = None
                        rank = form.cleaned_data['rank']    
                                            
                    elif type == 'OR':
                        name = form.cleaned_data['job_name']
                        runs = int(form.cleaned_data['runs'])
                        skip_load_balancing = form.cleaned_data['skip_load_balancing']
                        skip_model_generation = None
                        custom_report = None
                        raw_mode_args = None
                        rank = form.cleaned_data['rank']
                                            
                    elif type == 'PR':
                        name = form.cleaned_data['job_name']
                        runs = int(form.cleaned_data['runs'])
                        skip_load_balancing = form.cleaned_data['skip_load_balancing']
                        skip_model_generation = form.cleaned_data['skip_model_generation']
                        custom_report = form.cleaned_data['custom_report']
                        raw_mode_args = None
                        rank = form.cleaned_data['rank']
                                            
                    elif type == 'RW':
                        name = form.cleaned_data['job_name']
                        runs = int(form.cleaned_data['runs'])
                        skip_load_balancing = None
                        skip_model_generation = None
                        custom_report = None
                        raw_mode_args = form.cleaned_data['raw_mode_args']
                        rank = form.cleaned_data['rank']
                        
                    elif type == 'OD':
                        name = form.cleaned_data['job_name']
                        runs = algorithms_selected
                        skip_load_balancing = None
                        skip_model_generation = None
                        custom_report = None
                        raw_mode_args = None                      
                        rank = form.cleaned_data['rank']

                    #Create the job
                    job = models.Job(job_type=type, user=request.user, model_name=model_file.name, status='U', name=name, submission_time=datetime.datetime.today(), runs = runs, last_update=datetime.datetime.today(), skip_load_balancing=skip_load_balancing, custom_report=custom_report, raw_mode_args=raw_mode_args, skip_model_generation=skip_model_generation, rank=rank, condor_jobs=0)

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
                    #Or, also do this if this is a raw job, and a data file has been uploaded
                    if type == 'PR' or (type=='RW' and isinstance(form.cleaned_data['parameter_estimation_data'], TemporaryUploadedFile)):
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
                        
                    #Otherwise, if this is a raw job, create an empty file called data_files_list.txt
                    
                    elif type=='RW' and not isinstance(form.cleaned_data['parameter_estimation_data'], TemporaryUploadedFile):
                        data_files_list=open(os.path.join(job_dir, 'data_files_list.txt'), 'w')
                        data_files_list.write('') #Not sure if this line is needed, but can't hurt
                        data_files_list.close()
                        
                        
                    elif type == 'OD':
                        #If this is the optimization with different algorithms task, then prepare the relevant files now, while we have the algorithm information available
                        model = CopasiModel(destination)
                        model.prepare_od_jobs(algorithms)
                            
                    return HttpResponseRedirect(reverse('confirm_task', args=[str(job.id)]))
            except:
                raise
                file_error = 'The submitted file is not a valid COPASI xml file'
                    
    else:
        form = Form(last_rank=last_job_rank)
        file_error = False
        
        if type == 'OD':
            #Initialize form instances for each algorithm
            for algorithm in algorithms:
                algorithm['form_instance'] = algorithm['form'](prefix=algorithm['prefix'])
        
    return render_to_response('tasks/new_task.html', locals(), RequestContext(request))
    
@login_required
def taskConfirm(request, job_id):
    #Prompt the user for confirmation that the job is set up properly
    #On confirm, submit the job to the database
    try:
        job = models.Job.objects.get(user=request.user, id=job_id, status='U')
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

                #Mark the job as confirmed
                job.status = 'N'
                #And submitted
                job.submitted=True
                job.last_update = datetime.datetime.today()
                job.save()

                #Store a message stating that the job was successfully confirmed
                request.session['message'] = 'Job succesfully sumbitted.'

                return HttpResponseRedirect(reverse('tasks_home'))
            except IntegrityError:
                job.delete()
                return web_frontend_views.handle_error(request, 'There was a problem submitting the job.',['The job was not submitted to condor', 'Please try again'])
            except:
                job.delete()
                return web_frontend_views.handle_error(request, 'An error occured preparing temporary files',['The job was not submitted to condor'])
                
        
        elif 'cancel_job' in request.POST:
            job.delete()
            return HttpResponseRedirect(reverse('tasks_home'))

    
    job_filename = job.get_filename()
    
    model = CopasiModel(job_filename)  
    if job.job_type == 'SO':
        pageTitle = 'Confirm Sensitivity Optimization Task'
        job_details = (
            ('Job Name', job.name),
            ('File Name', job.model_name),
            ('Model Name', model.get_name()),
            ('Optimization algorithm', model.get_optimization_method()),
            ('Sensitivities Object', model.get_sensitivities_object()),    
            ('Job rank', job.rank),
        )
        parameters =  model.get_optimization_parameters(friendly=True)
        return render_to_response('tasks/sensitivity_optimization_confirm.html', locals(), RequestContext(request))
        
    elif job.job_type == 'SS':
        pageTitle = 'Confirm Stochastic Simulation Task'
        job_details = (
            ('Job Name', job.name),
            ('File Name', job.model_name),
            ('Model Name', model.get_name()),
            ('Time course algorithm', model.get_timecourse_method()),
            ('Number of runs', job.runs),
            ('Job rank', job.rank),
        )
        return render_to_response('tasks/task_confirm.html', locals(), RequestContext(request))
    elif job.job_type == 'PS':
        pageTitle = 'Confirm Parallel Scan Task'
        job_details = (
            ('Job Name', job.name),
            ('File Name', job.model_name),
            ('Model Name', model.get_name()),
            ('Total number of scans', model.get_ps_number()),
            ('Job rank', job.rank),
        )
        return render_to_response('tasks/task_confirm.html', locals(), RequestContext(request))
        
    elif job.job_type == 'OR':
        pageTitle = 'Confirm Optimization Repeat Task'
        job_details = (
            ('Job Name', job.name),
            ('File Name', job.model_name),
            ('Model Name', model.get_name()),
            ('Number of runs', job.runs),
            ('Job rank', job.rank),
        )
        return render_to_response('tasks/task_confirm.html', locals(), RequestContext(request))
        
    elif job.job_type == 'PR':
        pageTitle = 'Confirm Parameter Estimation Repeat Task'
        job_details = (
            ('Job Name', job.name),
            ('File Name', job.model_name),
            ('Model Name', model.get_name()),
            ('Number of Repeats', job.runs),
            ('Job rank', job.rank),
        )
        return render_to_response('tasks/task_confirm.html', locals(), RequestContext(request))
    elif job.job_type == 'OD':
        pageTitle = 'Confirm Optimization Repeat with Different Algorithms Task'
        job_details = (
            ('Job Name', job.name),
            ('File Name', job.model_name),
            ('Model Name', model.get_name()),
            ('Number of Algorithms Selected', job.runs),
            ('Job rank', job.rank),
        )
        return render_to_response('tasks/task_confirm.html', locals(), RequestContext(request))
        
    elif job.job_type == 'RW':
        pageTitle = 'Confirm Optimization Repeat with Different Algorithms Task'
        job_details = (
            ('Job Name', job.name),
            ('File Name', job.model_name),
            ('Model Name', model.get_name()),
            ('Arguments', job.raw_mode_args),
            ('Job rank', job.rank),
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
        job = models.Job.objects.get(user=request.user, name=job_name, submitted=True)
    except:
        return web_frontend_views.handle_error(request, 'Error Finding Job',['The requested job could not be found'])

    try:
        model = CopasiModel(job.get_filename())
    except:
        raise
        return web_frontend_views.handle_error(request, 'Error Loading Model',[])
    pageTitle = 'Job Details: ' + job.name
    running_condor_jobs = len(models.CondorJob.objects.filter(parent=job, queue_status='R'))
    idle_condor_jobs = len(models.CondorJob.objects.filter(parent=job, queue_status='I'))
    finished_condor_jobs = len(models.CondorJob.objects.filter(parent=job, queue_status='F'))
    held_condor_jobs = len(models.CondorJob.objects.filter(parent=job, queue_status='H'))
    total_condor_jobs = running_condor_jobs + idle_condor_jobs + held_condor_jobs + finished_condor_jobs
    
    rank = job.rank

    job_removal_days = settings.COMPLETED_JOB_REMOVAL_DAYS
    if job.finish_time != None:
        job_removal_date = job.finish_time + datetime.timedelta(days=job_removal_days)

        #Get the new calculated cpu time from the database
        if job.run_time != None:
            total_cpu_time = datetime.timedelta(job.run_time)
        else:
            total_cpu_time = datetime.timedelta(0)
    
    #If job type is 'PR' then use local variable auto_model_download
    auto_model_download = (job.skip_model_generation != True) #Should be true when field is True or Null
    return render_to_response('my_account/job_details.html', locals(), RequestContext(request))
    
@login_required
def jobRemove(request, job_name):
    submitted_job_count = len(models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='N') | models.Job.objects.filter(user=request.user, status='W') | models.Job.objects.filter(user=request.user, status='X'))
    completed_job_count = len(models.Job.objects.filter(user=request.user, status='C'))
    error_count = len(models.Job.objects.filter(user=request.user, status='E'))
    try:
        job = models.Job.objects.get(user=request.user, name=job_name, submitted=True)
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
                job.status = 'D'
                job.save()
                request.session['message'] = 'Job ' + str(job_name) + ' marked for removal.'
                return HttpResponseRedirect(reverse('my_account'))
            except:
                return web_frontend_views.handle_error(request, 'Error Removing Job',[])
        else:
            return HttpResponseRedirect(reverse('job_details', args=[str(job.name)]))
        
    return render_to_response('my_account/job_remove.html', locals(), RequestContext(request))
    
    
@login_required
def jobOutput(request, job_name):
    submitted_job_count = len(models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='N') | models.Job.objects.filter(user=request.user, status='W') | models.Job.objects.filter(user=request.user, status='X'))
    completed_job_count = len(models.Job.objects.filter(user=request.user, status='C'))
    error_count = len(models.Job.objects.filter(user=request.user, status='E'))
    job_remove_removal_days = settings.COMPLETED_JOB_REMOVAL_DAYS
    
    try:
        job = models.Job.objects.get(user=request.user, name=job_name, submitted=True)
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
        for i in range(len(results)):
            #Calculate url for progress plot for min and max
            min_param_index = i*2
            max_param_index = (i*2) + 1
            results[i]['url_min'] = reverse('so_progress_page', args=[job.name]) + '?custom=true&variables='+str(min_param_index)
            results[i]['url_max'] = reverse('so_progress_page', args=[job.name]) + '?custom=true&variables='+str(max_param_index)
            results[i]['url_min_max'] = reverse('so_progress_page', args=[job.name]) + '?custom=true&variables='+str(min_param_index)+'&variables='+str(max_param_index)
        all_plots_url=reverse('so_progress_page', args=[job.name])
        
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
    
    elif job.job_type == 'OR':
        try:
            output = model.get_or_best_value()
            best_value = output[0][1]
            parameters = output[1:]
        except:
            return web_frontend_views.handle_error(request, 'Error Reading Results',['An error occured while trying to processs the job output. You may be able to recover any raw, unprocessed results by downloading the job directory.'])
    elif job.job_type == 'PR':
        try:
            output = model.get_pr_best_value()
            best_value = output[0][1]
            parameters = output[3:]
        except:
            return web_frontend_views.handle_error(request, 'Error Reading Results',['An error occured while trying to processs the job output. You may be able to recover any raw, unprocessed results by downloading the job directory.'])
        
    elif job.job_type == 'OD':
        try:
            output = model.get_od_results()
            best_value = output[1][1]
        except:
            return web_frontend_views.handle_error(request, 'Error Reading Results',['An error occured while trying to processs the job output. You may be able to recover any raw, unprocessed results by downloading the job directory.'])
            
            
    pageTitle = 'Job Output: ' + str(job.name)
    return render_to_response('my_account/job_output.html', locals(), RequestContext(request))
  
  
@login_required
def jobResultDownload(request, job_name):
    """Return the file containing the job results file"""
    try:
        job = models.Job.objects.get(user=request.user, name=job_name, submitted=True)
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
    """Generate a tar.bz2 file of the results directory, and return it"""
    #Check to see if the tar.bz2 file exists already, if not create it
    try:
        job = models.Job.objects.get(user=request.user, name=job_name, submitted=True)
    except:
        return web_frontend_views.handle_error(request, 'Error Finding Job',['The requested job could not be found'])
    try:
        model = CopasiModel(job.get_filename())
    except:
        return web_frontend_views.handle_error(request, 'Error Loading Model',[])
    filename = os.path.join(model.path, str(job.name) + '.tar.bz2')
    if not os.path.isfile(filename):
        import tarfile
        tar = tarfile.open(name=filename, mode='w:bz2')
        tar.add(model.path, job.name)
        tar.close()

    result_file = open(filename, 'r')
    response = HttpResponse(result_file, content_type='application/x-bzip2')
    response['Content-Disposition'] = 'attachment; filename=' + job.name + '.tar.bz2'
    response['Content-Length'] = os.path.getsize(filename)

    return response
    
@login_required
def prModelDownload(request, job_name):
    """Return the model containing the best result values for the PR task"""
    try:
        job = models.Job.objects.get(user=request.user, name=job_name, submitted=True)
    except:
        return web_frontend_views.handle_error(request, 'Error Finding Job',['The requested job could not be found'])
    try:
        model = CopasiModel(job.get_filename())
    except:
        return web_frontend_views.handle_error(request, 'Error Loading Model',[])
    filename = os.path.join(model.path, 'best_values.cps')
    if not os.path.isfile(filename):
        return web_frontend_views.handle_error(request, 'Cannot Return Output',['There was an internal error processing the model file'])
    result_file = open(filename, 'r')
    response = HttpResponse(result_file, content_type='text/tab-separated-values')
    response['Content-Disposition'] = 'attachment; filename=' + job.name + '_best_values.cps'
    response['Content-Length'] = os.path.getsize(filename)
    
    return response
    
    
@login_required
def ss_plot(request, job_name):
    """Return the plot image for the results from a stochastic simulation"""
    import numpy as np
    try:
        job = models.Job.objects.get(user=request.user, name=job_name, submitted=True)
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

@login_required
def so_progress_plot(request, job_name):
    """Return the plot image for the progress of a single sensitivity optimization parameter"""

    try:
        job = models.Job.objects.get(user=request.user, name=job_name, submitted=True)
    except:
        return web_frontend_views.handle_error(request, 'Error Finding Job',['The requested job could not be found'])
    try:
        model = CopasiModel(job.get_filename())
    except:
        return web_frontend_views.handle_error(request, 'Error Loading Model',[])
    
    try:
        assert job.status == 'C' and job.job_type=='SO'
        results = model.get_so_results()
        #Get parameter names, min and max
        variable_choices = []
        for result in results:
            variable_choices.append(result['name'] + '_min')
            variable_choices.append(result['name'] + '_max')

    except:
        raise
        return web_frontend_views.handle_error(request, 'Error reading results',['The requested job output could not be read'])
    try:
        #Look at the GET data to see what chart options have been set:
        get_variables = request.GET.get('variables')
        log = request.GET.get('log', 'false')

        legend = request.GET.get('legend', 'false')
        grid = request.GET.get('grid', 'false')
        
        #Check to see if we should return as an attachment in .png or .svg or .eps
        download_png = 'download_png' in request.POST
        download_svg = 'download_svg' in request.POST
        download_eps = 'download_eps' in request.POST
        try:
            variables = map(int, get_variables.split(','))
            assert max(variables) < len(variable_choices)
        except:
            raise
            variables = range(len(variable_choices))
        
        matplotlib.rc('font', size=8)
        fig = plt.figure()
#        plt.title(job.name + ' (' + str(job.runs) + ' repeats)', fontsize=12, fontweight='bold')
        plt.xlabel('Iterations')
        plt.ylabel('Optimization value')
        
        color_list = ['red', 'blue', 'green', 'cyan', 'magenta', 'yellow', 'black']        
        
        j=0 #used to keep cycle through colors in order
        for i in variables:
            #Go through each result and plot the progress
            label = variable_choices[i]
            
            #Check if we're plotting a min or a max. Min will be all even numbers, max all odd
            file_index = int(math.floor(i/2))
            if i%2 == 0:
                filename = os.path.join(job.get_path(), 'min_' + str(file_index) + '.txt')
            else:
                filename = os.path.join(job.get_path(), 'max_' + str(file_index) + '.txt')
            all_evals=[]
            all_values=[]
            linenumber=0
            #Go through line by line; lines repeat every 4th line
            for line in open(filename, 'r'):
                if linenumber%4 == 0:
                    pass
                elif linenumber%4 == 1:
                    evals = int(line.split()[2]) # Extract number from 'Evals = n'
                    all_evals.append(evals)
                elif linenumber%4 == 2:
                    pass
                    #time = float(line.split()[2])
                elif linenumber%4 == 3:
                    value = float(line)
                    all_values.append(value)

                linenumber += 1
            #Plot the progress
            plt.plot(all_evals, all_values, lw=1, label=label, color=color_list[j%len(color_list)])
            
            j+=1
        #Set a logarithmic scale if requested
        if log != 'false':
            plt.yscale('log')
        if legend != 'false':
            plt.legend(loc=0, )
        if grid != 'false':
            plt.grid(True)
            
        plt.show()
            
            
            
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
        
@login_required
def so_progress_page(request, job_name):
    """Page for displaying a plot containing so optimization progress"""
    submitted_job_count = len(models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='N') | models.Job.objects.filter(user=request.user, status='W') | models.Job.objects.filter(user=request.user, status='X'))
    completed_job_count = len(models.Job.objects.filter(user=request.user, status='C'))
    error_count = len(models.Job.objects.filter(user=request.user, status='E'))
    job_remove_removal_days = settings.COMPLETED_JOB_REMOVAL_DAYS
    
    try:
        job = models.Job.objects.get(user=request.user, name=job_name, submitted=True)
    except:
        return web_frontend_views.handle_error(request, 'Error Finding Job',['The requested job could not be found'])
        
    if job.status != 'C':
        return web_frontend_views.handle_error(request, 'Cannot Display Output',['The requested job has not completed yet'])
        
    try:
        model = CopasiModel(job.get_filename())
    except:
        return web_frontend_views.handle_error(request, 'Error Finding Job',['The requested job could not be found'])
    
    try:
        assert job.job_type == 'SO'
        results = model.get_so_results()
        #Get parameter names, min and max
        variable_choices = []
        for result in results:
            variable_choices.append(result['name'] + '_min')
            variable_choices.append(result['name'] + '_max')
    except:
        return web_frontend_views.handle_error(request, 'Error reading results',['An error occured while trying to processs the job output'])
    
    #If the variables GET field hasn't been set, preset it to all variables
    
    try:
        assert request.GET.get('custom') == 'true'
        form=SOPlotUpdateForm(request.GET, variable_choices=variable_choices)
    except:
        form=SOPlotUpdateForm(variable_choices=variable_choices, initial={'variables' : range(len(variable_choices))})
    
    if form.is_valid():
        variables = map(int,form.cleaned_data['variables'])
        log = form.cleaned_data['logarithmic']
        legend = form.cleaned_data['legend']
        grid = form.cleaned_data['grid']
    else:
        variables=range(len(variable_choices))
        log=False
        legend=False
        grid=True
        
    #construct the string to load the image file
    img_string = '?variables=' + str(variables).strip('[').rstrip(']').replace(' ', '')
    if log:
        img_string += '&log=true'
    if legend:
        img_string += '&legend=true'
    if grid:
        img_string += '&grid=true'
    
    pageTitle = 'Optimization Progress: ' + str(job.name)
    return render_to_response('my_account/so_progress_plot.html', locals(), RequestContext(request))
    
    
    
    
    
    
#Class for holding information about SO jobs to compare
class SOCompareForm(forms.Form):

    def __init__(self, list_of_job_ids, *args, **kwargs):
        
        super(SOCompareForm, self).__init__(*args, **kwargs)
        for i in list_of_job_ids:
            self.fields['%d_selected' % i] = forms.BooleanField(required=False)
            self.fields['%d_quantification' % i] = forms.IntegerField(required=True, initial=0, min_value=0, max_value=99)

    
@login_required
def compareSOJobs(request):
    pageTitle = 'Compare Global Sensitivity Job Output'
    submitted_job_count = len(models.Job.objects.filter(user=request.user, status='S') | models.Job.objects.filter(user=request.user, status='N') | models.Job.objects.filter(user=request.user, status='W') | models.Job.objects.filter(user=request.user, status='X'))
    completed_job_count = len(models.Job.objects.filter(user=request.user, status='C'))
    error_count = len(models.Job.objects.filter(user=request.user, status='E'))
    
    so_jobs = models.Job.objects.filter(user=request.user, status='C', job_type='SO')
    so_job_count=len(so_jobs)
    

    job_id_list = [job.id for job in so_jobs]

    if request.method == 'POST':
        #populate the form
        form = SOCompareForm(job_id_list, request.POST)
        if form.is_valid():
            #Generate appropriate output
            #First, check which job id's we're comparing
            compare_jobs=[]
            for job in so_jobs:
                if form.cleaned_data['%d_selected' % job.id]:
                    compare_jobs.append((job,form.cleaned_data['%d_quantification' % job.id]))
                    
            if len(compare_jobs) > 0:
                try:
                    motionchart_data = motionchart.prepare_data(compare_jobs)
                    return render_to_response('my_account/so_motionchart.html', locals(), RequestContext(request))
                    
                    
                except:
                    return web_frontend_views.handle_error(request, 'Error reading results',['An error occured while trying to processs the job output'])
                    
            
    else:
        form = SOCompareForm(job_id_list)
        
        
    jobs=[]
    
    
    
    for job in so_jobs:
        condor_jobs = models.CondorJob.objects.filter(parent=job)
        jobs.append((job, condor_jobs, form['%d_selected' % job.id], form['%d_quantification' % job.id]))
        
    return render_to_response('my_account/so_compare.html', locals(), RequestContext(request))


class dateTimePeriodForm(forms.Form):
    """Form for selecting dates for the usage statistics page"""
    start_date = forms.DateField(required=True, help_text='YYYY-MM-DD', widget=widgets.AdminDateWidget())
    end_date = forms.DateField(required=True, help_text='YYYY-MM-DD', widget=widgets.AdminDateWidget())
    
@login_required
def usageHome(request):
    Form = dateTimePeriodForm
    
    if request.method == 'POST':
        try:
            form = Form(request.POST, request.FILES)
            if form.is_valid():
                s = form.cleaned_data['start_date']
                e = form.cleaned_data['end_date']
                start_date = datetime.date(s.year, s.month, s.day)
                end_date = datetime.date(e.year, e.month, e.day)
                
                return HttpResponseRedirect(reverse('usage_by_period', args=[s,e]))
            
        except:
            return web_frontend_views.handle_error(request, 'Error processing dates',['An error occured while trying to process the given dates'])
    else:
        form = Form()
    
    today = datetime.date.today()
    year_start = datetime.date(year=today.year, month=1, day=1)
    month_start = datetime.date(year=today.year, month=today.month, day=1)
    week_start = today - datetime.timedelta(today.weekday())
    
    
    #Plot usage by month
    jobs = models.Job.objects.all().order_by('submission_time')
    
    #Create a list of months vs total job usage    
    
    
    
    return render_to_response('usage/usageHome.html', locals(), RequestContext(request))

@login_required
def usageByPeriod(request, start=None, end=None):
    
    if start == None or end == None:
        return render_to_response('usage/usage.html', locals(), RequestContext(request))
    elif start == 'all':
        selected_jobs = models.Job.objects.all()
        period_string = 'All Time'
    else:
        try:
            #Construct the period string...
            period_string = start + ' to ' + end
            
            #Deconstruct the date strings to extract year, month, day
            start_list = start.split('-')
            end_list = end.split('-')
            
            start_date = datetime.datetime(int(start_list[0]), int(start_list[1]), int(start_list[2]))
            end_date = datetime.datetime(int(end_list[0]), int(end_list[1]), int(end_list[2]))
            
            selected_jobs = models.Job.objects.filter(submission_time__gte=start_date).filter(submission_time__lte=end_date)
            
        except:
            return web_frontend_views.handle_error(request, 'Error processing dates',['An error occured while trying to process the given dates']) 
        
        
        
    total_cpu_time_days = 0.0
    for job in selected_jobs:
        try:
            total_cpu_time_days += job.run_time
        except:
            pass
            
    temp_cpu_time = datetime.timedelta(total_cpu_time_days)
    #Round the timedelta seconds
    total_cpu_time = datetime.timedelta(days=temp_cpu_time.days, seconds=temp_cpu_time.seconds + round(temp_cpu_time.microseconds/1000000.0))
    
    usage_list = []
    
    #Build up a data structure for the CPU usage, job usage etc by user pie chart
    users = User.objects.all().order_by('date_joined')
    for user in users:
        #Calculate the run time for each user
        jobs = selected_jobs.filter(user=user)
        run_time = 0.0
        
        job_count = len(jobs)
        
        for job in jobs:
            try:            
                run_time += job.run_time
            except:
                pass
                    
        #Append to the results
        if user.first_name == '' or user.last_name == '':
            username = user.username
        else:
            username = '%s %s (%s)' % (user.first_name, user.last_name, user.username)
        
        usage= {}
        usage['user'] = username
        usage['cpu_time'] = "%.2f" % run_time
        usage['job_count'] = job_count
        
        
        condor_job_count = 0
        for job in jobs:
            try:
                condor_job_count += job.condor_jobs
            except:
                pass
                        
        usage['condor_job_count'] = condor_job_count
        
        usage_list.append(usage)
    return render_to_response('usage/usageByPeriod.html', locals(), RequestContext(request))

