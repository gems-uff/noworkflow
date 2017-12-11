import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';

import {Widget} from '@phosphor/widgets';


export
class EnvironmentInfoWidget extends Widget {

  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;

  static url(trialId: string) {
    return "trials/" + trialId + "/environment.json";
  }

  static createItem(parent: d3_Selection<d3_BaseType, {}, HTMLElement| null, any>, key: string, value: string): void {
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

  static createList(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, data: { [key: string]: string }): void {
    let list = parent.append("ul")
      .classed("env-list", true)

    Object.keys(data).forEach(key => {
      let value = data[key];
      EnvironmentInfoWidget.createItem(list, key, value);
    });
  }

  static createNode(trialDisplay: string, data: { [key: string]: string }): HTMLElement {
    let node = document.createElement('div');
    let d3node = d3_select(node);

    let content = d3node.append('div')
      .classed('list', true)
    .append('div')
      .classed('side-info', true)

    content.append("div")
      .classed("main", true)
    .append("h1")
      .text("Environment (" + trialDisplay + ")");

    EnvironmentInfoWidget.createList(content, data);

    return node;
  }

  constructor(trialDisplay: string, data: { [key: string]: string }) {
    super({ node: EnvironmentInfoWidget.createNode(trialDisplay, data) });
    this.d3node = d3_select(this.node);
    this.addClass('content');
    this.addClass('trial-info-list');
    this.title.label = trialDisplay + "- Environment";
    this.title.closable = true;
    this.title.caption = `Trial ${trialDisplay} Environment`;
  }
}
