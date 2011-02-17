from django.conf.urls.defaults import *
from web_frontend.views import *
from web_frontend.condor_copasi_db import views as db
from web_frontend.condor_copasi_db.views import tasks as db_tasks
# Uncomment the next two lines to enable the admin:
from django.contrib import admin
from django.conf import settings
admin.autodiscover()
subfolder = settings.SITE_SUBFOLDER.lstrip('/')

urlpatterns = patterns('',
    # Example:
    # (r'^web_frontend/', include('web_frontend.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    #(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^%sadmin/' % subfolder, include(admin.site.urls), name="admin"),
    url(r'^%s$' % subfolder, mainPage, name="index"),
    url(r'^%slogin/$' % subfolder, loginPage, name="login"),
    url(r'^%slogout/$' % subfolder,logoutPage, name="logout"),
    url(r'^%stasks/$' % subfolder, db_tasks, name="tasks_home"),
    url(r'^%stasks/new/sensitivity_optimization/$' % subfolder, db.newTask, {'type': 'SO'}, name="new_SO"),
    url(r'^%stasks/new/stochastic_simulation/$' % subfolder, db.newTask, {'type': 'SS'}, name="new_SS"),
    url(r'^%stasks/new/parallel_scan/$' % subfolder, db.newTask, {'type': 'PS'}, name="new_PS"),
    url(r'^%stasks/new/optimization_repeat/$' % subfolder, db.newTask, {'type': 'OR'}, name="new_OR"),
    url(r'^%stasks/new/parameter_estimation_repeat/$' % subfolder, db.newTask, {'type': 'PR'}, name="new_PR"),
    url(r'^%stasks/new/optimization_repeat_different_algorithms/$' % subfolder, db.newTask, {'type': 'OD'}, name="new_OD"),
    url(r'^%stasks/new/confirm/(?P<job_id>\w+)/$' % subfolder, db.taskConfirm, name="confirm_task"),
    url(r'^%smy_account/$' % subfolder, db.myAccount, name="my_account"),
    url(r'^%smy_account/change_password$' % subfolder, db.change_password, name="change_password"),
    url(r'^%smy_account/jobs/running/$' % subfolder, db.myAccountRunningJobs, name="running_jobs"),
    url(r'^%smy_account/jobs/completed/$' % subfolder, db.myAccountCompletedJobs, name="completed_jobs"),
    url(r'^%smy_account/jobs/errors/$' % subfolder, db.myAccountJobErrors, name="job_errors"),
    url(r'^%smy_account/jobs/details/(?P<job_name>.+)/download/$' % subfolder, db.jobDownload, name="job_download"),
    url(r'^%smy_account/jobs/details/(?P<job_name>.+)/save/plot.png$' % subfolder, db.ss_plot, name="plot"),
    url(r'^%smy_account/jobs/details/(?P<job_name>.+)/save/$' % subfolder, db.jobResultDownload, name="job_save"),
    url(r'^%smy_account/jobs/details/(?P<job_name>.+)/output/$' % subfolder, db.jobOutput, name="job_output"),
    url(r'^%smy_account/jobs/details/(?P<job_name>.+)/remove/$' % subfolder, db.jobRemove, name="job_remove"),
    url(r'^%smy_account/jobs/details/(?P<job_name>.+)/$' % subfolder, db.jobDetails, name="job_details"),
)

if settings.DEBUG:
    urlpatterns += patterns('',
        (r'^%sstatic/(?P<path>.*)$' % subfolder, 'django.views.static.serve', {'document_root': settings.MEDIA_ROOT}),
    )
