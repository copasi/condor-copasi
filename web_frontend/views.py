from django.shortcuts import render_to_response

import datetime    
from django import forms

def mainPage(request):

    pageTitle = 'Home'
    return render_to_response('index.html', locals())
