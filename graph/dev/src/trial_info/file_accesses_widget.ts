import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';

import {Widget} from '@phosphor/widgets';

import {FileAccessListData, FileAccessData} from '../base/structure';


export
class FileAccessWidget extends Widget {

  d3node: d3_Selection<d3_BaseType, {}, HTMLElement, any>;

  static url(trialId: string) {
    return "http://127.0.0.1:5000/trials/" + trialId + "/file_accesses.json";
  }

  static createList(parent: d3_Selection<d3_BaseType, {}, HTMLElement, any>, data: FileAccessData[]): void {
    let list = parent.append("ul")
      .classed("fac-list", true)

    for (var element of data) {
      var li = list.append("li");
      li.append("div").classed("name", true)
        .attr("title", "Name")
        .text(element.name);
      li.append("div").classed("mode", true)
        .attr("title", "Mode")
        .text(element.mode);
      li.append("div").classed("buffering", true)
        .attr("title", "Buffering")
        .text(element.buffering);
      li.append("div").classed("clear", true)
      li.append("div").classed("timestamp", true)
        .attr("title", "Time")
        .text(element.timestamp);
      li.append("div").classed("content_hash_before hash", true)
        .attr("title", "Content hash before")
        .text(element.content_hash_before);
      li.append("div").classed("content_hash_after hash", true)
        .attr("title", "Content hash after")
        .text(element.content_hash_after);
      li.append("div").classed("stack", true)
        .attr("title", "Stack")
        .text(element.stack);
    }
  }

  static createNode(trialId: string, data: FileAccessData[]): HTMLElement {
    let node = document.createElement('div');
    let d3node = d3_select(node);

    let content = d3node.append('div')
      .classed('list', true)
    .append('div')
      .classed('side-info', true)

    content.append("div")
      .classed("main", true)
    .append("h1")
      .text("File Accesses (" + trialId + ")");

    FileAccessWidget.createList(content, data);

    return node;
  }

  constructor(trialId: string, data: FileAccessData[]) {
    super({ node: FileAccessWidget.createNode(trialId, data) });
    this.d3node = d3_select(this.node);
    this.addClass('content');
    this.addClass('trial-info-list');
    this.title.label = trialId + "- Accesses";
    this.title.closable = true;
    this.title.caption = `Trial ${trialId} Accesses`;
  }
}
