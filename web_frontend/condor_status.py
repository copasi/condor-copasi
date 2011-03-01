#Script to read and process the output of the condor_status command

import subprocess, re, os, pickle, datetime
from web_frontend import settings

def run():
    p = subprocess.Popen(['condor_status'], stdout=subprocess.PIPE)

    output = p.communicate()[0].splitlines()

    #Process the output, looking for the following line:
    #Total   110    29      56        25       0          0        0

    #Where the numbers correspond to:
    #Total Owner Claimed Unclaimed Matched Preempting Backfill

    all_status_string = r'\s+Total\s+(?P<total>[0-9]+)\s+(?P<owner>[0-9]+)\s+(?P<claimed>[0-9]+)\s+(?P<unclaimed>[0-9]+)\s+(?P<matched>[0-9]+)\s+(?P<preempting>[0-9]+)\s+(?P<backfill>[0-9]+)\s*'

    all_status_re = re.compile(all_status_string)

    for line in output:
        match = all_status_re.match(line)
        if match:
            #Write the status and current time to the file condor_status in the user files dir using pickle
            d = match.groupdict()
            status = {
                'total' : int(d['total']),
                'owner' : int(d['owner']),
                'claimed' : int(d['claimed']),
                'unclaimed' : int(d['unclaimed']),
                'matched' : int(d['matched']),
                'preempting' : int(d['preempting']),
                'backfill' : int(d['backfill']),
                'time' : datetime.datetime.today()
            }
            pickle_file = open(os.path.join(settings.USER_FILES_DIR, 'condor_status.pickle'), 'w')
            pickle.dump(status, pickle_file)
            pickle_file.close()
            break
