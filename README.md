noWorkflow
==========

Supporting infrastructure to run scientific experiments without a scientific workflow management system.

Copyright (c) 2013 Universidade Federal Fluminense (UFF).
Copyright (c) 2013 Polytechnic Institute of New York University.
All rights reserved.

The noWorkflow project aims at allowing scientists to benefit from provenance data analysis even when they don't use a workflow system. Also, the goal is to allow them to avoid using naming conventions to store files originated in previous executions. Currently, when this is not done, the result and intermediate files are overwritten by every new execution of the pipeline.

noWorkflow was develop in Python and it currently is able to capture provenance of Python scripts using Software Engineering techniques such as abstract syntax tree (AST) analysis, reflection, and profiling, to collect provenance without the need of a version control system or any other environment. 

Installing and using noWorkflow is simple and easy. Please check our installation and basic usage guidelines below. 

Team
-----------

The noWorkflow team is composed by researchers from Universidade Federal Fluminense (UFF) in Brazil and New York University (NYU), in the USA.

* Leonardo Murta (UFF)    
* Vanessa Braganholo (UFF)
* Juliana Freire (NYU)
* Fernando Chirigati (NYU)
* David Koop (NYU)

Quick Installation
------------------

To install noWorkflow, you should follow these basic instructions: 

Precondition: Git (just to clone our repository) and Python
```bash
$ git clone git@github.com:gems-uff/noworkflow.git
```
```bash
$ cd noworkflow/capture
```
```bash
$ ./setup.py install
```

This is installs noWorkflow on your system. 

Basic Usage
-----------

noWorkflow is transparent in the sense that it requires neither changes to the script, nor any laborious configuration. Run 
```bash
now --help
```
to learn the usage options.

To run noWorkflow with a script called *simulation.py* with input data *data1.dat* and *data2.dat*, you should run  
```bash
now run -v simulation.py data1.dat data2.dat
```
The *-v* option turns the verbose mode on, so that noWorkflow gives you feedback on the steps taken by the tool. The output, in this case, is similar to what follows.

```bash
$ now run -v simulation.py data1.dat data2.dat
[now] removing noWorkflow boilerplate
[now] setting up local provenance store
[now] collecting definition provenance
[now]   registering user-defined functions
[now] collecting deployment provenance
[now]   registering environment attributes
[now]   searching for module dependencies
[now]   registering provenance from 703 modules
[now] collecting execution provenance
[now]   executing the script
[now] the execution of trial 1 finished successfully
```
Each new run produces a different trial that will be stored with a sequential identification number in the relational database.

Verifying the module dependencies is a time consuming step, and scientists can bypass this step by using the *-b* flag if they know that no library or source code has changed. The current trial then inherits the module dependencies of the previous one. 

To list all trials, just run 

```bash
now list
```
Assuming we run the experiment again and then run \texttt{now list}, the output would be as follows.

```bash
$ now list
[now] trials available in the provenance store:
  Trial 1: simulation.py data1.dat data2.dat
         with code hash aa49daae4ae8084af3602db436e895f08f14aba8
         ran from 2014-03-04 13:10:34.595995 to 2014-03-04 13:11:33.793083
  Trial 2: simulation.py data1.dat data2.dat
         with code hash aa49daae4ae8084af3602db436e895f08f14aba8
         ran from 2014-03-04 17:59:02.917920 to 2014-03-04 18:00:10.383637
```

To look at details of an specific trial, use 
```bash
now show
```
This command has several options, such as *-m* to show module dependencies; *-d* to show function definitions; *-e* to show the environment context; *-a* to show function activations; and *-f* to show file accesses. 

Running 
```bash
now show -a 1
```
would show details of trial 1. Notice that the function name is preceded by the line number where the call was activated. 

```bash
$ now show -a 1 
[now] trial information:
  Id: 1
  Inherited Id: None
  Script: simulation.py
  Code hash: aa49daae4ae8084af3602db436e895f08f14aba8
  Start: 2014-03-04 13:10:34.595995
  Finish: 2014-03-04 13:11:33.793083
[now] this trial has the following function activation graph:
  42: run_simulation (2014-03-04 13:11:30.969055 - 
                                2014-03-04 13:11:32.978796)
      Arguments: data_b = 'data2.dat', data_a = 'data1.dat'
      Globals: wait = 2
      Return value: [['0.0', '0.6'], ['1.0', '0.0'], ['1.0', '0.0'], 
      ...
```
The remaining options of noWorkflow are *diff* and *export*. The *diff* option compares two trials, and the *export* option exports provenance data of a given trial to Prolog facts, so inference queries can be run over the database.  

We have also a graph visualization implemented in Java, named noWorkflowVis, which connects to noWorkflow database and allows interactive analysis. 

Included software
-----------------

Parts of the following software were used by noWorkflow directly or in an adapted form:

The Python Debugger
Copyright (c) 2001-2013 Python Software Foundation.
All Rights Reserved.

License Terms
-------------

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

