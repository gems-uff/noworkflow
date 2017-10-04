import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';

import {Widget} from '@phosphor/widgets';

import {FileAccessData} from './structures';


export
class FileAccessesInfoWidget extends Widget {

  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;

  static url(trialId: string) {
    return "trials/" + trialId + "/file_accesses.json";
  }

  static createList(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, data: FileAccessData[]): void {
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

  static createNode(trialDisplay: string, data: FileAccessData[]): HTMLElement {
    let node = document.createElement('div');
    let d3node = d3_select(node);

    let content = d3node.append('div')
      .classed('list', true)
    .append('div')
      .classed('side-info', true)

    content.append("div")
      .classed("main", true)
    .append("h1")
      .text("File Accesses (" + trialDisplay + ")");

    FileAccessesInfoWidget.createList(content, data);

    return node;
  }

  constructor(trialDisplay: string, data: FileAccessData[]) {
    super({ node: FileAccessesInfoWidget.createNode(trialDisplay, data) });
    this.d3node = d3_select(this.node);
    this.addClass('content');
    this.addClass('trial-info-list');
    this.title.label = trialDisplay + "- Accesses";
    this.title.closable = true;
    this.title.caption = `Trial ${trialDisplay} Accesses`;
  }
}
