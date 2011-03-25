import os
from web_frontend.condor_copasi_db import models
from web_frontend.copasi.model import CopasiModel

def prepare_data(jobs):
    output = ""
    for job, variation in jobs:
        model = CopasiModel(job.get_filename())
        
        results = model.get_so_results()
        
        for result in results:
            output += "['" + result['name'] + "_max'," + str(variation) + "," + result['max_result'] + "],\n"
            output += "['" + result['name'] + "_min'," + str(variation) + "," + result['min_result'] + "],\n"

    return output
