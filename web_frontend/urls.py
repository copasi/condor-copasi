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
    url(r'^admin/', include(admin.site.urls), name="adminsite"),
    url(r'^my_admin/jsi18n', 'django.views.i18n.javascript_catalog'),
    url(r'^$', mainPage, name="index"),
    url(r'^login/$', loginPage, name="login"),
    url(r'^logout/$',logoutPage, name="logout"),
    url(r'^tasks/$', db_tasks, name="tasks_home"),
    url(r'^tasks/new/sensitivity_optimization/$', db.newTask, {'type': 'SO'}, name="new_SO"),
    url(r'^tasks/new/stochastic_simulation/$', db.newTask, {'type': 'SS'}, name="new_SS"),
    url(r'^tasks/new/parallel_scan/$', db.newTask, {'type': 'PS'}, name="new_PS"),
    url(r'^tasks/new/raw/$', db.newTask, {'type': 'RW'}, name="new_RW"),
    url(r'^tasks/new/optimization_repeat/$', db.newTask, {'type': 'OR'}, name="new_OR"),
    url(r'^tasks/new/parameter_estimation_repeat/$', db.newTask, {'type': 'PR'}, name="new_PR"),
    url(r'^tasks/new/optimization_repeat_different_algorithms/$', db.newTask, {'type': 'OD'}, name="new_OD"),
    url(r'^tasks/new/confirm/(?P<job_id>\w+)/$', db.taskConfirm, name="confirm_task"),
    url(r'^my_account/$', db.myAccount, name="my_account"),
    url(r'^my_account/change_password$', db.change_password, name="change_password"),
    url(r'^my_account/jobs/running/$', db.myAccountRunningJobs, name="running_jobs"),
    url(r'^my_account/jobs/completed/$', db.myAccountCompletedJobs, name="completed_jobs"),
    url(r'^my_account/jobs/errors/$', db.myAccountJobErrors, name="job_errors"),
    url(r'^my_account/jobs/details/(?P<job_name>.+)/download/best_results/$', db.prModelDownload, name="pr_best_results_download"),
    url(r'^my_account/jobs/details/(?P<job_name>.+)/download/$', db.jobDownload, name="job_download"),
    url(r'^my_account/jobs/details/(?P<job_name>.+)/save/plot.png$', db.ss_plot, name="plot"),
    url(r'^my_account/jobs/details/(?P<job_name>.+)/progress/plot.png$', db.so_progress_plot, name="so_progress_plot"),
    url(r'^my_account/jobs/details/(?P<job_name>.+)/progress/$', db.so_progress_page, name="so_progress_page"),
    url(r'^my_account/jobs/details/(?P<job_name>.+)/save/$', db.jobResultDownload, name="job_save"),
    url(r'^my_account/jobs/details/(?P<job_name>.+)/output/$', db.jobOutput, name="job_output"),
    url(r'^my_account/jobs/details/(?P<job_name>.+)/remove/$', db.jobRemove, name="job_remove"),
    url(r'^my_account/jobs/details/(?P<job_name>.+)/$', db.jobDetails, name="job_details"),
    url(r'^my_account/jobs/compare/so/$', db.compareSOJobs, name="so_compare"),
    url(r'^help/$', helpPage, name="help"),
    url(r'^usage/$', db.usageHome, name="usage_home"),
    url(r'^usage/all/$', db.usageByPeriod, {'start':'all', 'end':'all'} ,name="usage_by_period_all"),
    url(r'^usage/(?P<start>.+)/to/(?P<end>.+)/$', db.usageByPeriod, name="usage_by_period"),
)

if settings.DEBUG:
    urlpatterns += patterns('',
        (r'^static/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.MEDIA_ROOT}),
    )
