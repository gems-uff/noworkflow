import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';

import {Widget} from '@phosphor/widgets';

import {EnvironmentItemData, FilterObject} from './structures';

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

  static createFilterDiv(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>) {
    return parent.append("div");
  }

  static createFilter(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, default_local: string = "0"): FilterObject {
    let filterdiv = this.createFilterDiv(parent);

    let text_filter = filterdiv.append("input")
      .attr("type", "search");

    let select_local = filterdiv.append("select");
    select_local.append("option")
      .attr("value", "0")
      .text("Do not filter Main");

    select_local.append("option")
      .attr("value", "1")
      .text("Main Environment Only");

    select_local.append("option")
      .attr("value", "2")
      .text("Non-Main Environment Only");

    select_local.property("value", default_local);

    return {
      filterdiv: filterdiv,
      valid: (element: EnvironmentItemData) => {
        let stext = text_filter.property("value").toLowerCase();
        let slocal = Number(select_local.property("value"));

        let check_text = () => {
          return (
            element.name.toLowerCase().indexOf(stext) >= 0
            || element.value.toLowerCase().indexOf(stext) >= 0
          );
        }

        let check_local = () => {
            if (slocal == 0) return true;
            switch (element.name) {
              case 'PYTHON_IMPLEMENTATION':      
              case 'PYTHON_VERSION':
              case 'OS_NAME':
              case 'OS_RELEASE':
              case 'OS_USER':
              case 'PWD':
              case 'PID':
              case 'HOSTNAME':
              case 'ARCH':
              case 'PROCESSOR':
                return (slocal == 1)
              default:
                return (slocal != 1)
            }
          }

        return check_text() && check_local();
      },
      on_change: (filterfn: () => void) => {
        text_filter.on("keyup", filterfn);
        select_local.on("change", filterfn);
        filterfn();
      }
    };
  }

  static createList(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, data: EnvironmentItemData[], default_local: string = "0"): FilterObject {
    let filter = EnvironmentInfoWidget.createFilter(parent, default_local);
    let list = parent.append("ul")
      .classed("env-list", true)

    filter.on_change(() => {
      list.html("");
      for (var element of data) {
        if (!filter.valid(element)) {
          continue;
        }
        EnvironmentInfoWidget.createItem(list, element.name, element.value);
      }
    });
    return filter;
  }

  static createNode(trialDisplay: string, data: EnvironmentItemData[], default_local: string = "0"): HTMLElement {
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

    EnvironmentInfoWidget.createList(content, data, default_local);

    return node;
  }

  constructor(trialDisplay: string, data: EnvironmentItemData[], default_local: string = "0") {
    super({ node: EnvironmentInfoWidget.createNode(trialDisplay, data, default_local) });
    this.d3node = d3_select(this.node);
    this.addClass('content');
    this.addClass('trial-info-list');
    this.title.label = trialDisplay + "- Environment";
    this.title.closable = true;
    this.title.caption = `Trial ${trialDisplay} Environment`;
  }
}
