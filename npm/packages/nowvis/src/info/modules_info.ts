import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';

import {Widget} from '@phosphor/widgets';

import {ModuleData, FilterObject} from './structures';


export
class ModulesInfoWidget extends Widget {

  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;

  static url(trialId: string) {
    return "trials/" + trialId + "/dependencies.json";
  }

  static createFilterDiv(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>) {
    return parent.append("div");
  }

  static createFilter(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, default_local: string = "0"): FilterObject {
    let filterdiv = this.createFilterDiv(parent);

    let text_filter = filterdiv.append("input")
      .attr("type", "search");

    let select_version = filterdiv.append("select");
    select_version.append("option")
      .attr("value", "both")
      .text("Do not filter Version");

    select_version.append("option")
      .attr("value", "1")
      .text("Filter In Version");

    select_version.append("option")
      .attr("value", "0")
      .text("Filter Out Version");
    select_version.property("value", "both")

    let select_local = filterdiv.append("select");
    select_local.append("option")
      .attr("value", "0")
      .text("Do not filter Locality");

    select_local.append("option")
      .attr("value", "1")
      .text("Local Modules Only");

    select_local.append("option")
      .attr("value", "2")
      .text("Non-Local Modules Only");

    select_local.property("value", default_local);

    return {
      filterdiv: filterdiv,
      valid: (local: string, element: ModuleData) => {
        let stext = text_filter.property("value").toLowerCase();
        let sversion = select_version.property("value");
        let slocal = Number(select_local.property("value"));

        let check_text = () => {
          return element.name.toLowerCase().indexOf(stext) >= 0;
        }

        let check_version = () => {
          if (sversion == "both") return true;
          if (sversion == "1") return element.version != null;
          if (sversion == "0") return element.version == null;
          return false;
        }

        let check_local = () => {
          if (slocal == 0) return true;
          if (element.path == null) return (slocal != 1);
          if (!/^((\/)|(\w+:\\))/.test(element.path)) return (slocal == 1); // not absolute path
          if (element.path.startsWith(local)) return (slocal == 1);
          return (slocal != 1);
        }

        return check_text() && check_version() && check_local();
      },
      on_change: (filterfn: () => void) => {
        text_filter.on("keyup", filterfn);
        select_version.on("change", filterfn);
        select_local.on("change", filterfn);
        filterfn();
      }
    };
    
  }

  static createList(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, data: ModuleData[], trial_path: string, default_local: string = "0"): FilterObject {
    let filter = ModulesInfoWidget.createFilter(parent, default_local);

    let list = parent.append("ul")
      .classed("mod-list", true);

    filter.on_change(() => {
      list.html("");

      for (var element of data) {
        if (!filter.valid(trial_path, element)) {
          continue;
        }
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
    });
    return filter;
  }

  static createNode(trialDisplay: string, data: ModuleData[], trial_path: string): HTMLElement {
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

    ModulesInfoWidget.createList(content, data, trial_path);

    return node;
  }

  constructor(trialDisplay: string, data: ModuleData[], trial_path: string) {
    super({ node: ModulesInfoWidget.createNode(trialDisplay, data, trial_path) });
    this.d3node = d3_select(this.node);
    this.addClass('content');
    this.addClass('trial-info-list');
    this.title.label = trialDisplay + "- Modules";
    this.title.closable = true;
    this.title.caption = `Trial ${trialDisplay} Modules`;
  }
}
