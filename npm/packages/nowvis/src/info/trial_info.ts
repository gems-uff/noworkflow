import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';

import {Widget} from '@phosphor/widgets';

import {
  VisibleHistoryNode, HistoryTrialNodeData
} from '@noworkflow/history';
import {json} from '@noworkflow/utils';


import {ModuleListData, EnvironmentData, FileAccessListData, FilterObject} from './structures';

import {ModulesInfoWidget} from './modules_info';
import {EnvironmentInfoWidget} from './environment_info';
import {FileAccessesInfoWidget} from './file_accesses_info';


export
class TrialInfoWidget extends Widget {

  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  trial: VisibleHistoryNode;

  static createNode(trial: VisibleHistoryNode): HTMLElement {
    let node = document.createElement('div');
    let info = trial.info as HistoryTrialNodeData;

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
      .text(info.code_hash || "");

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
      .text(info.script);

    let startAttr = main.append("span")
      .classed("attr", true);
    startAttr.append("span")
      .classed("desc", true)
      .text("Start: ");
    startAttr.append("span")
      .classed("start", true)
      .text(info.str_start || "");

    let finishAttr = main.append("span")
      .classed("attr", true);
    finishAttr.append("span")
      .classed("desc", true)
      .text("Finish: ");
    finishAttr.append("span")
      .classed("finish", true)
      .text(info.str_finish || "");

    let durationAttr = main.append("span")
      .classed("attr", true);
    durationAttr.append("span")
      .classed("desc", true)
      .text("Duration: ");
    durationAttr.append("span")
      .classed("duration", true)
      .text(info.duration_text || "");

    if (info.command) {
      let argumentsAttr = main.append("span")
        .classed("attr", true);
      argumentsAttr.append("span")
        .classed("desc", true)
        .text("Arguments: ");
      argumentsAttr.append("span")
        .classed("arguments", true)
        .text(info.command);
    }


    content.append("div")
      .classed("modules", true)

    content.append("div")
      .classed("environment", true)

    content.append("div")
      .classed("file-accesses", true)

    return node;
  }

  constructor(trial: VisibleHistoryNode) {
    super({ node: TrialInfoWidget.createNode(trial) });
    this.trial = trial;
    this.d3node = d3_select(this.node);
    this.addClass('content');
    this.addClass('trial-info');
    this.title.label = trial.display + "- Information";
    this.title.closable = true;
    this.title.caption = `Trial ${trial.display} Information`;
    this.loadModules();
    this.loadEnvironment();
    this.loadFileAccess();
  }

  static createFold(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, title: string) {
    let fold = parent.append("div")
      .classed("fold", true)
    let foldI = fold.append("i")
      .classed("fa fa-minus", true)
    let spanI = fold.append("span")
      .text(title)
    
    let click = () => {
      let visible = foldI.classed("fa-plus");
      foldI.classed("fa-plus", !visible);
      foldI.classed("fa-minus", visible);
      parent.select(".foldable")
        .classed("show-toolbar", visible)
        .classed("hide-toolbar", !visible)
      return false;
    };
    foldI.on("click", click);
    spanI.on("click", click);
    return fold;
  }

  static createFilterFold(fold: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, filter: FilterObject) {
    filter.filterdiv
      .classed("info-filter", true)
      .classed("show-toolbar", false)
      .classed("hide-toolbar", true);

    let foldA = fold.append("a")
      .attr("href", "#")
      .attr("title", "Search")
      .classed("show-all", true);

    let foldAI = foldA.append("i")
      .classed("fa fa-search-plus", true);
     
    foldA.on("click", () => {
      let visible = foldAI.classed("fa-search-plus");
      foldAI.classed("fa-search-plus", !visible);
      foldAI.classed("fa-search-minus", visible);
      filter.filterdiv
        .classed("show-toolbar", visible)
        .classed("hide-toolbar", !visible)
      return false;
    });
  }

  loadModules() {
    let sub = this.node.getElementsByClassName("modules")[0];
    json("Modules", sub, ModulesInfoWidget.url(this.trial.title), (data: ModuleListData) => {
      let modules = this.d3node.select(".modules").html("");
      if (data.all.length > 0) {
        
        let fold = TrialInfoWidget.createFold(modules, "Modules");
        let filter = ModulesInfoWidget.createList(
          modules.append("div").classed("foldable show-toolbar", true),
          data.all, data.trial_path, "1"
        );
        TrialInfoWidget.createFilterFold(fold, filter);
      }
    });
  }

  loadEnvironment() {
    let sub = this.node.getElementsByClassName("environment")[0];

    json("Environment", sub, EnvironmentInfoWidget.url(this.trial.title), (data: EnvironmentData) => {
      let environment = this.d3node.select(".environment").html("");

      let fold = TrialInfoWidget.createFold(environment, "Environment");
      let filter = EnvironmentInfoWidget.createList(
        environment.append("div").classed("foldable show-toolbar", true),
        data.all, "1"
      );
      TrialInfoWidget.createFilterFold(fold, filter);
    })
  }

  loadFileAccess() {
    let sub = this.node.getElementsByClassName("file-accesses")[0];

    json("File Accesses", sub, FileAccessesInfoWidget.url(this.trial.title), (data: FileAccessListData) => {
      let accesses = this.d3node.select(".file-accesses").html("");

      if (data.file_accesses.length > 0) {

        let fold = TrialInfoWidget.createFold(accesses, "File Accesses");
        let filter = FileAccessesInfoWidget.createList(
          accesses.append("div").classed("foldable show-toolbar", true),
          data.file_accesses, data.trial_path
        );
        TrialInfoWidget.createFilterFold(fold, filter);
      }
    });
  }
}
