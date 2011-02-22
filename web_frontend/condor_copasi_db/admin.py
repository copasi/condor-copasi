from django.contrib import admin
from web_frontend.condor_copasi_db.models import *

admin.site.register(Job)
admin.site.register(CondorJob)

#Hide the 'group' field from the admin site
from django.contrib.auth.models import Group 
from django.contrib import admin 
admin.site.unregister(Group)
