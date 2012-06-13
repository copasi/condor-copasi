#!/usr/bin/env python
 
#Script adapted from example by Sander Marechal, released into public domain
#Taken from http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/
 
import sys, time
from daemon import Daemon
from web_frontend import settings
import background_run
class MyDaemon(Daemon):
    def run(self):
        while True:
            min_repeat_time = settings.MIN_CONDOR_Q_POLL_TIME * 60
            start_time = time.time()
            
            background_run.run()
            
            finish_time = time.time()
            
            difference = finish_time - start_time
            if difference < min_repeat_time:
                time.sleep(min_repeat_time - difference)
 
if __name__ == "__main__":
    daemon = MyDaemon('/tmp/Condor-COPASI.pid')
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        else:
            print "Unknown command"
            sys.exit(2)
        sys.exit(0)
    else:
        print "usage: %s start|stop|restart" % sys.argv[0]
        sys.exit(2)
