# Introduction #
Condor-COPASI is a web-based interface for integrating [COPASI](http://www.copasi.org) with the [Condor](http://www.cs.wisc.edu/condor/) High Throughput Computing (HTC) environment. It provides COPASI users with a simple environment for utilising the power of High Throughput Computing, without requiring any technical knowledge of Condor of other HTC tools.



## Log In ##
Before you can access Condor-COPASI you must have a user account created. Speak to you System Administrator for further details.

If you have a user account, log in by clicking on the link in the top-right.

## Submit new jobs ##
Condor-COPASI is able to perform a number of predefined tasks. Each task requires that the user set up a model using COPASI, and upload the COPASI model file to the web server.

To submit a new job, click 'Tasks' on the sidebar on the left, and select from the following tasks types. Click on the task name for more information on how the task operates, and how to prepare files.

#### [Global Sensitivity Analysis / Sensitivity Optimization](TaskTypes#Global_Sensitivity_Analysis_/_Sensitivity_Optimization.md) ####
Condor-COPASI is able to automate and parallelize the global sensitivity analysis procedure, as described in the paper [A new strategy for assessing sensitivities in biochemical models](http://www.ncbi.nlm.nih.gov/pubmed/18632455).

#### [Stochastic Simulation](TaskTypes#Stochastic_Simulation.md) ####
Condor-COPASI provides an easy to use environment for running multiple stochastic simulations. The simulations are automatically split into parallel jobs and run on the Condor pool. Once completed, the results are automatically collated, and particle number means and standard deviations calculated. Plots of this processed data can be obtained through the web interface.

#### [Parallel Scan](TaskTypes#Parallel_Scan.md) ####
Condor-COPASI will take a Parameter Scan set up in COPASI and automatically split it into smaller chunks. In cases where multiple scan tasks/repeats are nested, only the the top-level scan will be split. The smaller chunks are then submitted to the Condor pool, and the results collated as if the scan task had been run on a single machine.

#### [Optimization Repeat](TaskTypes#Optimization_Repeat.md) ####
This feature runs the optimization task a set number of times, splitting into multiple parallel jobs where necessary. The best value from the multiple number of runs is extracted, though the results of every optimization run are available for download too if necessary.


#### [Parameter Estimation Repeat](TaskTypes#Parameter_Estimation_Repeat.md) ####
Similar to the optimization repeat task above, this feature runs the parameter estimation task multiple times, splitting into parallel jobs where necessary. The best set of parameters values are then selected, though the results of each parameter estimation run are available to download if necessary.


#### [Optimization Repeat with Different Alogorithms](TaskTypes#Optimization_Repeat_with_Different_Alogorithms.md) ####
This feature runs the optimization task using different algorithms. Each algorithm runs a separate parallel job. Condor-COPASI will automatically determine which algorithm(s) found the best result.


## Monitor the status of submitted jobs ##

After you have submitted a job, you can monitor the status by clicking 'My Account' on the left sidebar. Jobs newly submitted, and those running on Condor are listed under 'Running Jobs'. Once a job has completed, it is listed under 'Completed Jobs', and if any errors occurred when running the job, it will be listed under 'Errors'

Click on the name of a job for further details about it's status, and to view any results generated.

The status of jobs on the system is refreshed approximately every two minutes.

### Running Jobs ###
Jobs submitted will have a status as one of the following:

| **Status** | **Description**|
|:-----------|:---------------|
| **New, waiting for Condor submission** | The job was successfully uploaded to Condor-COPASI, and is awaiting submission to the Condor pool |
| **Submitted to Condor** | The job was successfully parallelized and a number of Condor jobs were submitted to the pool. The status of these Condor jobs can be viewed by clicking on the job name |
| **Finished, processing data on Condor** | Currently only used for the Stochastic Simulation task. All simulations have completed, and the output data is being processed. This step can be computationally intensive, and so is being run on the Condor pool as a single Condor job.|
| **Finished, processing data locally** | All simulations/optimizations have completed, and the results are being processed on the server |

The status of individual jobs running on the Condor pool is displayed on the Job Details page as **Condor Status**. The status of individual Condor jobs will either be:
  * **Idle** -- in a queue, waiting to be executed
  * **Running** -- being executed on a remote machine
  * **Held** -- an error occurred while trying to run the job on a remote machine
  * **Finished** -- the Condor job successfully finished running on a remote machine

### Completed Jobs ###
If a job has successfully completed, it will be listed under 'Completed Jobs'. Depending on the type of task performed, the results can be viewed in the browser, or downloaded as a tab-separated text file.

The directory containing all automatically generated files, and output files can also be downloaded. For details on what the various files are, see the [Troubleshooting](Troubleshooting#Understanding_the_automatically_generated_files.md) Wiki page.

The output of the Stochastic Simulation task -- particle number means, and optionally, shaded areas showing the standard deviations -- can be plotted in the browser, and the plot images downloaded in various file formats. These plots are generated using Python's matplotlib library.

### Failed Jobs ###
If an error occurs, either automatically generating the files to submit to Condor, or while running a job on Condor, the job will be marked as **Error**, and listed under 'Errors'. To view more details about the error, click the job name for more information.

See the [Troubleshooting](Troubleshooting.md) Wiki page for more details about diagnosing and fixing errors.