import {Widget} from '@phosphor/widgets';

import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';

import {BaseActivationGraphWidget} from './graph/base_activation_graph';


export
class ConfigWidget extends Widget {

  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;

  static createNode(): HTMLElement {
    let node = document.createElement('div');
    let d3node = d3_select(node);

    let content = d3node.append('div')
      .classed('config-content', true)

    let historydiv = content.append("div")

    historydiv.append("h2")
      .text("History Graph")

    let showGraph = historydiv.append("div")
      .classed("graph-attr", true);

    showGraph.append("input")
      .attr("type", "checkbox")
      .attr("name", "show_graph")
      .attr("value", "on")
      .attr("checked", true)
      .classed("show-graph", true)
      .attr("id", "config-show-graph")

    showGraph.append("label")
      .attr("for", "config-show-graph")
      .attr("title", "Open trial graph")
      .text("Show trial graph on selection")

    let showInfo = historydiv.append("div")
      .classed("graph-attr", true);

    showInfo.append("input")
      .attr("type", "checkbox")
      .attr("name", "show_info")
      .attr("value", "on")
      .attr("checked", true)
      .classed("show-info", true)
      .attr("id", "config-show-info")

    showInfo.append("label")
      .attr("for", "config-show-info")
      .attr("title", "Open trial info")
      .text("Show trial information on selection")


    let trialdiv = content.append("div")
    trialdiv.append("h2")
      .text("Trial Graph")

    BaseActivationGraphWidget.graphTypeForm("config", trialdiv);
    BaseActivationGraphWidget.useCacheForm("config", trialdiv);

    return node;
  }

  constructor() {
    super({ node: ConfigWidget.createNode() });
    this.d3node = d3_select(this.node);
    //this.setFlag(Widget.Flag.DisallowLayout);
    this.addClass('content');
    this.title.label = "Config";
    this.title.closable = false
    this.title.caption = `Configuration`;
  }


  showTrial(): boolean {
    return this.d3node.select(".show-graph").property("checked");
  }

  showInfo(): boolean {
    return this.d3node.select(".show-info").property("checked");
  }

  graphType(): string {
    return this.d3node.select(".graph-type").property("value");
  }

  useCache(): boolean {
    return this.d3node.select(".use-cache").property("checked");
  }

}