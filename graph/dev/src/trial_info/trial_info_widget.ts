import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';

import {Widget} from '@phosphor/widgets';

import {
  DependencyListData, EnvironmentData, FileAccessListData
} from '../base/structure';

import {VisibleNode} from '../base/history';
import {json} from '../base/helpers';
import {NowVisPanel} from '../nowpanel';

import {DependencyWidget} from './dependency_widget';
import {EnvironmentWidget} from './environment_widget';
import {FileAccessWidget} from './file_accesses_widget';


export
class TrialInfoWidget extends Widget {

  d3node: d3_Selection<d3_BaseType, {}, HTMLElement, any>;
  trial: VisibleNode;

  static createNode(trial: VisibleNode): HTMLElement {
    let node = document.createElement('div');
    let d3node = d3_select(node);

    let content = d3node.append('div')
      .classed('trial-info', true)
    .append('div')
      .classed('side-info', true)

    let main = content.append('div')
      .classed('main', true)

    main.append("h1")
      .text("Trial " + trial.display);

    main.append("h3")
      .classed("hash", true)
      .text(trial.info.code_hash);

    let idAttr = main.append("span")
      .classed("attr", true);
    idAttr.append("span")
      .classed("desc", true)
      .text("Id: ");
    idAttr.append("span")
      .classed("id", true)
      .text(trial.title);

    let scriptAttr = main.append("span")
      .classed("attr", true);
    scriptAttr.append("span")
      .classed("desc", true)
      .text("Script: ");
    scriptAttr.append("span")
      .classed("script", true)
      .text(trial.info.script);

    let startAttr = main.append("span")
      .classed("attr", true);
    startAttr.append("span")
      .classed("desc", true)
      .text("Start: ");
    startAttr.append("span")
      .classed("start", true)
      .text(trial.info.start);

    let finishAttr = main.append("span")
      .classed("attr", true);
    finishAttr.append("span")
      .classed("desc", true)
      .text("Finish: ");
    finishAttr.append("span")
      .classed("finish", true)
      .text(trial.info.finish);

    let durationAttr = main.append("span")
      .classed("attr", true);
    durationAttr.append("span")
      .classed("desc", true)
      .text("Duration: ");
    durationAttr.append("span")
      .classed("duration", true)
      .text(trial.info.duration_text);

    if (trial.info.arguments) {
      let argumentsAttr = main.append("span")
        .classed("attr", true);
      argumentsAttr.append("span")
        .classed("desc", true)
        .text("Arguments: ");
      argumentsAttr.append("span")
        .classed("arguments", true)
        .text(trial.info.arguments);
    }


    content.append("div")
      .classed("modules", true)

    content.append("div")
      .classed("environment", true)

    content.append("div")
      .classed("file-accesses", true)

    return node;
  }

  constructor(trial: VisibleNode) {
    super({ node: TrialInfoWidget.createNode(trial) });
    this.trial = trial;
    this.d3node = d3_select(this.node);
    this.addClass('content');
    this.addClass('trial-info');
    this.title.label = trial.display + "- Information";
    this.title.closable = true;
    this.title.caption = `Trial ${trial.display} Information`;
    this.loadDependencies();
    this.loadEnvironment();
    this.loadFileAccess();
  }

  createFold(parent: d3_Selection<d3_BaseType, {}, HTMLElement, any>, title: string, fn:(parentDock: NowVisPanel) => void) {
    let fold = parent.append("div")
      .classed("fold", true)
    let foldI = fold.append("i")
      .classed("fa fa-minus", true)
    fold.append("span")
      .text(title)
    fold.append("a")
      .attr("href", "#")
      .attr("title", "Show all")
      .classed("show-all", true)
      .on("click", () => {
        fn(this.parent as NowVisPanel);
        return false;
      })
    .append("i")
      .classed("fa fa-binoculars", true)

    fold.on("click", () => {
      let visible = foldI.classed("fa-plus");
      foldI.classed("fa-plus", !visible);
      foldI.classed("fa-minus", visible);
      parent.select(".foldable")
        .classed("show-toolbar", visible)
        .classed("hide-toolbar", !visible)
      return false;
    })
  }

  loadDependencies() {
    let sub = this.node.getElementsByClassName("modules")[0];

    json("Modules", sub, DependencyWidget.url(this.trial.title), (data: DependencyListData) => {
      let modules = this.d3node.select(".modules").html("");
      if (data.all.length > 0) {
        this.createFold(modules, "Modules", (parentDock: NowVisPanel) => {
          var widget = new DependencyWidget(this.trial.title, data.all);

          parentDock.addInfoWidget(widget);
          parentDock.activateWidget(widget);
        })

        DependencyWidget.createList(
          modules.append("div").classed("foldable show-toolbar", true),
          data.local
        );
      }
    });
  }

  loadEnvironment() {
    let sub = this.node.getElementsByClassName("environment")[0];

    json("Environment", sub, EnvironmentWidget.url(this.trial.title), (data: EnvironmentData) => {
      let environment = this.d3node.select(".environment").html("");

      this.createFold(environment, "Environment", (parentDock: NowVisPanel) => {
        var widget = new EnvironmentWidget(this.trial.title, data.env);

        parentDock.addInfoWidget(widget);
        parentDock.activateWidget(widget);
      })

      var list = environment.append("div")
        .classed("foldable show-toolbar", true)
      .append("ul")
        .classed("env-list", true);

      function li(key: string) {
        EnvironmentWidget.createItem(list, key, data.env[key]);
      }
      li('PYTHON_IMPLEMENTATION');
      li('PYTHON_VERSION');
      li('OS_NAME');
      li('OS_RELEASE');
      li('OS_VERSION');
      li('OS_USER');
      li('PWD');
      li('PID');
      li('HOSTNAME');
      li('ARCH');
      li('PROCESSOR');
    })
  }

  loadFileAccess() {
    let sub = this.node.getElementsByClassName("file-accesses")[0];

    json("File Accesses", sub, FileAccessWidget.url(this.trial.title), (data: FileAccessListData) => {
      let accesses = this.d3node.select(".file-accesses").html("");

      if (data.file_accesses.length > 0) {

        this.createFold(accesses, "File Accesses", (parentDock: NowVisPanel) => {
          var widget = new FileAccessWidget(this.trial.title, data.file_accesses);

          parentDock.addInfoWidget(widget);
          parentDock.activateWidget(widget);
        });

        FileAccessWidget.createList(
          accesses.append("div").classed("foldable show-toolbar", true),
          data.file_accesses
        );
      }
    });
  }
}
