import '../style/index.css';

import {Widget} from '@phosphor/widgets';

import {NowVisPanel} from './nowpanel';
import {ConfigWidget} from './config_widget';
//import {ProjectWidget} from './project_widget';
import {HistoryWidget} from './graph/history_graph';
//import { json } from '@noworkflow/utils';


function main(): void {
  // ToDo: parse URL to open specific graphs
  var experimentsIn = (<HTMLInputElement>document.getElementById("experimentsIn")).value;
  var selectedExp = (<HTMLInputElement>document.getElementById("selectedExperiment")).value;
  var folders=[];
  if(experimentsIn)
    folders=JSON.parse(experimentsIn);
  console.log(folders);
  console.log(window.location.pathname);
  console.log(selectedExp);
  var mainpanel = new NowVisPanel();
  mainpanel.id = 'main';
  var config = new ConfigWidget();
  //var projectWidget = new ProjectWidget(folders);
  var history = new HistoryWidget(config, "History", "History", selectedExp);

  mainpanel.addMainWidget(history);
  mainpanel.addMainWidget(config);

  //mainpanel.addMainWidget(projectWidget);
  history.load();

  Widget.attach(mainpanel, document.body);
  window.onresize = () => { mainpanel.update() };
}

window.onload = main;