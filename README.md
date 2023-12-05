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
- Eduardo Jandre (UFF)

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
* [OLIVEIRA, E.; Enabling Collaboration in Scientific Experiments. Masters Dissertation, Universidade Federal Fluminense, 2022.](/docs/Disserta__o___Eduardo_Jandre.pdf)

History
------------------

The project started in 2013, when Leonardo Murta and Vanessa Braganholo were visiting professors at New York University (NYU) with Juliana Freire. At that moment, David Koop and Fernando Chirigati also joined the project. They published the initial paper about noWorkflow in IPAW 2014. After going back to their home university, Universidade Federal Fluminense (UFF), Leonardo and Vanessa invited João Felipe Pimentel to join the project in 2014 for his PhD. João, Juliana, Leonardo and Vanessa integrated noWorkflow and IPython and published a paper about it in TaPP 2015. They also worked on provenance versioning and fine-grained provenance collection and published papers in IPAW 2016. During the same time, David, João, Leonardo and Vanessa worked with the YesWorkflow team on an integration between noWorkflow & YesWorkflow and published a demo in IPAW 2016. The research and development on noWorkflow continues and is currently under the responsibility of João Felipe, in the context of his PhD thesis.

[![Contribution Timeline](history/history.png)](history/history.svg)


Quick Installation
------------------

To install noWorkflow, you should follow these basic instructions:

First your Python version must be 3.7, then if you have pip, just run:
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

If you want to install the dependencies to run the demos execute the following commands:

```bash
$ cd noworkflow
$ pip install -e capture[demo]
```

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
[now] using content engine noworkflow.now.persistence.content.plain_engine.PlainEngine
[now] collecting deployment provenance
[now]   registering environment attributes
[now] collection definition and execution provenance
[now]   executing the script
[now] the execution of trial 91f4fdc7-6c36-4c9d-a43a-341eaee9b7fb finished successfully
```
Each new run produces a different trial that will be stored with a universally unique identifier in the relational database.

Verifying the module dependencies is a time consuming step, and scientists can bypass this step by using the *-b* flag if they know that no library or source code has changed. The current trial then inherits the module dependencies of the previous one.

To list all trials, just run

```bash
$ now list
```
Assuming we run the experiment again and then run `now list`, the output would be as follows. Note that 9 trials were extracted from the demonstration.

```bash
$ now list
[now] trials available in the provenance store:
  [f]Trial 7fb4ca3d-8046-46cf-9c54-54923d2076ba: run -v .\simulation.py .\data1.dat .\data2.dat
                                                 with code hash 6a28e58e34bbff0facaf55f80313ab2fd2505a58
                                                 ran from 2023-04-12 19:38:50.234485 to 2023-04-12 19:38:51.672300
                                                 duration: 0:00:01.437815
  [*]Trial 01482b72-2005-4319-bd57-773291f9f7b1: run -v .\simulation.py .\data1.dat .\data2.dat
                                                 with code hash 6a28e58e34bbff0facaf55f80313ab2fd2505a58
                                                 ran from 2023-04-12 19:40:18.747749 to 2023-04-12 19:40:48.401719
                                                 duration: 0:00:29.653970
  [*]Trial c320d339-09d1-4d10-ad38-e565fa1f1f08: run simulation.py data1.dat data2.dat
                                                 with code hash 6a28e58e34bbff0facaf55f80313ab2fd2505a58
                                                 ran from 2023-04-12 19:44:28.459500 to 2023-04-12 19:44:43.310089
                                                 duration: 0:00:14.850589
  [f]Trial 28a6e5da-9a3c-473b-902c-44574beeef29: run simulation_complete.py
                                                 with code hash 78b5b11f3e6f7dca48a6ab9851df2cc0fb5157bc
                                                 ran from 2023-04-12 19:44:44.987635 to 2023-04-12 19:44:58.970957
                                                 duration: 0:00:13.983322
  [*]Trial 4a30be20-e295-4a38-8aea-6b36e4fd2bcd: run simulation.py data1.dat data2.dat
                                                 with code hash 8f73e09f17e877cb2d3ce3604cc66293abed2300
                                                 ran from 2023-04-12 19:45:00.667359 to 2023-04-12 19:45:15.783596
                                                 duration: 0:00:15.116237
  [*]Trial 87161c9c-9a8b-4742-ab3a-df1cdf1779d5: run simulation.py data2.dat data1.dat
                                                 with code hash 6a28e58e34bbff0facaf55f80313ab2fd2505a58
                                                 ran from 2023-04-12 19:45:19.122164 to 2023-04-12 19:45:35.050733
                                                 duration: 0:00:15.928569
  [b]Trial 8bf59cf5-cd06-409e-97f6-185063b1cfc3: restore 3
                                                 with code hash c3aeb4cb9af363b375aec603010dd1b97460f6b1
                                                 ran from 2023-04-12 19:45:36.937565 to 2023-04-12 19:45:37.141808
                                                 duration: 0:00:00.204243
  [*]Trial 0adee409-bebf-4119-ae57-8a9d5ba345ce: run simulation.py data1.dat data2.dat
                                                 with code hash 8f73e09f17e877cb2d3ce3604cc66293abed2300
                                                 ran from 2023-04-12 19:45:38.873199 to 2023-04-12 19:45:53.370662
                                                 duration: 0:00:14.497463
  [f]Trial 035a4749-1c58-4f1b-b296-d708779e258a: run simulation.py data1.dat data2.dat
                                                 with code hash c3aeb4cb9af363b375aec603010dd1b97460f6b1
                                                 ran from 2023-04-12 19:45:54.945150 to 2023-04-12 19:46:08.792798
                                                 duration: 0:00:13.847648
  [f]Trial b14bf7b9-a0e5-4f12-a1ae-fb3922c1cd5f: run simulation_complete.py
                                                 with code hash c7c8de76eb564530131abfab4d510bb187ec4b04
                                                 ran from 2023-04-12 19:46:10.360999 to 2023-04-12 19:46:23.811610
                                                 duration: 0:00:13.450611
  [*]Trial 231368e0-786a-4bf4-8e21-a8d05cc72585: run simulation.py data1.dat data2.dat
                                                 with code hash 6a28e58e34bbff0facaf55f80313ab2fd2505a58
                                                 ran from 2023-04-12 19:46:25.385022 to 2023-04-12 19:46:42.141455
                                                 duration: 0:00:16.756433
  [*]Trial 91f4fdc7-6c36-4c9d-a43a-341eaee9b7fb: run -v simulation.py data1.dat data2.dat
                                                 with code hash 6a28e58e34bbff0facaf55f80313ab2fd2505a58
                                                 ran from 2023-04-12 19:48:29.463034 to 2023-04-12 19:48:46.930577
                                                 duration: 0:00:17.467543
```
Each symbol between brackets is its respective trial status. They can express if
```
a trial is a backup: b

a trial has not finished: f

a trial has finished: *
```
To look at details of an specific trial, use
```bash
$ now show [trial]
```
This command has several options, such as *-m* to show module dependencies; *-d* to show function definitions; *-e* to show the environment context; *-a* to show function activations; and *-f* to show file accesses.

Running
```bash
$ now show -a 91f4fdc7-6c36-4c9d-a43a-341eaee9b7fb
```
would show details of trial 91f4fdc7-6c36-4c9d-a43a-341eaee9b7fb. Notice that the function name is preceded by the line number where the call was activated.

```bash
$ now show -a 91f4fdc7-6c36-4c9d-a43a-341eaee9b7fb
[now] trial information:
  Id: 91f4fdc7-6c36-4c9d-a43a-341eaee9b7fb
  Sequence Key: 21
  Status: Finished
  Inherited Id: None
  Script: simulation.py
  Code hash: 6a28e58e34bbff0facaf55f80313ab2fd2505a58
  Start: 2023-04-12 19:48:29.463034
  Finish: 2023-04-12 19:48:46.930577
  Duration: 0:00:17.467543
[now] this trial has the following function activation tree:
  1: __main__ (2023-04-12 19:48:30.263701 - 2023-04-12 19:48:42.070729)
     Return value: <module '__main__' from '/home/joao/demotest/demo1/simulation.py'>
    38: run_simulation (2023-04-12 19:48:38.590221 - 2023-04-12 19:48:40.676348)
        Parameters: data_a = 'data1.dat', data_b = 'data2.dat'
        Return value: [['0.0', '0.6'], ['1.0', '0.0'], ['1.0', '0.0']
        ...
```

To restore files used by trial 91f4fdc7-6c36-4c9d-a43a-341eaee9b7fb, run
```bash
$ now restore 91f4fdc7-6c36-4c9d-a43a-341eaee9b7fb
```

By default, the restore command will restore the trial script, imported local modules and the first access to files. Use the option *-s* to leave out the script; the option *-l* to leave out modules; and the option *-a* to leave out file accesses. The restore command track the evolution history. By default, subsequent trials are based on the previous Trial (e.g. Trial 01482b72-2005-4319-bd57-773291f9f7b1 is based on 7fb4ca3d-8046-46cf-9c54-54923d2076ba). When you restore a Trial, the next Trial will be based on the restored Trial (e.g. c320d339-09d1-4d10-ad38-e565fa1f1f08 based on Trial 7fb4ca3d-8046-46cf-9c54-54923d2076ba).

The restore command also provides a *-f path* option. This option can be used to restore a single file. With this command there are extra options: *-t path2* specifies the target of restored file; *-i id* identifies the file. There are 3 possibilities to identify files: by access time, by code hash, or by number of access.

```bash
$ now restore 91f4fdc7-6c36-4c9d-a43a-341eaee9b7fb -f data1.dat -i "A|2023-04-12 19:48:46"
$ now restore 91f4fdc7-6c36-4c9d-a43a-341eaee9b7fb -f output.png -i 90451b101 -t output_trial1.png
$ now restore 91f4fdc7-6c36-4c9d-a43a-341eaee9b7fb -f simulation.py -i 1
```

The first command queries data1.dat of Trial 91f4fdc7-6c36-4c9d-a43a-341eaee9b7fb accessed at "2023-04-12 19:48:46", and restores the resulting content after the access.
The second command restores output.png with subhash 90451b101, and save it to output_trial1.png.
The third command restores the first access to simulation.py, which represents the trial script.

The option *-f* does not affect evolution history.


The remaining options of noWorkflow are *diff*, *export*, *history*, *dataflow*, and *vis*.

The *diff* option compares two trials. It has options to compare modules (*-m*), environment (*-e*), file accesses (*-f*). It has also an option to present a brief diff, instead of a full diff (*--brief*)

The *export* option exports provenance data of a given trial to Prolog facts, so inference queries can be run over the database.

The *history* option presents a textual history evolution graph of trials.

The *dataflow* option exports fine-grained provenance data to a graphviz dot representing the dataflow. This command has many options to change the resulting graph. Please, run "now dataflow -h" to get their descriptions.

```bash
$ now dataflow 91f4fdc7-6c36-4c9d-a43a-341eaee9b7fb -l -m prospective | dot -Tpng -o prospective.png
```

The *vis* option starts a visualization tool that allows interactive analysis:
```bash
$ now vis -b
```
The visualization tool shows the evolution history, the trial information, an activation graph. It is also possible to compare different trials in the visualization tool.

The visualization tool requires Flask to be installed.
To install Flask, you can run
```bash
$ pip install flask==2.1.3
```

Collaboration Usage
-----------

noWorkflow can also be used to run collaborative experiments. Scientists with different computers can work on the same experiments without much trouble. To do this they must do push and pull operations to a server.

The server can be a central one or a peer-to-peer connection. To set up a server or connection online the command below must be run

```bash
$ now vis --force true
```

The command line output will show the server address 
```bash
 * Serving Flask app 'noworkflow.now.vis.views'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on http://localhost:5000
Press CTRL+C to quit
```
In the case above it's http://localhost:5000

To create a new experiment you must open the server address and choose the "Add Experiment" option
![Collab main page](/readme_images/collab_main_page.png)

Then you must give the experiment a name, write its description, and choose "Confirm"
![Collab add experiment](/readme_images/collab_add_experiment.png)

If the experiment is successfully created you should see a message stating so
![Collab add experiment success](/readme_images/collab_add_experiment_success.png)
As you can see in the image above, an id and an url for the experiment will be generated after the experiment is created.
The url is extremely important since it will be used to do the push and pull operations.

To get the experiment on a computer you first need to navigate to the folder where you want the experiment, then execute the pull command. The pull command accepts a --url parameter that must be followed by the experiment's url. For example

```bash
$ now pull --url http://localhost:5000/experiments/958273cc-b90a-4d1c-b617-43bd2dca20de
```

The command will download the experiment's files and provenience in the folder. If there are already any files or trials in the experiment you must execute the command "now restore" with or without a trial id.

To push(or commit) to the server(or peer-to-peer connection) you must run the push command. The push command accepts a --url parameter that must be followed by the experiment's url. For example

```bash
$ now push --url http://localhost:5000/experiments/958273cc-b90a-4d1c-b617-43bd2dca20de
```

You can also add groups to a server by navigating to the "Group Information" tab and choosing the "Add Group" option

![Collab group tab](/readme_images/collab_group_tab.png)

Then you should write the group's name and choose "Confirm"
![Collab group add group](/readme_images/collab_add_group.png)

If the group is added successfully, you should see a message confirming that the group was created. You should also see the options to add a user to a group or to delete the group
![Collab group success](/readme_images/collab_group_success.png)

If the option to add a user is chosen, you must select the user from a list and choose "Confirm".
![Collab group member](/readme_images/collab_add_group_member.png)

To delete a group just select "Delete Group", then "OK" on the alert that will appear on the screen
![Collab delete group](/readme_images/collab_delete_group.png)

Annotations
-----------------

You can also add annotations to an experiment. To do this you need to access the experiment's url, then go to the "Annotation" tab, and select "Add Annotation"
![Annotation experiment](/readme_images/annotation%20experiment.png)

After filling the annotation's information, choose "Confirm"
![Annotation add](/readme_images/annotation_add.png)

If the annotation is added, you will see a success message and will be able to download the annotation as seen below
![Annotation success](/readme_images/annotation_success.png)

Annotations can also be added to a trial by following the same procedure above. But first, you must select a trial, choose "Manage Annotations"

![Annotation trial](/readme_images/trial_annotations.png)

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
Out [2]: <Trial "7fb4ca3d-8046-46cf-9c54-54923d2076ba"> # Loads the trial object represented as a graph
```

2- Load the code inside a cell
```python
In  [3]: arg = 4

In  [4]: %%now_run --name new_simularion --interactive
    ...: l = range(arg)
    ...: c = sum(l)
    ...: print(c)
         6
Out [4]: <Trial "01482b72-2005-4319-bd57-773291f9f7b1"> # Loads the trial object represented as a graph

In  [5]: c
Out [5]: 6
```
Both modes supports all the `now run` parameters.

The *--interactive* mode allows the cell to share variables with the notebook.

Loading existing trials, histories and diffs:
```python
In  [6]: trial = nip.Trial("7fb4ca3d-8046-46cf-9c54-54923d2076ba") # Loads trial with Id = 7fb4ca3d-8046-46cf-9c54-54923d2076ba
    ...: trial # Shows trial graph
Out [6]: <Trial 7fb4ca3d-8046-46cf-9c54-54923d2076ba>

In  [7]: history = nip.History() # Loads history
    ...: history # Shows history graph
Out [7]: <History>

In  [8]: diff = nip.Diff("7fb4ca3d-8046-46cf-9c54-54923d2076ba", "01482b72-2005-4319-bd57-773291f9f7b1") # Loads diff between trial 7fb4ca3d-8046-46cf-9c54-54923d2076ba and 01482b72-2005-4319-bd57-773291f9f7b1
    ...: diff # Shows diff graph
Out [8]: <Diff "7fb4ca3d-8046-46cf-9c54-54923d2076ba" "01482b72-2005-4319-bd57-773291f9f7b1">
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

Pull requests for bugfixes and new features are welcome!

For installing the python dependencies locally, clone the repository and run:
```
pip install -e noworkflow/capture
```

For changes on the now vis or IPython integration files, install nodejs, Python 3 and run:
```
cd noworkflow/npm
python watch.py
```
(If it is your first time making changes or if you changed some modules, you must first run the following command before "python watch.py":)
```
npm install
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
