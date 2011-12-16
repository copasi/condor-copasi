from django.shortcuts import render_to_response, redirect
import datetime, os, shutil, re, math
from django import forms
from django.db import IntegrityError
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
import web_frontend.condor_copasi_db.views
from web_frontend import settings, condor_log, motionchart
from web_frontend.condor_copasi_db import models
from web_frontend import views as web_frontend_views
from web_frontend.copasi.model import CopasiModel
from django.core.urlresolvers import reverse
from django.core.files.uploadedfile import TemporaryUploadedFile


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
    job_name = forms.RegexField(max_length=64, regex=re.compile(r'^(a-z|A-Z|0-9)*[^%]*$'), label='Job Name', help_text='For your reference, enter a name for this job', widget=forms.TextInput(attrs={'size':'40'}))
    
    #Checkbox to give the user the option to skip the load balancing step
    skip_load_balancing = forms.BooleanField(label='Skip load balancing step', help_text='Select this to skip the automatic load balancing step, and make the run time of each parallel job as short as possible. <b>Use with caution! This has the potential to overload the Condor system with huge numbers of parallel jobs.</b> Not applicable for some job types - see documentation for further details.', required=False)
    
    def clean_job_name(self):
        job_name = self.cleaned_data['job_name']
        user = self.request.user
        try:
            jobs = models.Job.objects.filter(user=user, name=job_name, submitted=True)
            assert len(jobs)==0            
            return self.cleaned_data['job_name']
        except AssertionError:
            raise forms.ValidationError('A job with this name already exists.')

class SOUploadModelForm(UploadModelForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(UploadModelForm, self).__init__(*args, **kwargs)
        #This removes the skip load balancing field, which isn't required for this task
        self.fields.pop('skip_load_balancing')

class StochasticUploadModelForm(UploadModelForm):
    runs = forms.IntegerField(label='Repeats', help_text='The number of repeats to perform')        
    
    def clean_runs(self):
        runs = self.cleaned_data['runs']
        try:
            assert runs > 0
            return runs
        except AssertionError:
            raise forms.ValidationError('There must be at least one run')

#Form for the parameter estimation task. Adds one more file field
class ParameterEstimationUploadModelForm(StochasticUploadModelForm):
    parameter_estimation_data = forms.FileField(help_text='Select either a single data file, or if more than one data file is required, upload a .zip file containing multiple data files')
    custom_report = forms.BooleanField(label='Use a custom report', help_text='Select this to use a custom report instead of the automatically generated one. If you select this, Condor-COPASI may not be able to process the output data, and the job will fail. However, you will still be able download the unprocessed results for manual processing. For output processing to work, you must create a report with custom fields added before the fields that would otherwise be automatically generated (Best Parameters, Best Value, CPU Time and Function Evaluations).', required=False)
    
class RawUploadModelForm(StochasticUploadModelForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.get('request', None)
        super(RawUploadModelForm, self).__init__(*args, **kwargs)
        #This removes the skip load balancing field, which isn't required for this task
        self.fields.pop('skip_load_balancing')
    
    #Allow us to include some extra files for the run
    parameter_estimation_data = forms.FileField(required=False, label='Optional data files', help_text='Select either a single data file, or if more than one data file is required, upload a .zip file containing multiple data files')
    
    raw_mode_args = forms.RegexField(max_length=128, regex=re.compile(r'.*\$filename.*$'), label='Optional arguments', help_text='Optional arguments to add when running COPASI. Must contain <b>$filename</b> as an argument', widget=forms.TextInput(attrs={'size':'40'}), required=True, initial='--nologo --home . --save $filename $filename') #TODO: update this regex so that it won't match certain characters, e.g. ';','|', '&' etc (though perhaps this isn't necessary)

#Forms for the optimization repeat w/different algorithms task
class CurrentSolutionStatisticsForm(forms.Form):
    enabled = forms.BooleanField(label='Enabled', required=False)
    
    
class GeneticAlgorithmForm(forms.Form):
    enabled = forms.BooleanField(label='Enabled', required=False, widget=forms.CheckboxInput(attrs={'onclick':"toggle('genetic_algorithm', this);",}))
    no_of_generations = forms.IntegerField(label='Number of Generations', initial=200, min_value=1)
    population_size = forms.IntegerField(label='Population Size', initial=20, min_value=1)
    random_number_generator = forms.IntegerField(label='Random Number Generator', initial=1, min_value=0)
    seed=forms.IntegerField(label='Seed', initial=0, min_value=0)
    
class GeneticAlgorithmSRForm(forms.Form):
    enabled = forms.BooleanField(label='Enabled', required=False, widget=forms.CheckboxInput(attrs={'onclick':"toggle('genetic_algorithm_sr', this);",}))
    no_of_generations = forms.IntegerField(label='Number of Generations', initial=200, min_value=1)
    population_size = forms.IntegerField(label='Population Size', initial=20, min_value=1)
    random_number_generator = forms.IntegerField(label='Random Number Generator', initial=1, min_value=0)
    seed=forms.IntegerField(label='Seed', initial=0, min_value=0)
    pf = forms.FloatField(label='Pf', initial=0.475, min_value=0, max_value=1)    
    
class HookeAndJeevesForm(forms.Form):
    enabled = forms.BooleanField(label='Enabled', required=False, widget=forms.CheckboxInput(attrs={'onclick':"toggle('hooke_and_jeeves', this);",}))
    iteration_limit = forms.IntegerField(label='Iteration Limit', initial=50, min_value=1)
    tolerance = forms.FloatField(label='Tolerance', initial=1e-5, min_value=0)
    rho = forms.FloatField(label='Rho', initial=0.2, min_value=0, max_value=1)
    
class LevenbergMarquardtForm(forms.Form):
    enabled = forms.BooleanField(label='Enabled', required=False, widget=forms.CheckboxInput(attrs={'onclick':"toggle('levenberg_marquardt', this);",}))
    iteration_limit = forms.IntegerField(label='Iteration Limit', initial=200, min_value=1)
    tolerance = forms.FloatField(label='Tolerance', initial=1e-5, min_value=0)
    
class EvolutionaryProgrammingForm(forms.Form):
    enabled = forms.BooleanField(label='Enabled', required=False, widget=forms.CheckboxInput(attrs={'onclick':"toggle('evolutionary_programming', this);",}))
    no_of_generations = forms.IntegerField(label='Number of Generations', initial=200, min_value=1)
    population_size = forms.IntegerField(label='Population Size', initial=20, min_value=1)
    random_number_generator = forms.IntegerField(label='Random Number Generator', initial=1, min_value=0)
    seed=forms.IntegerField(label='Seed', initial=0, min_value=0)
    
class RandomSearchForm(forms.Form):
    enabled = forms.BooleanField(label='Enabled', required=False, widget=forms.CheckboxInput(attrs={'onclick':"toggle('random_search', this);",}))
    no_of_iterations = forms.IntegerField(label='Number of Iterations', initial=100000, min_value=1)
    random_number_generator = forms.IntegerField(label='Random Number Generator', initial=1, min_value=0)
    seed=forms.IntegerField(label='Seed', initial=0, min_value=0)
    
class NelderMeadForm(forms.Form):
    enabled = forms.BooleanField(label='Enabled', required=False, widget=forms.CheckboxInput(attrs={'onclick':"toggle('nelder_mead', this);",}))
    iteration_limit = forms.IntegerField(label='Iteration Limit', initial=200, min_value=1)
    tolerance = forms.FloatField(label='Tolerance', initial=1e-5, min_value=0)
    scale = forms.FloatField(label='Scale', initial=10, min_value=0)
    
class ParticleSwarmForm(forms.Form):
    enabled = forms.BooleanField(label='Enabled', required=False, widget=forms.CheckboxInput(attrs={'onclick':"toggle('particle_swarm', this);",}))
    iteration_limit = forms.IntegerField(label='Iteration Limit', initial=2000, min_value=1)
    swarm_size = forms.IntegerField(label='Swarm Size', initial=50, min_value=1)
    std_deviation = forms.FloatField(label='Std. Deviation', initial=1e-6, min_value=0)
    random_number_generator = forms.IntegerField(label='Random Number Generator', initial=1, min_value=0)
    seed=forms.IntegerField(label='Seed', initial=0, min_value=0)
    
class PraxisForm(forms.Form):
    enabled = forms.BooleanField(label='Enabled', required=False, widget=forms.CheckboxInput(attrs={'onclick':"toggle('praxis', this);",}))
    tolerance = forms.FloatField(label='Tolerance', initial=1e-5, min_value=0)
    
class TruncatedNewtonForm(forms.Form):
    enabled = forms.BooleanField(label='Enabled', required=False)
    
    
class SimulatedAnnealingForm(forms.Form):
    enabled = forms.BooleanField(label='Enabled', required=False, widget=forms.CheckboxInput(attrs={'onclick':"toggle('simulated_annealing', this);",}))
    start_temperature = forms.FloatField(label='Start Temperature', initial=1, min_value=0)
    cooling_factor = forms.FloatField(label='Cooling Factor', initial=0.85, min_value=0)
    tolerance = forms.FloatField(label='Tolerance', initial=1e-6, min_value=0)
    random_number_generator = forms.IntegerField(label='Random Number Generator', initial=1, min_value=0)
    seed=forms.IntegerField(label='Seed', initial=0, min_value=0)
    
    
class EvolutionStrategyForm(forms.Form):
    enabled = forms.BooleanField(label='Enabled', required=False, widget=forms.CheckboxInput(attrs={'onclick':"toggle('evolution_strategy', this);",}))
    no_of_generations = forms.IntegerField(label='Number of Generations', initial=200, min_value=1)
    population_size = forms.IntegerField(label='Population Size', initial=20, min_value=1)
    random_number_generator = forms.IntegerField(label='Random Number Generator', initial=1, min_value=0)
    seed=forms.IntegerField(label='Seed', initial=0, min_value=0)
    pf = forms.FloatField(label='Pf', initial=0.475, min_value=0, max_value=1)    
    
class SteepestDescentForm(forms.Form):
    enabled = forms.BooleanField(label='Enabled', required=False, widget=forms.CheckboxInput(attrs={'onclick':"toggle('steepest_descent', this);",}))
    iteration_limit = forms.IntegerField(label='Iteration Limit', initial=100, min_value=1)
    tolerance = forms.FloatField(label='Tolerance', initial=1e-6, min_value=0)
    
    
#form to update the stochastic simulation plots
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

#form to update the SO progress plots
class SOPlotUpdateForm(forms.Form):
    """Form containing controls to update plots"""
    
    def __init__(self, *args, **kwargs):
        variables = kwargs.pop('variable_choices', None)
        variable_choices = []
        for i in range(len(variables)):
            variable_choices.append((i, variables[i]))

        super(SOPlotUpdateForm, self).__init__(*args, **kwargs)
        self.fields['variables'].choices = variable_choices
        
    legend = forms.BooleanField(label='Show figure legend', required=False, initial=False)
    grid = forms.BooleanField(label='Show grid', required=False, initial=True)
    logarithmic = forms.BooleanField(label='Logarithmic scale', required=False)
    variables = forms.MultipleChoiceField(choices=(), widget=forms.CheckboxSelectMultiple(), required=True)
    
class ChangePasswordForm(forms.Form):
    """Form for allowing a user to change their password. Checks that the old password is valid, and the new passwords match"""
    old_password = forms.CharField(label='Current password',widget=forms.PasswordInput(render_value=False))
    new_password_1 = forms.CharField(label='New password',widget=forms.PasswordInput(render_value=False))
    new_password_2 = forms.CharField(label='New password again',widget=forms.PasswordInput(render_value=False))  
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(ChangePasswordForm, self).__init__(*args, **kwargs)
        
    def clean_old_password(self):
        user = self.request.user
        old_pass = self.cleaned_data['old_password']
        if user.check_password(old_pass):
            return old_pass
        else:
            raise forms.ValidationError('The password you entered was not correct')
            
            
    def clean_new_password_2(self):
        new_pass_1 = self.cleaned_data['new_password_1']
        new_pass_2 = self.cleaned_data['new_password_2']
        
        if new_pass_1 == new_pass_2:
            return new_pass_2
        else:
            raise forms.ValidationError('The new passwords must match')
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
        Form = UploadModelForm
    elif type == 'OR':
        pageTitle = 'Optimization Repeat'
        Form = StochasticUploadModelForm
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
        Form = SOUploadModelForm
        
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
    if request.method == 'POST':
        form = Form(request.POST, request.FILES, request=request)

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
                    if type == 'SS' or type == 'OR' or type=='PR' or type=='RW':
                        runs=int(form.cleaned_data['runs'])
                    elif type == 'OD':
                        runs = algorithms_selected # Use runs in this instance as a count of the number of algorithms we're running
                    else:
                        runs = None
                        
                    try:
                        skip_load_balancing = form.cleaned_data['skip_load_balancing']
                    except:
                        skip_load_balancing = None
                    
                    job = models.Job(job_type=type, user=request.user, model_name=model_file.name, status='U', name=form.cleaned_data['job_name'], submission_time=datetime.datetime.today(), runs = runs, last_update=datetime.datetime.today(), skip_load_balancing=skip_load_balancing)
                    
                    if type=='PR':
                        job.custom_report = form.cleaned_data['custom_report']
                    if type=='RW':
                        job.raw_mode_args = form.cleaned_data['raw_mode_args']
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
        form = Form()
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
            ('Number of runs', job.runs)
        )
        return render_to_response('tasks/task_confirm.html', locals(), RequestContext(request))
    elif job.job_type == 'PS':
        pageTitle = 'Confirm Parallel Scan Task'
        job_details = (
            ('Job Name', job.name),
            ('File Name', job.model_name),
            ('Model Name', model.get_name()),
            ('Total number of scans', model.get_ps_number())
        )
        return render_to_response('tasks/task_confirm.html', locals(), RequestContext(request))
        
    elif job.job_type == 'OR':
        pageTitle = 'Confirm Optimization Repeat Task'
        job_details = (
            ('Job Name', job.name),
            ('File Name', job.model_name),
            ('Model Name', model.get_name()),
            ('Number of runs', job.runs),
        )
        return render_to_response('tasks/task_confirm.html', locals(), RequestContext(request))
        
    elif job.job_type == 'PR':
        pageTitle = 'Confirm Parameter Estimation Repeat Task'
        job_details = (
            ('Job Name', job.name),
            ('File Name', job.model_name),
            ('Model Name', model.get_name()),
            ('Number of Repeats', job.runs),
        )
        return render_to_response('tasks/task_confirm.html', locals(), RequestContext(request))
    elif job.job_type == 'OD':
        pageTitle = 'Confirm Optimization Repeat with Different Algorithms Task'
        job_details = (
            ('Job Name', job.name),
            ('File Name', job.model_name),
            ('Model Name', model.get_name()),
            ('Number of Algorithms Selected', job.runs),
        )
        return render_to_response('tasks/task_confirm.html', locals(), RequestContext(request))
        
    elif job.job_type == 'RW':
        pageTitle = 'Confirm Optimization Repeat with Different Algorithms Task'
        job_details = (
            ('Job Name', job.name),
            ('File Name', job.model_name),
            ('Model Name', model.get_name()),
            ('Arguments', job.raw_mode_args),
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
        
        #Calculate the total amount of CPU time used by the individual condor jobs
        total_cpu_time = datetime.timedelta()
        for condor_job in models.CondorJob.objects.filter(parent=job):
            try:
                log_file = os.path.join(job.get_path(), condor_job.log_file)
                log = condor_log.Log(log_file)
                total_cpu_time += log.running_time
            except:
                pass
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
        os.environ['HOME'] = settings.USER_FILES_DIR #This needs to be set to a writable directory
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
        os.environ['HOME'] = settings.USER_FILES_DIR #This needs to be set to a writable directory
        import matplotlib
        matplotlib.use('Agg') #Use this so matplotlib can be used on a headless server. Otherwise requires DISPLAY env variable to be set.
        import matplotlib.pyplot as plt

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

