import '../style/index.css';

import {Widget} from '@lumino/widgets';

import {NowVisPanel} from './nowpanel';
import {ConfigWidget} from './config_widget';
import {ProjectWidget} from './project_widget';
import {GroupWidget} from './group_widget';
import {HistoryWidget} from './graph/history_graph';
import { AnnontationWidget } from './annotation_widget';
//import { json } from '@noworkflow/utils';


function main(): void {
  // ToDo: parse URL to open specific graphs
  var experimentsIn = (<HTMLInputElement>document.getElementById("experimentsIn")).value;
  var selectedExp = (<HTMLInputElement>document.getElementById("selectedExperiment")).value;
  var server = (<HTMLInputElement>document.getElementById("server")).value;
  var experiments=[];

  if(experimentsIn)
  experiments=JSON.parse(experimentsIn);

  var mainpanel = new NowVisPanel();
  mainpanel.id = 'main';
  if(server=="True"){
    var projectWidget = new ProjectWidget(experiments);
    var groupWidget = new GroupWidget();
    mainpanel.addMainWidget(projectWidget);
    mainpanel.addMainWidget(groupWidget);
  }
  else{
    var config = new ConfigWidget();
    var annotationn = new AnnontationWidget(selectedExp);
    var history = new HistoryWidget(config, "History", "History", selectedExp,annotationn);
 

    mainpanel.addMainWidget(history);
    mainpanel.addMainWidget(config);
    mainpanel.addMainWidget(annotationn);
    history.load();
  }  

  Widget.attach(mainpanel, document.body);
  window.onresize = () => { mainpanel.update() };
}

window.onload = main;