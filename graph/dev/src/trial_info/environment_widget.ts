import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';

import {Widget} from '@phosphor/widgets';

import {DependencyListData, DependencyData} from '../base/structure';


export
class EnvironmentWidget extends Widget {

  d3node: d3_Selection<d3_BaseType, {}, HTMLElement, any>;

  static url(trialId: string) {
    return "http://127.0.0.1:5000/trials/" + trialId + "/environment.json";
  }

  static createItem(parent: d3_Selection<d3_BaseType, {}, HTMLElement, any>, key: string, value: string): void {
    if (value) {
      let li = parent.append("li");
      li.append("span")
        .classed("key", true)
        .text(key)
      li.append("span")
        .classed("equal", true)
        .text(" = ")
      li.append("span")
        .classed("value", true)
        .text(value)
    }
  }

  static createList(parent: d3_Selection<d3_BaseType, {}, HTMLElement, any>, data: { [key: string]: string }): void {
    let list = parent.append("ul")
      .classed("env-list", true)

    Object.keys(data).forEach(key => {
      let value = data[key];
      EnvironmentWidget.createItem(list, key, value);
    });
  }

  static createNode(trialId: string, data: { [key: string]: string }): HTMLElement {
    let node = document.createElement('div');
    let d3node = d3_select(node);

    let content = d3node.append('div')
      .classed('list', true)
    .append('div')
      .classed('side-info', true)

    content.append("div")
      .classed("main", true)
    .append("h1")
      .text("Environment (" + trialId + ")");

    EnvironmentWidget.createList(content, data);

    return node;
  }

  constructor(trialId: string, data: { [key: string]: string }) {
    super({ node: EnvironmentWidget.createNode(trialId, data) });
    this.d3node = d3_select(this.node);
    this.addClass('content');
    this.addClass('trial-info-list');
    this.title.label = trialId + "- Environment";
    this.title.closable = true;
    this.title.caption = `Trial ${trialId} Environment`;
  }
}
