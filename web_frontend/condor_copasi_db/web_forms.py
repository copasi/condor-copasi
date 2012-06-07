#This file contains all the forms used in views.py
#Refactored as of revision 219

from django import forms
from web_frontend.condor_copasi_db import models
import re

#Used as a base for all task submit forms. Contains the information required by every task
class UploadModelForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        last_rank = kwargs.pop('last_rank', False)
        
        super(UploadModelForm, self).__init__(*args, **kwargs)
        
        if last_rank:
            self.fields['rank'].help_text = """<script type="text/javascript">
            function loadtext() {
                oFormObject = document.forms[0];
                oFormElement = oFormObject.elements["id_rank"];
                oFormElement.value = "%s";
            }
            </script> <a href="javascript:loadtext()">Use rank from last job</a>. """ % last_rank
        else:
            self.fields['rank'].help_text = ''
        self.fields['rank'].help_text += 'If you are unsure how to use rank, then do not change from the default value'
        
    model_file = forms.FileField()
    #Use a regex to exclude slashes or percentages. Also, must begin with non-whitespace character
    job_name = forms.RegexField(max_length=64, regex=re.compile(r'^[^%/\\\s]+[^%/\\]*$'), label='Job Name', help_text='For your reference, enter a name for this job', widget=forms.TextInput(attrs={'size':'40'}))
    
    
    rank = forms.CharField(max_length=5000, label='Rank', help_text='', initial='0', widget=forms.TextInput(attrs={'size':'40'}))

    def clean_job_name(self):
        job_name = self.cleaned_data['job_name']
        user = self.request.user
        try:
            jobs = models.Job.objects.filter(user=user, name=job_name, submitted=True)
            assert len(jobs)==0            
            return self.cleaned_data['job_name']
        except AssertionError:
            raise forms.ValidationError('A job with this name already exists.')

#Sensitivity optimization form
class SOUploadModelForm(UploadModelForm):
    pass #No difference from the base form

#Stochastic simulation form. Contains extra fields for number of runs, and option to skip load balancing step
class StochasticUploadModelForm(UploadModelForm):
    skip_load_balancing = forms.BooleanField(label='Skip load balancing step', help_text='Select this to skip the automatic load balancing step, and make the run time of each parallel job as short as possible. <b>Use with caution! This has the potential to overload the Condor system with huge numbers of parallel jobs.</b> Not applicable for some job types - see documentation for further details.', required=False)

    runs = forms.IntegerField(label='Repeats', help_text='The number of repeats to perform')        
   
    def clean_runs(self):
        runs = self.cleaned_data['runs']
        try:
            assert runs > 0
            return runs
        except AssertionError:
            raise forms.ValidationError('There must be at least one run')


#Form for parallel scan task
class ParallelScanForm(UploadModelForm):
    skip_load_balancing = forms.BooleanField(label='Skip load balancing step', help_text='Select this to skip the automatic load balancing step, and make the run time of each parallel job as short as possible. <b>Use with caution! This has the potential to overload the Condor system with huge numbers of parallel jobs.</b> Not applicable for some job types - see documentation for further details.', required=False)

#Form for the Optimization Repeat task
class OptimizationRepeatForm(UploadModelForm):

    runs = forms.IntegerField(label='Repeats', help_text='The number of repeats to perform')        
    skip_load_balancing = forms.BooleanField(label='Skip load balancing step', help_text='Select this to skip the automatic load balancing step, and make the run time of each parallel job as short as possible. <b>Use with caution! This has the potential to overload the Condor system with huge numbers of parallel jobs.</b> Not applicable for some job types - see documentation for further details.', required=False)

#Form for the parameter estimation task.
class ParameterEstimationUploadModelForm(UploadModelForm):

    runs = forms.IntegerField(label='Repeats', help_text='The number of repeats to perform')        

    parameter_estimation_data = forms.FileField(help_text='Select either a single data file, or if more than one data file is required, upload a .zip file containing multiple data files')
    custom_report = forms.BooleanField(label='Use a custom report', help_text='Select this to use a custom report instead of the automatically generated one. If you select this, Condor-COPASI may not be able to process the output data, and the job will fail. However, you will still be able download the unprocessed results for manual processing. For output processing to work, you must create a report with custom fields added before the fields that would otherwise be automatically generated (Best Parameters, Best Value, CPU Time and Function Evaluations).', required=False)
    skip_load_balancing = forms.BooleanField(label='Skip load balancing step', help_text='Select this to skip the automatic load balancing step, and make the run time of each parallel job as short as possible. <b>Use with caution! This has the potential to overload the Condor system with huge numbers of parallel jobs.</b> Not applicable for some job types - see documentation for further details.', required=False)
    skip_model_generation = forms.BooleanField(label='Skip automatic model generation', help_text='Select this to prevent Condor-COPASI from creating a new model contanining the best values found by the task. In most cases this will not need to be changed, though can slow down results processing for larger models.', required=False)
    
class RawUploadModelForm(UploadModelForm):

    runs = forms.IntegerField(label='Repeats', help_text='The number of repeats to perform')

    #Allow us to include some extra files for the run
    parameter_estimation_data = forms.FileField(required=False, label='Optional data files', help_text='Select either a single data file, or if more than one data file is required, upload a .zip file containing multiple data files')
    
    raw_mode_args = forms.RegexField(max_length=128, regex=re.compile(r'.*\$filename.*$'), label='Optional arguments', help_text='Optional arguments to add when running COPASI. Must contain <b>$filename</b> as an argument', widget=forms.TextInput(attrs={'size':'40'}), required=True, initial='--nologo --home . --save $filename $filename') #TODO: update this regex so that it won't match certain characters, e.g. ';','|', '&' etc (though perhaps this isn't necessary)



class ODUploadModelForm(UploadModelForm):
    pass






#----------------------------
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
    fontsize = forms.IntegerField(label='Font size', required=False, initial='12')
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
    fontsize = forms.IntegerField(label='Font size', required=False, initial='12')
    
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
