noWorkflow
==========

Copyright (c) 2016 Universidade Federal Fluminense (UFF).
Copyright (c) 2016 Polytechnic Institute of New York University.
All rights reserved.

The noWorkflow project aims at allowing scientists to benefit from provenance data analysis even when they don't use a workflow system. Also, the goal is to allow them to avoid using naming conventions to store files originated in previous executions. Currently, when this is not done, the result and intermediate files are overwritten by every new execution of the pipeline.


noWorkflow was developed in Python and it currently is able to capture provenance of Python scripts using Software Engineering techniques such as abstract syntax tree (AST) analysis, reflection, and profiling, to collect provenance without the need of a version control system or any other environment.

Installing and using noWorkflow is simple and easy. Please check our installation and basic usage guidelines below, and the [tutorial videos at our Wiki page](https://github.com/gems-uff/noworkflow/wiki/Videos).


Team
----

The main noWorkflow team is composed by researchers from Universidade Federal Fluminense (UFF) in Brazil and New York University (NYU), in the USA.

- João Felipe Pimentel (UFF) (main developer)
- Juliana Freire (NYU)
- Leonardo Murta (UFF)
- Vanessa Braganholo (UFF)

Collaborators

- David Koop (University of Massachusetts Dartmouth)
- Fernando Chirigati (NYU)
- Paolo Missier (Newcastle University)

Publications
------------

* [MURTA, L. G. P.; BRAGANHOLO, V.; CHIRIGATI, F. S.; KOOP, D.; FREIRE, J.; noWorkflow: Capturing and Analyzing Provenance of Scripts. In: International Provenance and Annotation Workshop (IPAW), 2014, Cologne, Germany.](https://github.com/gems-uff/noworkflow/raw/master/docs/ipaw2014.pdf)
* [PIMENTEL, J. F. N.; FREIRE, J.; MURTA, L. G. P.; BRAGANHOLO, V.; Collecting and Analyzing Provenance on Interactive Notebooks: when IPython meets noWorkflow. In: Theory and Practice of Provenance (TaPP), 2015, Edinburgh, Scotland.](https://github.com/gems-uff/noworkflow/raw/master/docs/tapp2015.pdf)
* [PIMENTEL, J. F.; FREIRE, J.; BRAGANHOLO, V.; MURTA, L. G. P.; Tracking and Analyzing the Evolution of Provenance from Scripts. In: International Provenance and Annotation Workshop (IPAW), 2016, McLean, Virginia.](https://github.com/gems-uff/noworkflow/raw/master/docs/ipaw2016a.pdf)
* [PIMENTEL, J. F.; FREIRE, J.; MURTA, L. G. P.; BRAGANHOLO, V.; Fine-grained Provenance Collection over Scripts Through Program Slicing. In: International Provenance and Annotation Workshop (IPAW), 2016, McLean, Virginia.](https://github.com/gems-uff/noworkflow/raw/master/docs/ipaw2016b.pdf)
* [PIMENTEL, J. F.; DEY, S.; MCPHILLIPS, T.; BELHAJJAME, K.; KOOP, D.; MURTA, L. G. P.; BRAGANHOLO, V.; LUDÄSCHER B.; Yin & Yang: Demonstrating Complementary Provenance from noWorkflow & YesWorkflow. In: International Provenance and Annotation Workshop (IPAW), 2016, McLean, Virginia.](https://github.com/gems-uff/noworkflow/raw/master/docs/ipaw2016c.pdf)
* [PIMENTEL, J. F.; MURTA, L. G. P.; BRAGANHOLO, V.; FREIRE, J.; noWorkflow: a Tool for Collecting, Analyzing, and Managing Provenance from Python Scripts. In: International Conference on Very Large Data Bases (VLDB), 2017, Munich, Germany.](https://github.com/gems-uff/noworkflow/raw/master/docs/vldb2017.pdf)

History
------------------

The project started in 2013, when Leonardo Murta and Vanessa Braganholo were visiting professors at New York University (NYU) with Juliana Freire. At that moment, David Koop and Fernando Chirigati also joined the project. They published the initial paper about noWorkflow in IPAW 2014. After going back to their home university, Universidade Federal Fluminense (UFF), Leonardo and Vanessa invited João Felipe Pimentel to join the project in 2014 for his PhD. João, Juliana, Leonardo and Vanessa integrated noWorkflow and IPython and published a paper about it in TaPP 2015. They also worked on provenance versioning and fine-grained provenance collection and published papers in IPAW 2016. During the same time, David, João, Leonardo and Vanessa worked with the YesWorkflow team on an integration between noWorkflow & YesWorkflow and published a demo in IPAW 2016. The research and development on noWorkflow continues and is currently under the responsibility of João Felipe, in the context of his PhD thesis.

[![Contribution Timeline](history/history.png)](history/history.svg)


Quick Installation
------------------

This version of noWorkflow only supports **Python 2.7** and **Python 3.5**. If you want to use Python 3.6, please try the [2.0-alpha](https://github.com/gems-uff/noworkflow/tree/2.0-alpha) version.

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
$ now restore 1
```

By default, the restore command will restore the trial script, imported local modules and the first access to files. Use the option *-s* to leave out the script; the option *-l* to leave out modules; and the option *-a* to leave out file accesses. The restore command track the evolution history. By default, subsequent trials are based on the previous Trial (e.g. Trial 2 is based on Trial 1). When you restore a Trial, the next Trial will be based on the restored Trial (e.g. Trial 3 based on Trial 1).

The restore command also provides a *-f path* option. This option can be used to restore a single file. With this command there are extra options: *-t path2* specifies the target of restored file; *-i id* identifies the file. There are 3 possibilities to identify files: by access time, by code hash, or by number of access.

```bash
$ now restore 1 -f data1.dat -i "A|2016-01-13 19:06:59"
$ now restore 1 -f output.png -i 90451b101 -t output_trial1.png
$ now restore 1 -f simulation.py -i 1
```

The first command queries data1.dat of Trial 1 accessed at "2016-01-13 19:06:59", and restores the resulting content after the access.
The second command restores output.png with subhash 90451b101, and save it to output_trial1.png.
The third command restores the first access to simulation.py, which represents the trial script.

The option *-f* does not affect evolution history.


The remaining options of noWorkflow are *diff*, *export*, *history*, *dataflow*, and *vis*.

The *diff* option compares two trials. It has options to compare modules (*-m*), environment (*-e*), file accesses (*-f*). It has also an option to present a brief diff, instead of a full diff (*--brief*)

The *export* option exports provenance data of a given trial to Prolog facts, so inference queries can be run over the database.

The *history* option presents a textual history evolution graph of trials.

The *dataflow* option exports fine-grained provenance data (captured through *-e Tracer*) to a graphviz dot representing the dataflow. This command has many options to change the resulting graph. Please, run "now dataflow -h" to get their descriptions.

```bash
$ now dataflow 6 -l -m prospective | dot -Tpng -o prospective.png
```

The *vis* option starts a visualization tool that allows interactive analysis:
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
$ jupyter nbextension install --py --sys-prefix noworkflow
$ jupyter nbextension enable noworkflow --py --sys-prefix
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

To visualize the dataflow of a trial, it is possible to use the dot attribute of trial objects:
```python
In  [9]: trial.dot
Out [9]: <png image>

This command requires an installation of graphviz.


There are attributes on those objects to change the graph visualization, width, height and filter values. Please, check the documentation by running the following code on jupyter notebook:
```python
In  [10]: trial?

In  [11]: history?
```

It is also possible to run prolog queries on IPython notebook. To do so, you will need to install SWI-Prolog with shared libraries and the pyswip module.

You can install pyswip module with the command:
```bash
$ pip install pyswip-alt
```

Check how to install SWI-Prolog with shared libraries at https://github.com/yuce/pyswip/blob/master/INSTALL

To query a specific trial, you can do:
```python
In  [12]: result = trial.query("activation(_, 550, X, _, _, _)")
    ...: next(result) # The result is a generator
Out [12]: {'X': 'range'}
```

To check the existing rules, please do:
```python
In  [13]: %now_schema prolog -t
Out [13]: [...]
```

Finally, it is possible to run the CLI commands inside ipython notebook:
```python
In  [14]: !now export {trial.id}
Out [14]: %
     ...: % FACT: activation(trial_id, id, name, start, finish, caller_activation_id).
     ...: %
     ...: ...
```


Contributing
------------

Pull requests for bugfixes and new features are welcome! If you want to add a new feature, please consider working on the branch `2.0-alpha`. The `master` branch is going to be replaced by it soon and the code base has many changes that make it harder to merge it.

For installing the python dependencies locally, clone the repository and run:
```
pip install -e noworkflow/capture
```

For changes on the now vis or IPython integration files, install nodejs, Python 3 and run:
```
cd noworkflow/npm
python watch.py
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

The MIT License (MIT)

Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.

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
