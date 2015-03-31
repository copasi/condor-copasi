This page gives a few hints and tips on solving problems. It is not comprehensive, though should guide you in the right direction



# The model file could not be uploaded to Condor-COPASI #
Condor-COPASI will reject COPASI model files unless a number of criteria have been met:
  * The model was saved using a supported version of COPASI (Build 33 or Build 34)
  * The model prepared according to the guidelines set out by the task you are trying to perform
    * Each task requires that the COPASI model be prepared in a certain way
    * For full information, refer to the Wiki page on [submitting tasks](TaskTypes.md).

If you are sure the model file is correctly configured, it is possible that there is a bug in the Condor-COPASI software. Consider [filing a bug report](#Reporting_Bugs.md).

# The model file was uploaded, but the task failed before any jobs were submitted to Condor #
If your job failed before any Condor jobs were submitted, the most likely cause is that the COPASI model was not set up correctly. Check the guidelines [here](#The_model_file_could_not_be_uploaded_to_Condor-COPASI.md).

Also check that, when running a job that performs multiple repeats of a certain task, you can successfully run the task on your local machine.

If you still can't get the job to run, you may have found a bug in Condor-COPASI. Consider [filing a bug report](#Reporting_Bugs.md).

# Jobs were submitted to Condor, but the task still failed #
In this situation, examining the log files for the Condor jobs should give information about why the job(s) failed.

## Understanding the automatically generated files ##
Condor-COPASI automatically generates a number of files associated with each Job submitted to condor. The can be obtained by downloading the `.tar.bz2` file of the results directory.

For each job submitted to Condor, the associated files are named as follows:
| **Filename** | **Description** |
|:-------------|:----------------|
|`auto_condor_0.job`| The Condor job specification file. |
|`auto_copasi_0.cps` | The copasi model file associated with the Condor job|
|`auto_copasi_0.cps.log` | The Condor log file associated with  the Condor job |
|`auto_copasi_0.cps.out` | The stdout from the COPASI instance running on the Condor job. This is normally empty |
|`auto_copasi_0.cps.err` | The stderror from the COPASI instance running on the Condor job. **This is normally a good place to look to diagnose problems**.|

Any output files produced by COPASI are usually saved in files named `0_out.txt`, `1_out.txt` etc.

The file `raw_results.txt` contains the collated, unprocessed output from all the Condor jobs, while `results.txt` contains processed results.

The file `results.txt` contains the processed output.

# Reporting Bugs #
If you think you have found a bug in Condor-COPASI, please report it using the [Issue Tracker](http://code.google.com/p/condor-copasi/issues/list). Include as much information as possible about the problem, and if relevant, include the COPASI model file as an attachment.