from django.shortcuts import render_to_response
import datetime    
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.template import RequestContext

@login_required
def tasks(request):
    pageTitle = 'Setup new task'
    return render_to_response('tasks/tasks.html', locals(), RequestContext(request))
    
class UploadModelForm(forms.Form):
    file = forms.FileField()
    job_name = forms.CharField(max_length=64, label='Job Name', help_text='For your reference, enter a name for this job', widget=forms.TextInput(attrs={'size':'40'}))

@login_required
def sensitivityOptimization(request):
    pageTitle = 'Optimization of Sensitivities'
    #Upload page for a new sensitvity optimization task
    if request.method == 'POST':
        form = UploadModelForm(request.POST, request.FILES)
        if form.is_valid():
            #file can be accessed by request.FILES['file']
            #Confirm model is valid by running a number of tests on it, e.g. valid xml, correct tasks set up properly etc.
            pass
    else:
        form = UploadModelForm()
        
    confirm = False
    return render_to_response('tasks/sensitivity_optimization.html', locals(), RequestContext(request))
    
@login_required
def sensitivityOptimizationConfirm(request):
    #Prompt the user for confirmation that the job is set up properly
    #List: the optimization method, variables to be optimized etc.
    #On confirm, submit the job to the database
    pass
