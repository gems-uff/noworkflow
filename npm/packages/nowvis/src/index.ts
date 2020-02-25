import '../style/index.css';

import {Widget} from '@phosphor/widgets';

import {NowVisPanel} from './nowpanel';
import {ConfigWidget} from './config_widget';
import {ProjectWidget} from './project_widget';
import {HistoryWidget} from './graph/history_graph';
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
    mainpanel.addMainWidget(projectWidget);
  }
  else{
    var config = new ConfigWidget();
    var history = new HistoryWidget(config, "History", "History", selectedExp);

    mainpanel.addMainWidget(history);
    mainpanel.addMainWidget(config);
    history.load();
  }  

  Widget.attach(mainpanel, document.body);
  window.onresize = () => { mainpanel.update() };
}

window.onload = main;