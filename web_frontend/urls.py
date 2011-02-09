from django.conf.urls.defaults import *
from web_frontend.views import *
from web_frontend.condor_copasi_db import views as db
from web_frontend.condor_copasi_db.views import tasks as db_tasks
# Uncomment the next two lines to enable the admin:
from django.contrib import admin
from django.conf import settings
admin.autodiscover()

urlpatterns = patterns('',
    # Example:
    # (r'^web_frontend/', include('web_frontend.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    #(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    (r'^admin/', include(admin.site.urls)),
    (r'^$', mainPage),
    (r'login/$', loginPage),
    (r'logout/$',logoutPage),
    (r'tasks/$', db_tasks),
    (r'tasks/new/sensitivity_optimization/$', db.newTask, {'type': 'SO'}),
    (r'tasks/new/stochastic_simulation/$', db.newTask, {'type': 'SS'}),
    (r'tasks/new/parallel_scan/$', db.newTask, {'type': 'PS'}),
    (r'tasks/new/optimization_repeat/$', db.newTask, {'type': 'OR'}),
    (r'tasks/new/parameter_estimation_repeat/$', db.newTask, {'type': 'PR'}),
    (r'tasks/new/optimization_repeat_different_algorithms/$', db.newTask, {'type': 'OD'}),
    (r'tasks/new/confirm/(?P<job_id>\w+)/$', db.taskConfirm),
    (r'my_account/$', db.myAccount),
    (r'my_account/change_password$', db.change_password),
    (r'my_account/jobs/running/$', db.myAccountRunningJobs),
    (r'my_account/jobs/completed/$', db.myAccountCompletedJobs),
    (r'my_account/jobs/errors/$', db.myAccountJobErrors),
    (r'my_account/jobs/details/(?P<job_name>.+)/download/$', db.jobDownload),
    (r'my_account/jobs/details/(?P<job_name>.+)/save/plot.png$', db.ss_plot),
    (r'my_account/jobs/details/(?P<job_name>.+)/save/$', db.jobResultDownload),
    (r'my_account/jobs/details/(?P<job_name>.+)/output/$', db.jobOutput),
    (r'my_account/jobs/details/(?P<job_name>.+)/remove/$', db.jobRemove),
    (r'my_account/jobs/details/(?P<job_name>.+)/$', db.jobDetails),
)

if settings.DEBUG:
    urlpatterns += patterns('',
        (r'^static/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.MEDIA_ROOT}),
    )
