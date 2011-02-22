import os
import sys

currentdir = os.path.dirname(__file__)
#Get the web frontend dir
wfdir, blah = os.path.split(currentdir)
#And the web frontend parend dir
parentdir, blah = os.path.split(wfdir)

#Add them both to the python path
if wfdir not in sys.path:
    sys.path.append(wfdir)
if parentdir not in sys.path:
    sys.path.append(parentdir)


os.environ['DJANGO_SETTINGS_MODULE'] = 'web_frontend.settings'

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()
