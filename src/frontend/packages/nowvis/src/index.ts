import '../style/index.css';

import { Widget } from '@lumino/widgets';

import { NowVisPanel } from './nowpanel';
import { ConfigWidget } from './config_widget';
import { ProjectWidget } from './project_widget';
import { GroupWidget } from './group_widget';
import { HistoryWidget } from './graph/history_graph';
import { AnnontationWidget } from './annotation_widget';
import { DatabaseWidget } from './database_widget';
//import { json } from '@noworkflow/utils';

function main(): void {
  // ToDo: parse URL to open specific graphs
  const experimentsIn = (<HTMLInputElement>(
    document.getElementById('experimentsIn')
  )).value;
  const selectedExp = (<HTMLInputElement>(
    document.getElementById('selectedExperiment')
  )).value;
  const server = (<HTMLInputElement>document.getElementById('server')).value;
  let experiments = [];

  if (experimentsIn) {
    experiments = JSON.parse(experimentsIn);
  }

  const mainpanel = new NowVisPanel();
  mainpanel.id = 'main';
  if (server === 'True') {
    const projectWidget = new ProjectWidget(experiments);
    const groupWidget = new GroupWidget();
    const databaseWidget = new DatabaseWidget(mainpanel);

    mainpanel.addMainWidget(projectWidget);
    mainpanel.addMainWidget(groupWidget);
    mainpanel.addMainWidget(databaseWidget);
  } else {
    const config = new ConfigWidget();
    const annotationn = new AnnontationWidget(selectedExp);
    const history = new HistoryWidget(
      config,
      'History',
      'History',
      selectedExp,
      annotationn
    );
    const databaseWidget = new DatabaseWidget(mainpanel);

    mainpanel.addMainWidget(history);
    mainpanel.addMainWidget(config);
    mainpanel.addMainWidget(annotationn);
    mainpanel.addMainWidget(databaseWidget);
    history.load();
  }

  Widget.attach(mainpanel, document.body);
  window.onresize = () => {
    mainpanel.update();
  };
}

window.onload = main;
