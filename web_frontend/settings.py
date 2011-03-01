# Django settings for web_frontend project.
import os.path
import logging


DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2', # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': '',                      # Or path to database file if using sqlite3.
        'USER': '',                      # Not used with sqlite3.
        'PASSWORD': '',                  # Not used with sqlite3.
        'HOST': '',                      # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
    }
}

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'rl9pqx!dyqf)ev#@%1#82maga0c^m&))su%=crvfw^f$o$&cr1'

#The subfolder the site is served from on the webserver, e.g. '/condor-copasi/' for www.domain.com/condor-copasi/. If serving from the root, set to '/'
SITE_SUBFOLDER = '/'
#The domain on which condor_copasi is being hosted. e.g. for www.domain.com/condor-copasi set to 'www.domain.com'. Note, no trailing '/'
SITE_DOMAIN = 'www.domain.com'
#The directory to store user uploaded and automatically generated files. Must be writable by the web server and background daemon (See Wiki page on Deployment for details)
USER_FILES_DIR = '/path/to/user/files'

#The path to the log file. This must be in a directory in which the background daemon can write
LOG_FILE = os.path.join('/var/log/condor-copasi/daemon-log.txt')
#Set the logging level. Either logging.DEBUG or logging.ERROR
LOG_LEVEL = logging.DEBUG

#The directoriy containing CopasiSE binary files
COPASI_BINARY_DIR = '/home/ed/bin/condor_files/'
#The copasi binary that is able to run on the local machine
COPASI_LOCAL_BINARY = os.path.join(COPASI_BINARY_DIR, 'CopasiSE.LINUX.X86_64')

#The number of days completed jobs are stored for. To disable automatic job removal, set this to 0
COMPLETED_JOB_REMOVAL_DAYS = 14

#The minimim time between condor_q polls in minutes. If too small can cause condor pool to become overwhelmed!
MIN_CONDOR_Q_POLL_TIME = 2

#The ideal time, in minutes, to aim for when splitting tasks up.
#   Too small, and the overhead of submitting jobs becomes an issue.
#   Too large, and the benefits of parralelisation are lost.
#   Larger still, and the jobs risk being pre-empted by condor.
IDEAL_JOB_TIME = 15

#Send email notifications, e.g. job completion, job errors?
SEND_EMAILS = False
#The SMTP Host server.
SMTP_HOST = 'smtp.manchester.ac.uk'
#The 'from' email address
EMAIL_FROM_ADDRESS = 'condor-copasi@googlecode.com' 

#Optional: link to condor pool status page. Will be included on the home page. Include the full address, e.g. 'http://www.domain.com/condor_status_page/'
CONDOR_POOL_STATUS = ''

#Optional: Condor-Copasi can submit jobs using the username of the webfrontend users, rather than the user running the background daemon.
#This requires significant extra system configuration to function correctly; see the wiki page for details
SUBMIT_WITH_USERNAMES = False

#########################

#Django configuration follows below; this does not usually need to be changed

#########################

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'Europe/London'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1
LOGIN_URL = SITE_SUBFOLDER.rstrip('/') + '/login/'
LOGOUT_URL = SITE_SUBFOLDER.rstrip('/') + '/logout/'
# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = os.path.join(os.path.dirname(__file__), 'static').replace('\\','/')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/static/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = SITE_SUBFOLDER.rstrip('/') + '/admin/static/'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

ROOT_URLCONF = 'web_frontend.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(os.path.dirname(__file__), 'templates').replace('\\','/'),
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
#    'django.contrib.sites',
    'django.contrib.messages',
    # Uncomment the next line to enable the admin:
    'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    'django.contrib.admindocs',
    'condor_copasi_db',
    'copasi'
)

TEMPLATE_CONTEXT_PROCESSORS = ('django.core.context_processors.request',
'django.core.context_processors.auth',
'django.core.context_processors.debug',
'django.core.context_processors.i18n',
'context_processors.folder_urls',
'context_processors.cc_version',
)

FILE_UPLOAD_HANDLERS= ("django.core.files.uploadhandler.TemporaryFileUploadHandler",)
