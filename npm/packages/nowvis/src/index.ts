import '../style/index.css';

import {Widget} from '@phosphor/widgets';

import {NowVisPanel} from './nowpanel';
//import {ConfigWidget} from './config_widget';
import {ProjectWidget} from './project_widget';
//import {HistoryWidget} from './graph/history_graph';
//import { json } from '@noworkflow/utils';


function main(): void {
  // ToDo: parse URL to open specific graphs
  var folderInput = (<HTMLInputElement>document.getElementById("folderId")).value;
  var folders=[];
  if(folderInput)
    folders=JSON.parse(folderInput);
  console.log(folders);
  var mainpanel = new NowVisPanel();
  mainpanel.id = 'main';
  //var config = new ConfigWidget();
  var projectWidget = new ProjectWidget(folders);
  //var history = new HistoryWidget(config, "History", "History");

  //mainpanel.addMainWidget(history);
  //mainpanel.addMainWidget(config);

  mainpanel.addMainWidget(projectWidget);
  //history.load();

  Widget.attach(mainpanel, document.body);
  window.onresize = () => { mainpanel.update() };
}

window.onload = main;