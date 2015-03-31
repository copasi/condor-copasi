# Introduction #
Condor-COPASI is a web-based interface for integrating [COPASI](http://www.copasi.org) with the [Condor](http://www.cs.wisc.edu/condor/) High Throughput Computing (HTC) environment. It provides COPASI users with a simple environment for utilising the power of High Throughput Computing, without requiring any technical knowledge of Condor of other HTC tools.

Condor-COPASI is written in Python 2.6 as a [Django 1.2](http://docs.djangoproject.com/en/dev/releases/1.2/) application. It is free, open source software, and distributed under the terms of the [Artistic License 2.0](http://www.perlfoundation.org/artistic_license_2_0)

Condor-COPASI was developed at the [University of Manchester](http://www.manchester.ac.uk).

# Instruction Manual #
A full instruction manual on how to use Condor-COPASI is [available on the Wiki](Instructions.md).

# Usage #
Condor-COPASI is able to perform a number of predefined tasks. Each task requires that the user set up a model using COPASI, and upload the COPASI model file to the web server.

## Global Sensitivity Analysis ##
Condor-COPASI is able to automate and parallelize the global sensitivity analysis procedure, as described in the paper [A new strategy for assessing sensitivities in biochemical models](http://www.ncbi.nlm.nih.gov/pubmed/18632455).

## Stochastic Simulation ##
Condor-COPASI provides an easy to use environment for running multiple stochastic simulations. The simulations are automatically split into parallel jobs and run on the Condor pool. Once completed, the results are automatically collated, and particle number means and standard deviations calculated. Plots of this processed data can be obtained through the web interface.

## Parallel Scan ##
Condor-COPASI will take a Parameter Scan set up in COPASI and automatically split it into smaller chunks. In cases where multiple scan tasks/repeats are nested, only the the top-level scan will be split. The smaller chunks are then submitted to the Condor pool, and the results collated as if the scan task had been run on a single machine.

## Optimization Repeat ##
This feature runs the optimization task a set number of times, splitting into multiple parallel jobs where necessary. The best value from the multiple number of runs is extracted, though the results of every optimization run are available for download too if necessary.


## Parameter Estimation Repeat ##
Similar to the optimization repeat task above, this feature runs the parameter estimation task multiple times, splitting into parallel jobs where necessary. The best set of parameters values are then selected, though the results of each parameter estimation run are available to download if necessary.


## Optimization Repeat with Different Alogorithms ##
This feature runs the optimization task using different algorithms. Each algorithm runs a separate parallel job. Condor-COPASI will automatically determine which algorithm(s) found the best result.

# Examples #
### Screenshots: ###
![http://condor-copasi.googlecode.com/svn/wiki/images/stochastic_1.png](http://condor-copasi.googlecode.com/svn/wiki/images/stochastic_1.png)
![http://condor-copasi.googlecode.com/svn/wiki/images/stochastic_2.png](http://condor-copasi.googlecode.com/svn/wiki/images/stochastic_2.png)