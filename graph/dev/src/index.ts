import './style/panel.css';
import './style/index.css';

import {Widget} from '@phosphor/widgets';

import {NowVisPanel} from './nowpanel';
import {HistoryWidget} from './history_widget';
import {ConfigWidget} from './config_widget';




function main(): void {
  // ToDo: parse URL to open specific graphs
  var mainpanel = new NowVisPanel();
  mainpanel.id = 'main';
  var config = new ConfigWidget();
  var history = new HistoryWidget(config, "History", "History");
  history.title.closable = false;
  mainpanel.addMainWidget(history);
  mainpanel.addMainWidget(config);

  history.load();

  console.log(config.showTrial(), config.showInfo())

  Widget.attach(mainpanel, document.body);
  window.onresize = () => { mainpanel.update() };
}

window.onload = main;