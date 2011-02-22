import os
import sys
path = '/home/ed/condor-copasi-svn/'
if path not in sys.path:
    sys.path.append(path)


os.environ['DJANGO_SETTINGS_MODULE'] = 'web_frontend.settings'

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()
