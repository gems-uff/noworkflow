import '../style/index.css';

import {Widget} from '@phosphor/widgets';

import {NowVisPanel} from './nowpanel';
import {ConfigWidget} from './config_widget';
import {HistoryWidget} from './graph/history_graph';


function main(): void {
  // ToDo: parse URL to open specific graphs
  var mainpanel = new NowVisPanel();
  mainpanel.id = 'main';
  var config = new ConfigWidget();
  var history = new HistoryWidget(config, "History", "History");

  mainpanel.addMainWidget(history);
  mainpanel.addMainWidget(config);

  history.load();

  Widget.attach(mainpanel, document.body);
  window.onresize = () => { mainpanel.update() };
}

window.onload = main;