noWorkflow
==========

Copyright (c) 2016 Universidade Federal Fluminense (UFF).
Copyright (c) 2016 Polytechnic Institute of New York University.
All rights reserved.

The noWorkflow project aims at allowing scientists to benefit from provenance data analysis even when they don't use a workflow system. Also, the goal is to allow them to avoid using naming conventions to store files originated in previous executions. Currently, when this is not done, the result and intermediate files are overwritten by every new execution of the pipeline.

noWorkflow was developed in Python and it currently is able to capture provenance of Python scripts using Software Engineering techniques such as abstract syntax tree (AST) analysis, reflection, and profiling, to collect provenance without the need of a version control system or any other environment.

Installing and using noWorkflow is simple and easy. Please check our installation and basic usage guidelines below, and the [tutorial videos at our Wiki page](https://github.com/gems-uff/noworkflow/wiki/Videos).

noWorkflow supports Python 2.7 and Python 3.5.

Team
----

The noWorkflow team is composed by researchers from Universidade Federal Fluminense (UFF) in Brazil and New York University (NYU), in the USA.

* Vanessa Braganholo (UFF)
* Fernando Chirigati (NYU)
* Juliana Freire (NYU)
* David Koop (NYU)
* Leonardo Murta (UFF)
* João Felipe Pimentel (UFF)

Publications
------------

* [MURTA, L. G. P.; BRAGANHOLO, V.; CHIRIGATI, F. S.; KOOP, D.; FREIRE, J.; noWorkflow: Capturing and Analyzing Provenance of Scripts. In: International Provenance and Annotation Workshop (IPAW), 2014, Cologne, Germany.] (https://github.com/gems-uff/noworkflow/raw/master/docs/ipaw2014.pdf)
* [PIMENTEL, J. F. N.; FREIRE, J.; MURTA, L. G. P.; BRAGANHOLO, V.; Collecting and Analyzing Provenance on Interactive Notebooks: when IPython meets noWorkflow. In: Theory and Practice of Provenance (TaPP), 2015, Edinburgh, Scotland.] (https://github.com/gems-uff/noworkflow/raw/master/docs/tapp2015.pdf)

Quick Installation
------------------

To install noWorkflow, you should follow these basic instructions:

If you have pip, just run:
```bash
$ pip install noworkflow[all]
```
This installs noWorkflow, PyPosAST, SQLAlchemy, python-future, flask, IPython, Jupyter and PySWIP.
The only requirements for running noWorkflow are PyPosAST, SQLAlchemy and python-future. The other libraries are only used for provenance analysis.

If you only want to install noWorkflow, PyPosAST, SQLAlchemy and python-future please do:
```bash
$ pip install noworkflow
```

If you do not have pip, but already have Git (to clone our repository) and Python:
```bash
$ git clone git@github.com:gems-uff/noworkflow.git
$ cd noworkflow/capture
$ python setup.py install
```
This installs noWorkflow on your system. It will download the dependencies from PyPI

Upgrade
-------

To upgrade the version of a previously installed noWorkflow using pip, you should run the following command:

```bash
$ pip install --upgrade noworkflow[all]
```

Basic Usage
-----------

noWorkflow is transparent in the sense that it requires neither changes to the script, nor any laborious configuration. Run
```bash
$ now --help
```
to learn the usage options.

noWorkflow comes with a demonstration project. To extract it, you should run
```bash
$ now demo 1
$ cd demo1
```

To run noWorkflow with the demo script called *simulation.py* with input data *data1.dat* and *data2.dat*, you should run
```bash
$ now run -v simulation.py data1.dat data2.dat
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
[now]   registering provenance from 1369 modules
[now] collecting execution provenance
[now]   executing the script
[now] the execution of trial 10 finished successfully
```
Each new run produces a different trial that will be stored with a sequential identification number in the relational database.

Verifying the module dependencies is a time consuming step, and scientists can bypass this step by using the *-b* flag if they know that no library or source code has changed. The current trial then inherits the module dependencies of the previous one.

It is possible to collect more information than what is collected by default, such as variable usages and dependencias.
To perform a dynamic program slicing and capture those information, just run
```bash
$ now run -e Tracer simulation.py data1.dat data2.dat
```

To list all trials, just run

```bash
$ now list
```
Assuming we run the experiment again and then run `now list`, the output would be as follows. Note that 9 trials were extracted from the demonstration.

```bash
$ now list
[now] trials available in the provenance store:
  Trial 1: simulation.py data1.dat data2.dat
           with code hash 9f13b9b35f5215a82f9b12f9f32238dddf02646a
           ran from 2016-01-13 19:06:53.740877 to 2016-01-13 19:07:13.250622
  Trial 2: simulation_complete.py 
           with code hash 705471548f6253da20302333f0a3f79059d79e40
           ran from 2016-01-13 19:07:13.583000 to 2016-01-13 19:07:39.225553
  Trial 3: simulation.py data1.dat data2.dat
           with code hash ba58136d9eac420930d352c127a78988c226dff8
           ran from 2016-01-13 19:07:39.530637 to 2016-01-13 19:07:58.513666
  Trial 4: simulation.py data2.dat data1.dat
           with code hash 9f13b9b35f5215a82f9b12f9f32238dddf02646a
           ran from 2016-01-13 19:07:58.953236 to 2016-01-13 19:08:20.822072
  Trial 5: simulation.py <restore 3>
           with code hash 16d9ba96a1dfa97d26fd5009b19f872a4fa5cb57
           ran from 2016-01-13 19:08:21.146970 to None
  Trial 6: simulation.py data1.dat data2.dat
           with code hash ba58136d9eac420930d352c127a78988c226dff8
           ran from 2016-01-13 19:08:42.827121 to 2016-01-13 19:09:02.137061
  Trial 7: simulation.py data1.dat data2.dat
           with code hash 16d9ba96a1dfa97d26fd5009b19f872a4fa5cb57
           ran from 2016-01-13 19:09:02.430346 to None
  Trial 8: simulation_complete.py 
           with code hash 705471548f6253da20302333f0a3f79059d79e40
           ran from 2016-01-13 19:09:22.637177 to 2016-01-13 19:09:46.327150
  Trial 9: simulation.py data1.dat data2.dat
           with code hash 9f13b9b35f5215a82f9b12f9f32238dddf02646a
           ran from 2016-01-13 19:09:46.711818 to 2016-01-13 19:10:10.998172
  Trial 10: simulation.py data1.dat data2.dat
            with code hash 9f13b9b35f5215a82f9b12f9f32238dddf02646a
            ran from 2016-01-13 19:10:21.587332 to 2016-01-13 19:10:41.900566
  Trial 11: simulation.py data1.dat data2.dat
            with code hash 9f13b9b35f5215a82f9b12f9f32238dddf02646a
            ran from 2016-01-13 19:11:00.033094 to 2016-01-13 19:11:25.632197
```

To look at details of an specific trial, use
```bash
$ now show [trial]
```
This command has several options, such as *-m* to show module dependencies; *-d* to show function definitions; *-e* to show the environment context; *-a* to show function activations; and *-f* to show file accesses.

Running
```bash
$ now show -a 1
```
would show details of trial 1. Notice that the function name is preceded by the line number where the call was activated.

```bash
$ now show -a 1
[now] trial information:
  Id: 1
  Inherited Id: None
  Script: simulation.py
  Code hash: 9f13b9b35f5215a82f9b12f9f32238dddf02646a
  Start: 2016-01-13 19:06:53.740877
  Finish: 2016-01-13 19:07:13.250622
[now] this trial has the following function activation graph:
  54: /home/joao/demotest/demo1/simulation.py (2016-01-13 19:07:12.135981 - 2016-01-13 19:07:13.250515)
      Return value: None
    38: run_simulation (2016-01-13 19:07:12.136067 - 2016-01-13 19:07:12.201430)
        Arguments: data_a = 'data1.dat', data_b = 'data2.dat'
        Return value: [['0.0', '0.6'], ['1.0', '0.0'], ['1.0', '0.0'],
        ...
```

To restore files used by trial 1, run
```bash
$ now restore -l -i 1
```

By default, the restore command only restores the script used for the trial ("simulation.py"), even when it has imports and read files as input. Use the option *-l* to restore imported modules and the option *-i* to restore input files.
The restore command track the evolution history. By default, subsequent trials are based on the previous Trial (e.g. Trial 2 is based on Trial 1). When you checkout a Trial, the next Trial will be based on the checked out Trial (e.g. Trial 3 based on Trial 1).


The remaining options of noWorkflow are *diff*, *export* and *vis*. The *diff* option compares two trials, and the *export* option exports provenance data of a given trial to Prolog facts, so inference queries can be run over the database.

The vis option starts a visualization tool that allows interactive analysis:
```bash
$ now vis -b
```
The visualization tool shows the evolution history, the trial information, an activation graph. It is also possible to compare different trials in the visualization tool.

The visualization tool requires Flask to be installed.
To install Flask, you can run
```bash
$ pip install flask
```

IPython Interface
-----------------

Another way to run, visualize, and query trials is to use Jupyter notebook with IPython kernel.
To install Jupyter notebook and IPython kernel, you can run
```bash
$ pip install jupyter
$ pip install ipython
```

Then, to run Jupyter notebook, go to the project directory and execute:
```bash
$ jupyter notebook
```

It will start a local webserver where you can create notebooks and run python code.

Before loading anything related to noworkflow on a notebook, you must initialize it:
```python
In  [1]: %load_ext noworkflow
    ...: import noworkflow.now.ipython as nip
```
It is equivalent to:
```python
In  [1]: %load_ext noworkflow
    ...: nip = %now_ip
```

After that, you can either run a new trial or load an existing object (*History*, *Trial*, *Diff*).

There are two ways to run a new trial:

1- Load an external file
```python
In  [1]: arg1 = "data1.dat"
         arg2 = "data2.dat"

In  [2]: trial = %now_run simulation.py {arg1} {arg2}
    ...: trial
Out [2]: <Trial 12> # Loads the trial object represented as a graph
```

2- Load the code inside a cell
```python
In  [3]: arg = 4

In  [4]: %%now_run --name new_simularion --interactive
    ...: l = range(arg)
    ...: c = sum(l)
    ...: print(c)
         6
Out [4]: <Trial 13> # Loads the trial object represented as a graph

In  [5]: c
Out [5]: 6
```
Both modes supports all the `now run` parameters.

The *--interactive* mode allows the cell to share variables with the notebook.

Loading existing trials, histories and diffs:
```python
In  [6]: trial = nip.Trial(1) # Loads trial with Id = 1
    ...: trial # Shows trial graph
Out [6]: <Trial 1>

In  [7]: history = nip.History() # Loads history
    ...: history # Shows history graph
Out [7]: <History>

In  [8]: diff = nip.Diff(1, 3) # Loads diff between trial 1 and 3
    ...: diff # Shows diff graph
Out [8]: <Diff 1 3>
```

There are attributes on those objects to change the graph visualization, width, height and filter values. Please, check the documentation by running the following code on jupyter notebook:
```python
In  [9]: trial?

In  [10]: history?
```

It is also possible to run prolog queries on IPython notebook. To do so, you will need to install SWI-Prolog with shared libraries and the pyswip module.

You can install pyswip module with the command:
```bash
$ pip install pyswip-alt
```

Check how to install SWI-Prolog with shared libraries at https://github.com/yuce/pyswip/blob/master/INSTALL

To query a specific trial, you can do:
```python
In  [10]: result = trial.query("activation(_, 550, X, _, _, _)")
    ...: next(result) # The result is a generator
Out [10]: {'X': 'range'}
```

To check the existing rules, please do:
```python
In  [11]: %now_prolog_schema
Out [11]: [...]
```

Finally, it is possible to run the CLI commands inside ipython notebook:
```python
In  [12]: !now export {trial.id}
Out [12]: %
     ...: % FACT: activation(trial_id, id, name, start, finish, caller_activation_id).
     ...: %
     ...: ...
```

Included Software
-----------------

Parts of the following software were used by noWorkflow directly or in an adapted form:

The Python Debugger
Copyright (c) 2001-2016 Python Software Foundation.
All Rights Reserved.

Acknowledgements
----------------

We would like to thank CNPq, FAPERJ, and the National Science Foundation (CNS-1229185, CNS-1153503, IIS-1142013) for partially supporting this work.

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
