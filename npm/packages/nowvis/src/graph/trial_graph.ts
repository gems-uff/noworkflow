import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';

import {Widget} from '@phosphor/widgets';

import {json} from '@noworkflow/utils';

import {BaseActivationGraphWidget} from './base_activation_graph';

import {TrialGraph, TrialGraphData} from '@noworkflow/trial';


export
class TrialGraphWidget extends BaseActivationGraphWidget {

  name: string;
  cls: string;
  t1: number;
  t2: number;
  graph: TrialGraph;
  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;

  static url(trialId: number, selectedGraph: string, useCache: boolean) {
    let cache = useCache ? "1" : "0"
    return ("trials/"
      + trialId + "/" + selectedGraph + "/" + cache + ".json"
    );
  }

  constructor(name: string, cls: string, t1: number, t2: number) {
    super({ node: BaseActivationGraphWidget.createNode(cls) });
    this.d3node = d3_select(this.node);
    this.d3node.select('.reload-button')
      .on("click", () => {
        this.load(
          this.d3node.select(".graph-type").property("value"),
          this.d3node.select(".use-cache").property("checked"),
        )
      })
    this.addClass('content');
    this.addClass('trial-widget');
    this.title.label = name;
    this.title.closable = true;
    this.title.caption = `${name} Graph`;
    this.name = name;
    this.cls = cls;
    this.t1 = t1;
    this.t2 = t2;
  }

  setGraph(data: TrialGraphData, config: any={}) {
    let sub = this.node.getElementsByClassName("sub-content")[0];
    sub.innerHTML = "";
    this.graph = new TrialGraph(this.cls, sub, config);
    this.graph.load(data, this.t1, this.t2);
  }

  configureGraph(selectedGraph: string = "namespace_match", useCache: boolean = true, data: TrialGraphData) {
    this.setGraph(data, {
      width: this.node.getBoundingClientRect().width - 24,
      height: this.node.getBoundingClientRect().height - 24,
      customForm: (graph: TrialGraph, form: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>) => {
        // Toggle Tooltips
        let selectorDiv = this.d3node.select(".trial-content .graphselector");

        let typeOptions = selectorDiv.select(".graph-type");
        typeOptions.property("value", selectedGraph);

        let useCacheDiv = selectorDiv.select(".use-cache");
        useCacheDiv.property("checked", useCache);


        let selectorToggle = form.append("input")
          .attr("id", "trial-" + graph.graphId + "-toolbar-selector-check")
          .attr("type", "checkbox")
          .attr("name", "trial-toolbar-selector-check")
          .attr("value", "show")
          .property("checked", selectorDiv.classed('visible'))
          .on("change", () => {
            let visible = selectorToggle.property("checked");
            selectorToggleI
              .classed('fa-circle-o', visible)
              .classed('fa-circle', !visible);
            selectorDiv
              .classed('visible', visible)
              .classed('show-toolbar', visible)
              .classed('hide-toolbar', !visible)
          });
        let selectorLabel = form.append("label")
          .attr("for", "trial-" + graph.graphId + "-toolbar-selector-check")

        let optionsNode: any = typeOptions.node();

        selectorLabel.append("span")
          .classed("toggle-label", true)
          .text(optionsNode.options[optionsNode.selectedIndex].text)

        let selectorToggleI = selectorLabel.append("i")
          .classed('fa', true)
          .classed("fa-circle", !selectorDiv.classed('visible'))
          .classed("fa-circle-o", selectorDiv.classed('visible'))
      }
    });
  }

  load(selectedGraph: string = "namespace_match", useCache: boolean = true) {
    let sub = this.node.getElementsByClassName("sub-content")[0];
    json("Trial", sub, TrialGraphWidget.url(this.t1, selectedGraph, useCache), (data: TrialGraphData) => {
      this.configureGraph(selectedGraph, useCache, data);
    })
  }

  protected onResize(msg: Widget.ResizeMessage): void {
    if (this.graph) {
      this.graph.config.width = this.node.getBoundingClientRect().width - 24;
      this.graph.config.height = this.node.getBoundingClientRect().height - 24;
      this.graph.updateWindow();
    }
  }

}

