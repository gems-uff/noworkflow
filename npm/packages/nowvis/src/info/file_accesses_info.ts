import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';

import {Widget} from '@phosphor/widgets';

import {FileAccessData, FilterObject} from './structures';


export
class FileAccessesInfoWidget extends Widget {

  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;

  static url(trialId: string) {
    return "trials/" + trialId + "/file_accesses.json";
  }

  static createFilterDiv(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>) {
    return parent.append("div");
  }

  static createFilter(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, default_local: string = "0"): FilterObject {
    let filterdiv = this.createFilterDiv(parent);

    let text_filter = filterdiv.append("input")
      .attr("placeholder", "Name")
      .attr("type", "search");

    let mode_filter = filterdiv.append("input")
      .attr("placeholder", "Mode")
      .attr("type", "search");

    let select_hash = filterdiv.append("select");
    select_hash.append("option")
      .attr("value", "0")
      .text("Do not filter Existence");

    select_hash.append("option")
      .attr("value", "1")
      .text("Exists only before trial");

    select_hash.append("option")
      .attr("value", "2")
      .text("Exists only after trial");

    select_hash.append("option")
      .attr("value", "3")
      .text("Changes during trial");

    select_hash.append("option")
      .attr("value", "7")
      .text("Does not change during trial");

    select_hash.property("value", "0");

    let select_local = filterdiv.append("select");
    select_local.append("option")
      .attr("value", "0")
      .text("Do not filter Locality");

    select_local.append("option")
      .attr("value", "1")
      .text("Local files only");

    select_local.append("option")
      .attr("value", "2")
      .text("Non-local files only");

    select_local.property("value", default_local);

    return {
      filterdiv: filterdiv,
      valid: (local: string, element: FileAccessData) => {
        let stext = text_filter.property("value").toLowerCase();
        let smode = mode_filter.property("value").toLowerCase();
        let shash = Number(select_hash.property("value"));
        let slocal = Number(select_local.property("value"));

        let check_text = () => {
          return element.name.toLowerCase().indexOf(stext) >= 0;
        }

        let check_mode = () => {
          return element.mode.toLowerCase().indexOf(smode) >= 0;
        }

        let check_hash = () => {
          if (((shash & 1) == 1) && element.content_hash_before == null) return false;
          if (((shash & 2) == 2) && element.content_hash_after == null) return false;
          if (shash == 1) return element.content_hash_after == null;
          if (shash == 2) return element.content_hash_before == null;
          if (shash == 3) return element.content_hash_before != element.content_hash_after;
          if (shash == 4) return element.content_hash_before == element.content_hash_after;
          return true;
        } 

        let check_local = () => {
          if (slocal == 0) return true;
          if (!/^((\/)|(\w+:\\))/.test(element.name)) return (slocal == 1); // not absolute path
          if (element.name.startsWith(local)) return (slocal == 1);
          return (slocal != 1);
        }

        return check_text() && check_mode() && check_hash() && check_local();
      },
      on_change: (filterfn: () => void) => {
        text_filter.on("keyup", filterfn);
        mode_filter.on("keyup", filterfn);
        select_hash.on("change", filterfn);
        select_local.on("change", filterfn);
        filterfn();
      }
    };
  }

  static createList(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, data: FileAccessData[], trial_path: string, default_local: string = "0"): FilterObject {
    let filter = FileAccessesInfoWidget.createFilter(parent, default_local);

    let list = parent.append("ul")
      .classed("fac-list", true)

    filter.on_change(() => {
      list.html("");
      for (var element of data) {
        if (!filter.valid(trial_path, element)) {
          continue;
        }
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
    });
    return filter;
  }

  static createNode(trialDisplay: string, data: FileAccessData[], trial_path: string, default_local: string = "0"): HTMLElement {
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

    FileAccessesInfoWidget.createList(content, data, trial_path, default_local);

    return node;
  }

  constructor(trialDisplay: string, data: FileAccessData[], trial_path: string, default_local: string = "0") {
    super({ node: FileAccessesInfoWidget.createNode(trialDisplay, data, trial_path, default_local) });
    this.d3node = d3_select(this.node);
    this.addClass('content');
    this.addClass('trial-info-list');
    this.title.label = trialDisplay + "- Accesses";
    this.title.closable = true;
    this.title.caption = `Trial ${trialDisplay} Accesses`;
  }
}
