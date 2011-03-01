from django.shortcuts import render_to_response
import datetime, pickle, os
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from web_frontend import settings
from django.core.urlresolvers import reverse

def mainPage(request):
    pageTitle = 'Home'
    
    #Attempt to load the queue status from user_files/condor_status.pickle
    try:
        pickle_filename = os.path.join(settings.USER_FILES_DIR, 'condor_status.pickle')
        pickle_file = open(pickle_filename, 'r')
        status = pickle.load(pickle_file)
        pickle_file.close()
    except:
        pass
    if settings.CONDOR_POOL_STATUS != '':
        pool_status_page = settings.CONDOR_POOL_STATUS
        
    return render_to_response('index.html', locals(), RequestContext(request))

def helpPage(request):
    pageTitle = 'Help'
    return render_to_response('help.html', locals(), RequestContext(request))    

class LoginForm(forms.Form):
    username = forms.CharField(label='Username')
    password = forms.CharField(label='Password',widget=forms.PasswordInput(render_value=False)) 


def loginPage(request):
    if request.user.is_authenticated():
        return HttpResponseRedirect(settings.SITE_SUBFOLDER)
    login_failure = False
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            username = cd['username']
            password = cd['password']
            user = authenticate(username=username, password=password)
            if user is not None:
                #Successfully authenticated - log in
                login(request, user)
                try:
                    return HttpResponseRedirect(request.GET['next'])
                except:
                    return HttpResponseRedirect(reverse('index'))
            else:
                #Login unsuccsessful
                login_failure = True
    else:        
        form = LoginForm()

    pageTitle = 'Login'
    return render_to_response('login.html', {'pageTitle': pageTitle, 'login_failure': login_failure, 'form':form}, context_instance=RequestContext(request))
        

def logoutPage(request):
    #Logout
    logout(request)
    return HttpResponseRedirect(reverse('index'))
    
    
def handle_error(request, pageTitle, errors=[]):
    return render_to_response('500.html', locals(), context_instance=RequestContext(request))
    

