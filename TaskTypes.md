# Condor-COPASI Tasks #

This page gives detailed information each of the tasks Condor-COPASI can perform, and details on how to prepare COPASI models for each task.

All COPASI models should be saved using Build 33 or Build 34 of COPASI.

### Rank ###
As of version 0.4, all jobs can now be assigned a custom rank. The rank expression allows for jobs to prioritize certain machines when being assigned. For full details see the [Condor manual](http://research.cs.wisc.edu/condor/manual/v7.4/4_1Condor_s_ClassAd.html#classad-reference). **Note that an invalid rank expression can result in Condor jobs failing to submit, and the task failing**.


### Task types ###


## Global Sensitivity Analysis / Sensitivity Optimization ##
### Introduction ###
Condor-COPASI is able to automate and parallelize the global sensitivity analysis procedure, as described in the paper [A new strategy for assessing sensitivities in biochemical models](http://www.ncbi.nlm.nih.gov/pubmed/18632455).


### Model preparation ###

All parameters that you wish to vary should be added to the **Optimization** task, with initial values appropriate upper and lower bounds set.

An appropriate optimization method, such as 'Particle Swarm' should also be set.

In addition, the parameter you wish to calculate the sensitivities against (for example, the flux through a reaction, or the concentration of a metabolite) should be set as the Function the **Sensitivities** task as a Single Object.

### Parallelization ###
Condor-COPASI will split this task up into two Condor jobs per parameter specified in the Optimization task -- one job to minimize the sensitivity and one job to maximise it.

### Output ###
Condor-COPASI produces a tab-separated text file containing, for each parameter in the Optimization task, the maximum and minimum values found for the parameter specified in the Sensitivities task. In addition, information is returned on the amount of CPU time taken per optimization run, and the number of function evaluations taken by the optimization algorithm.

### Example File ###
[Click here](http://condor-copasi.googlecode.com/svn/wiki/examples/SO%20Test%20(MAPK).cps) to download an example model that has been configured to run the Sensitivity Optimization task.


## Stochastic Simulation ##
### Introduction ###
Condor-COPASI provides an easy to use environment for running multiple stochastic simulations. The simulations are automatically split into parallel jobs and run on the Condor pool. Once completed, the results are automatically collated, and particle number means and standard deviations calculated.

### Model preparation ###
The model should be prepared as if a single Time Course task were to run. A stochastic or hybrid algorithm should be selected, and all other parameters for the Time Course task set as desired.

### Parallelization ###
Condor-COPASI will automatically split this task into a number of sub-jobs, each of which can be executed in parallel on the Condor pool. The number of repeats performed for each Condor job will depend on the time taken to simulate a single run of the Time Course task. Condor-COPASI aims to make each Stochastic Simulation job submitted to Condor run for a constant length of time. If a single stochastic run of the Time Course task takes longer than this time, then a single stochastic run will be performed for each Condor job.

Typically, the running time of each job is set to be approximately equal to 20 minutes, but can be adjusted by the System Administrator. Note that, due to differences in the processing power of different machines in the Condor pool, the running time of individual jobs may vary considerably.

### Output ###
Condor-COPASI will automatically calculate particle number means and standard deviations for all species in the model at each time point. These are available to download as a tab-separated text file by clicking 'Download the results', and can be plotted by clicking 'View the results'.

The output produced for each individual Time Course repeat is also available in the file `raw_results.txt`. This file is available by clicking 'Download results directory'.

### Example File ###
[Click here](http://condor-copasi.googlecode.com/svn/wiki/examples/stochastic_test.cps) to download an example model configured to run the Stochastic Simulation task.

## Parallel Scan ##
### Introduction ###
Condor-COPASI will take a Parameter Scan set up in COPASI and automatically split it into smaller chunks to be run in parallel. In cases where multiple scan tasks/repeats are nested, only the the top-level scan will be split. The smaller chunks are then submitted to the Condor pool, and the results collated as if the scan task had been run on a single machine.

### Model preparation ###
The **Parameter Scan** task in COPASI should be set up as though the scan were to take place on the local machine. Unlike the other Condor-COPASI tasks, Parallel Scan requires that a report be set for the Parameter Scan task. This report must contain output you wish to generate.


### Parallelization ###
Like the Stochastic Simulation task, Condor-COPASI aims to split the Scan task into smaller jobs that can be run in parallel on the Condor pool, aiming to make each smaller job run for a constant length of time. If nested scans or repeats are set, only the top-level scan or repeat can be split. This should be taken into account when deciding on the order of the nested items.

### Output ###
Output is generated according to the report set for the Parameter Scan task. **You must set this up manually using COPASI**. The output is collated as though the Parameter Scan task had been run on a single machine.

### Example File ###
[Click here](http://condor-copasi.googlecode.com/svn/wiki/examples/parallel_scan.cps) to download an example model configured to run the Parallel Scan task.

## Optimization Repeat ##
### Introduction ###
This feature runs the optimization task a set number of times, splitting into multiple parallel jobs where necessary. The best value from the multiple number of runs is extracted, though the results of every optimization run are available for download too if necessary.

### Model preparation ###
The Optimization task should be set up as though a single optimization was to take place on the local machine. All parameters should be set as necessary.
### Parallelization ###
Like the Stochastic Simulation task, Condor-COPASI aims to split the Optimization Repeat task into a number of small jobs, each of which will be executed in parallel on the Condor pool. The number of repeats per job depends on the time taken to perform a single repeat.

### Output ###
Condor-COPASI will automatically create a report for each Optimization repeat containing the best optimization value and the values of all variable parameters. Condor-COPASI will then search the output files to find the best optimization value and associated parameter values.

The output from each optimization repeat is available in the file `raw_results.txt`, which can be obtained by downloading the results directory.
### Example File ###
[Click here](http://condor-copasi.googlecode.com/svn/wiki/examples/optimization_repeat.cps) to download an example model configured to run the Optimization Repeat task.

## Parameter Estimation Repeat ##
### Introduction ###
Similar to the optimization repeat task above, this feature runs the parameter estimation task multiple times, splitting into parallel jobs where necessary. The best set of parameters values are then selected, though the results of each parameter estimation run are available to download if necessary.

### Model preparation ###
The **Parameter Estimation** task should be set up as though a single parameter estimation was to take place on the local machine. All parameters should be set as necessary, and any experimental data imported. Note that, when importing experimental data, all data files should be located in the same directory on the local machine as the model file.

### Parallelization ###
Like the Stochastic Simulation task, Condor-COPASI aims to split the Parameter Estimation Repeat task into a number of small jobs, each of which will be executed in parallel on the Condor pool. The number of repeats per job depends on the time taken to perform a single repeat.

### Output ###
Condor-COPASI will automatically create a report for each Parameter Estimation repeat containing the best objective value value and the values of all variable parameters. After all repeats have finished, Condor-COPASI will search the output files to find the best objective value and associated parameter values.

Alternatively, by checking the appropriate box when submitting the task, a custom report can be used. This must be created manually using COPASI, and set for the Parameter Estimation task. Condor-COPASI will try to process the output from any custom report; for this to succeed, the following fields must be placed (in order) at the end of the report:
  * `TaskList[ParameterEstimation].(Problem)Parameter Estimation.Best Parameters`
  * `TaskList[ParameterEstimation].(Problem)Parameter Estimation.Best Value`
  * `TaskList[ParameterEstimation].(Problem)Parameter Estimation.(Timer)CPU Time`
  * `TaskList[ParameterEstimation].(Problem)Parameter Estimation.Function Evaluations`

The output from each optimization repeat is available in the file `raw_results.txt`, which can be obtained by downloading the results directory.

### Example File ###
[Click here](http://condor-copasi.googlecode.com/svn/wiki/examples/KinMMFit.cps) to download an example model configured to run the Parameter Estimation task, and the [associated data file](http://condor-copasi.googlecode.com/svn/wiki/examples/KinMMFitData.zip).

## Optimization Repeat with Different Alogorithms ##
### Introduction ###
This feature runs the optimization task using different algorithms. Each algorithm runs as a separate parallel job. Condor-COPASI will automatically determine which algorithm(s) found the best result.

### Model preparation ###
The **Optimization** task should be configured as though a single optimization was to take place on the local machine. All parameters should be set as desired, except for those relating to the optimization algorithm, which will be set when submitting the model to Condor-COPASI.

### Parallelization ###
Condor-COPASI creates a separate job to run on the Condor pool for each optimization algorithm.

### Output ###
Condor-COPASI will automatically create a report for the Optimization task containing the best optimization value, along with any associated variable parameter values.

After each optimization algorithm has run on the Condor pool, Condor-COPASI will go through the output and find the best value(s) and associated variable parameter values, and will list these alongside the name of the algorithm(s) which found the result.

The output for each optimization algorithm is available by downloading the results directory. Each output is named according to the name of the algorithm, e.g. `particle_swarm_out.txt`

### Example File ###
[Click here](http://condor-copasi.googlecode.com/svn/wiki/examples/multiple_optimizations.cps) to download an example model configured to run the Multiple Optimizations with Different Algorithms task.