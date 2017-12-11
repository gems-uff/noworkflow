import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';

import {Widget} from '@phosphor/widgets';

import {ModuleData} from './structures';


export
class ModulesInfoWidget extends Widget {

  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;

  static url(trialId: string) {
    return "trials/" + trialId + "/dependencies.json";
  }

  static createList(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, data: ModuleData[]): void {
    let list = parent.append("ul")
      .classed("mod-list", true)

    for (var element of data) {
      var li = list.append("li");
      li.append("div").classed("name", true)
        .text(element.name);
      li.append("div").classed("version", true)
        .text(element.version === null ? "" : element.version);
      li.append("div").classed("clear", true)
      li.append("div").classed("hash", true)
        .attr("title", element.path)
        .text(element.code_hash);
    }
  }

  static createNode(trialDisplay: string, data: ModuleData[]): HTMLElement {
    let node = document.createElement('div');
    let d3node = d3_select(node);

    let content = d3node.append('div')
      .classed('list', true)
    .append('div')
      .classed('side-info', true)

    content.append("div")
      .classed("main", true)
    .append("h1")
      .text("Modules (" + trialDisplay + ")");

    ModulesInfoWidget.createList(content, data);

    return node;
  }

  constructor(trialDisplay: string, data: ModuleData[]) {
    super({ node: ModulesInfoWidget.createNode(trialDisplay, data) });
    this.d3node = d3_select(this.node);
    this.addClass('content');
    this.addClass('trial-info-list');
    this.title.label = trialDisplay + "- Modules";
    this.title.closable = true;
    this.title.caption = `Trial ${trialDisplay} Modules`;
  }
}
