**This page is intended to provide information for those wishing to install Condor-COPASI on their own server. For information on using the Condor-COPASI web interface, see the [Instruction Manual](Instructions.md) Wiki page.**

The Condor-COPASI Web Frontend is written in Python as a [Django 1.2 Application](http://docs.djangoproject.com/en/1.2/releases/1.2.4/). In addition to the web frontend, a background daemon must be configured. This daemon periodically checks for new jobs to submit to condor, and checks on the status of jobs that have already been submitted.

# General setup #

## Python setup ##
Python 2.6 must be installed and configured.

#### LXML ####
The [LXML](http://lxml.de/tutorial.html) package must be installed, and added to the python path.

#### Matplotlib ####
To make use of the stochastic simulation plotting feature, the [matplotlib](http://matplotlib.sourceforge.net/) Python library must be installed and in the Python path.

Condor-COPASI has only been tested with version 0.99.1.1


## Django setup ##
Django version 1.2.4 or 1.2.5 must be installed and in the Python path. See http://www.djangoproject.com/download/ for details.

## Condor setup ##
Condor must be installed and configured as a submit node. Specifically, we must be able to submit jobs to the Condor pool by running `condor_submit`, and check the queue status by running `condor_q`.

Condor COPASI has only been tested with Condor version 7.4.2


# Web Frontend #
Deployment involves a few additional steps in addition to the standard Django application deployment procedure.


## Database setup ##
Condor COPASI uses a database to store information on users and the jobs they have submitted. Django supports a number of different databases (see http://docs.djangoproject.com/en/1.2/ref/databases/), including:
  * PostgreSQL
  * MySQL
  * SQLite
  * Oracle
Note that an appropriate python wrapper must also be installed.

While all these databases should work with Condor COPASI, please note that we have only tested with PostgreSQL 8.4 with the [psycopg2](http://initd.org/psycopg/) Python adaptor.

### Configuring the database ###
A new database should be created, and  username and password should be set up to allow Condor COPASI to access this database. Refer to your database documentation for details on how to do this. Initially this user must have permission to create tables in the database, though after the database has been initially populated (see below), this privilege can be dropped.

Note that the database will be accessed by both the web frontend and the background daemon. Depending on your system configuration, it is likely that the web server and background daemon will be running as different users, though both will need to be able to log into the database using the same username/password combination, and so the database must be configured to accommodate this situation.

In PostgreSQL, this could involved changing the default local authentication method from ident to md5 in pg\_hba.conf:

**from:**
```
# IPv4 local connections:
host    all         all         127.0.0.1/32          ident
```
**to:**
```
# IPv4 local connections:
host    all         all         127.0.0.1/32          md5
```

## Web server setup ##
The web frontend can be run on any web server capable of running Django applications (see http://docs.djangoproject.com/en/1.2/howto/deployment/), though the Django documentation recommends using Apache with the mod\_wsgi Python interface. Condor COPASI ships with a preset configuration for Apache and mod\_wsgi.

See http://docs.djangoproject.com/en/1.2/howto/deployment/modwsgi/ for general details on deployment. The steps involved in deployment using Ubuntu are listed below:

  * Ensure Apache and mod\_wsgi are installed and configured correctly
  * Create a directory to hold the web\_frontend folder
> `sudo mkdir /var/www/condor-copasi`
  * Copy web\_frontend folder to /var/www/condor-copasi
> `sudo cp -r path/to/web_frontend /var/www/condor-copasi`
  * Create a link to the Django admin media files in /var/www/condor-copasi
> `sudo ln -s  /usr/local/lib/python2.6/dist-packages/django/contrib/admin/media/ /var/www/condor-copasi/admin-media`
  * Configure apache site config
    * Under Ubuntu, this involves adding a new file to /etc/apache2/sites-available:
> > `sudo touch /etc/apache2/sites-available/condor-copasi`
    * Under other distributions, this may involve editing your httpd.conf file
    * **The configuration file contains three parts:
      * An alias for serving the static file style.css in the directory /static/
      * An alias for serving the static media for the admin site in the directory /admin/static/
      * A WSGIScript alias**
    * The example below assumes that we wish to serve the web frontend in the subfolder /condor-copasi
```
<VirtualHost *:80>

    Alias /condor-copasi/static/style.css /var/www/condor-copasi/web_frontend/static/style.css

    <Directory /var/www/condor-copasi/web_frontend/static>
        Order deny,allow
        Allow from all
    </Directory>

    Alias /condor-copasi/admin/static /var/www/condor-copasi/admin-media/

    <Directory /var/www/condor-copasi/admin-media>
        Order deny,allow
        Allow from all
    </Directory>

    WSGIScriptAlias /condor-copasi /var/www/condor-copasi/web_frontend/apache/django.wsgi

    <Directory /var/www/condor-copasi/web_frontend/apache>
        Order deny,allow
        Allow from all
    </Directory>

    ErrorLog /var/log/apache2/error.log

    # Possible values include: debug, info, notice, warn, error, crit,
    # alert, emerg.
    LogLevel debug

    CustomLog /var/log/apache2/access.log combined

</VirtualHost>
```
    * Under Ubuntu, the site must then be enabled:
```
sudo a2ensite condor-copasi
sudo service apache2 restart
```
    * Note that WSGIScriptAlias points to the file web\_frontend/apache/django.wsgi. This file is configured to ensure that the web\_frontend directory, and the directory above that (in this example condor-copasi) are both added to the python path, and shouldn't need editing unless you change the structure of code.

# Background Daemon #
The background daemon runs in addition to the web server, periodically checking the database for new jobs to submit to Condor, and checking the status of existing jobs on Condor queue.

## User and permissions setup ##
For security reasons, we recommend creating a new user to run the condor-copasi-daemon. E.g.:
```
adduser condor-copasi-user
```

This user must have permission to submit jobs to the Condor pool by running `condor_submit` and to check on the Condor queue status by running `condor_q`.

In addition to the new user, a new group should be created containing both the Condor COPASI daemon user and the web server user (e.g. condor-copasi-user and www-data). E.g.
```
sudo addgroup condor-copasi
sudo adduser www-data condor-copasi
sudo adduser condor-copasi-user condor-copasi
```

## Install the helper daemon ##
Copy the `condor-copasi-daemon` folder to an appropriate location. E.g.
```
sudo cp -r condor-copasi-daemon /opt
```
And mark condor-copasi-daemon as executable
```
sudo chmod +x /opt/condor-copasi-daemon.py
```

### Optional - create a script in /etc/init.d ###
For convenience, we can create a script in /etc/init.d to automatically set up the necessary environmental variables and run the background daemon as the appropriate user.

For example, save the following code in /etc/init.d/condor-copasi-daemon:
```
#!/bin/bash
### BEGIN INIT INFO
# Provides:          condor_copasi_daemon
# Required-Start:    $all
# Required-Stop:     $all
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Start condor copasi daemon
# Description:       Enable service provided by condor-coapsi daemon.
### END INIT INFO

#Fill in the appropriate locations in the PYTHONPATH below.
#Remember, must include the web_frontend folder, the folder above that, and the folder containing the daemon

#Replace condor-copas-user with the username you wish to run the condor-copasi-daemon as
sudo -u condor-copasi-user sh -c "export PYTHONPATH=$PYTHONPATH:/var/www/condor-copasi:/var/www/condor-copasi/web_frontend:/opt/condor-copasi-daemon; export DJANGO_SETTINGS_MODULE=web_frontend.settings; /opt/condor-copasi-daemon/condor-copasi-daemon.py $@"
```
And mark it as executable
```
sudo chmod +x /etc/init.d/condor-copasi-daemon
```

Under Ubuntu/Debian, the update-rc.d command can be used to automatically add the appropriate links so that the daemon automatically starts on boot:
```
sudo update-rc.d condor-copasi-daemon defaults
```

The daemon can now be started as follows:
```
sudo /etc/init.d/condor-copasi-daemon start
```
And stopped:
```
sudo /etc/init.d/condor-copasi-daemon stop
```

## Uploaded files directory ##
A directory must be created
Create a directory to hold uploaded files, and any automatically generated files. This directory must be readable and writeable by www-data and condor-copasi-user. The easiest way to achieve this is to set it as owned by the the condor-copasi group, and add rwx group permissions. We also add the SGID bit +s to ensure that all files and directories added retain the same group:
```
sudo mkdir /var/www/condor-copasi/user-files
shudo chgrp condor-copasi /var/www/condor-copasi/user-files
sudo chmod g+rws /var/www/condor-copasi/user-files
```

## Configure the Web Server Umask ##
Although we have now created a folder that has the appropriate group permissions, by default, any directories and files added by Apache will not be group writeable. To fix this, change the default umask for Apache to 002

On Debian-like systems, add the following line to /etc/apache2/envvars and restart Apache:
```
umask 002
```

Alternatively, on systems such as Slackware, edit the http startup script /etc/rc.d/rc.httpd, and add the following line:
```
umask 002
```

## Logging setup ##
The helper deamon must be able to write to a log file. We recommend creating a folder in /var/log that is writeable by the condor-copasi group. We can then configure Condor-COPASI to write logs to this directory (see below):
```
sudo mkdir /var/log/condor-copasi
sudo chgrp condor-copasi /var/log/condor-copasi
sudo chmod g+rws /var/log/condor-copasi
```


# Configure Condor-COPASI #
With the Web Frontend and Background Daemon installed and set up, Condor COPASI must now be configured. The configuration file `settings.py` is located in the `web_frontend` directory (in the example configuration above, this is located in `/var/www/condor-copasi`).
  * Set the database engine, database name, username and password. Host and port can be left blank if the database is running on the local server.
  * Change the secret key to a random string
  * Set SITE\_SUBFOLDER to the folder at which the web server is serving the web frontend, e.g. `'/condor-copasi/'` if the web frontend is being served at `www.example.com/condor-copasi`. If serving at the root folder, set to `'/'`
  * Set USER\_FILES\_DIR to the absolute path of the directory created earlier to store user-uploaded and automatically generated files. Remember, this must be readable and writeable by the web server and the background daemon.
  * Set LOG\_FILE to the absolute path of the log file we wish to write to. Remember, the background daemon must be able to write to this file and to the parent folder.
  * If necessary, change the logging level (options are logging.DEBUG to record all debugging messages and logging.ERROR to just record error messages).
  * Set COPASI\_BINARY\_DIR to the absolute path of the directory containing the CopasiSE binaries for all operating systems. The binaries should be named as follows:
```
CopasiSE.LINUX.INTEL
CopasiSE.LINUX.X86_64
CopasiSE.OSX.INTEL
CopasiSE.OSX.PPC
CopasiSE.WINDOWS.INTEL
CopasiSE.WINNT51.INTEL
```
Remember, the files in this directory must be executable by the condor-copasi-user!
  * Set COPASI\_LOCAL\_BINARY to the absolute path of the CopasiSE binary that is can be executed on the local machine. This must be executable by hte web server and background daemon
  * If necessary, change COMPLETED\_JOB\_DAYS, MIN\_CONDOR\_Q\_POOL\_TIME and IDEAL\_JOB\_TIME according to the descriptions given in settings.py

`settings.py` contains other, Django-specific settings that should not need to be changed.

## Populate the database ##
Assuming everything has been configured correctly, we can now create the required database tables, and populate them accordingly. This is done using `manage.py` in the `web_frontend` directory. Firstly though, the PYTHONPATH and DJANGO\_SETTINGS\_MODULE environmental variables must be set.

### Setting the Python path ###
Both the `web_frontend` folder, and it's parent folder must be added to the python path. For example, if web\_frontend is located in /var/www/condor-copasi:
```
export PYTHONPATH=$PYTHONPATH:/var/www/condor-copasi:/var/www/condor-copasi/web_frontend
```
And add the DJANGO\_SETTINGS\_MODULE environmental variable:
```
export DJANGO_SETTINGS_MODULE=web_frontend.settings
```
### Run manage.py ###
With the PYTHONPATH and DJANGO\_SETTINGS\_MODULE variables set, execute the following command in the web\_frontend directory:
```
python manage.py syncdb
```
This should prompt you to create an initial username and password, and will create the appropriate database tables.

At this point, if required, CREATE\_TABLE and DROP\_TABLE privileges for the condor copasi database user can be dropped.

# Start the background daemon #
With everything set up, we can now start the background daemon.

If you added the script in /etc/init.d, the daemon can be started by running:
```
sudo /etc/init.d/condor-copasi-daemon start
```

Otherwise, ensure that the Python path is correctly set, containing the following folders:
  * web\_frontend
  * The web\_frontend parent folder
  * The folder containing the background daemon

Also, the DJANGO\_SETTINGS\_MODULE environmental variable must be set to web\_frontend.settings

For example:
```
export PYTHONPATH=$PYTHONPATH:/var/www/condor-copasi:/var/www/condor-copasi/web_frontend:/TODO-path/to/bg/daemon
export DJANGO_SETTINGS_MODULE=web_frontend.settings
```
And start the daemon:
```
/path/to/condor-copasi-daemon.py start
```
The daemon can then be stopped:
```
/path/to/condor-copasi-daemon.py stop
```

# Start Apache #
If Apache isn't already running, start it. Otherwise, reload it to load the new configuration

```
sudo service apache2 start
```
or
```
sudo service apache2 restart
```

# Optional -- condor\_submit username configuration #
By default, Condor-COPASI will submit jobs to the Condor pool with the user running the condor-copasi-daemon as the owner.

Condor-COPASI can optionally submit to the condor pool using the username of the Condor-COPASI user as the owner. To enable this feature, change `SUBMIT_WITH_USERNAMES` in settings.py to `True`.

For this feature to work, the Condor-COPASI usernames must have user accounts on the server running the condor-copasi-daemon. **In addition, the user running condor-copasi-daemon must be able to use `sudo -u username` to execute the following commands as user username, without being prompted for a password:**
```
cp
mv
chmod
chown
rm
condor_submit
condor_rm
```

To achieve this, we recommend creating a new group condor-copasi-submitters
```
addgroup condor-copasi-submitters
```

And then adding the following lines to /etc/sudoers. (Note, under Ubuntu, and possibly other systems, /etc/sudoers must be edited by using the command `visudo`):
```
#Condor COPASI config
Cmnd_Alias CONDOR_COPASI_COMMANDS = /bin/cp *, /bin/mv *, /bin/chgrp *, /bin/chmod g+w *, /bin/rm *, /usr/bin/condor_submit *, usr/bin/condor_rm *
condor-copasi-user ALL = (%condor-copasi-submitters) NOPASSWD:NOEXEC: CONDOR_COPASI_COMMANDS
```
This allows the user condor-copasi-user to run the commands listed in `CONDOR_COPASI_COMMANDS` as any user in the group condor-copasi-submitters without being prompted for a password.

When new users are added to the system, a corresponding user account with the same username must be created on the system. This can be performed as follows:
```
useradd -G condor-copasi,condor-copasi-submitters some_username
```
This creates a user with username some\_username which is a member of the condor-copasi and condor-copasi-submitters groups (both are necessary). Note that no corresponding entry is added to /etc/shadow, which should mean that the only way to gain access to the account is via the `sudo` or `su` commands.