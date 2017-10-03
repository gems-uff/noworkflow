import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';

import {Widget} from '@phosphor/widgets';

import {DependencyListData, DependencyData} from '../base/structure';


export
class DependencyWidget extends Widget {

  d3node: d3_Selection<d3_BaseType, {}, HTMLElement, any>;

  static url(trialId: string) {
    return "http://127.0.0.1:5000/trials/" + trialId + "/dependencies.json";
  }

  static createList(parent: d3_Selection<d3_BaseType, {}, HTMLElement, any>, data: DependencyData[]): void {
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

  static createNode(trialId: string, data: DependencyData[]): HTMLElement {
    let node = document.createElement('div');
    let d3node = d3_select(node);

    let content = d3node.append('div')
      .classed('list', true)
    .append('div')
      .classed('side-info', true)

    content.append("div")
      .classed("main", true)
    .append("h1")
      .text("Modules (" + trialId + ")");

    DependencyWidget.createList(content, data);

    return node;
  }

  constructor(trialId: string, data: DependencyData[]) {
    super({ node: DependencyWidget.createNode(trialId, data) });
    this.d3node = d3_select(this.node);
    this.addClass('content');
    this.addClass('trial-info-list');
    this.title.label = trialId + "- Modules";
    this.title.closable = true;
    this.title.caption = `Trial ${trialId} Modules`;
  }
}
