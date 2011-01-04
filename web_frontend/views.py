from django.shortcuts import render_to_response
import datetime    
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
    
def mainPage(request):
    pageTitle = 'Home'
    return render_to_response('index.html', locals(), RequestContext(request))
    
class LoginForm(forms.Form):
    username = forms.CharField(label='Username')
    password = forms.CharField(label='Password',widget=forms.PasswordInput(render_value=False)) 

def loginPage(request):
    if request.user.is_authenticated():
        return HttpResponseRedirect('/')
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
                    return HttpResponseRedirect('/')
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
    return HttpResponseRedirect('/')
    
@login_required
def restricted(request):
    return HttpResponseRedirect('/')
    
