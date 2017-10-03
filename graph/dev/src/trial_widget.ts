import './style/trial.css';

import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';

import {Widget} from '@phosphor/widgets';

import {TrialGraph, TrialConfig} from './base/trial';
import {MultiGraphData, TrialGraphData} from './base/structure';
import {json} from './base/helpers';

export
class GraphWidget extends Widget {

  name: string;
  cls: string;
  t1: number;
  t2: number;
  graph: TrialGraph;
  d3node: d3_Selection<d3_BaseType, {}, HTMLElement, any>;

  static graphTypeForm(name: string, selectorDiv: d3_Selection<d3_BaseType, {}, HTMLElement, any>) {
    let graphType = selectorDiv.append("div")
      .classed("graph-attr", true);

    graphType.append("label")
      .attr("for", name + "-graphtype")
      .attr("title", "Select the graph type")
      .text("Graph Type:")

    let typeOptions = graphType.append("select")
      .attr("id", name + "-graphtype")
      .classed("graph-type", true)
      .classed("select-style", true);

    typeOptions.append("option")
      .attr("value", "tree")
      .attr("data-description", "Activation tree. Edges represent order of execution")
      .text("Tree")

    typeOptions.append("option")
      .attr("value", "no_match")
      .attr("data-description", "Activation tree presented as a Graph")
      .text("No Match")

    typeOptions.append("option")
      .attr("value", "exact_match")
      .attr("data-description", "Calls have counting independent from caller activations")
      .text("Exact Match")

    typeOptions.append("option")
      .attr("value", "namespace_match")
      .attr("data-description", "Calls are combined and a function may have more than one call workflow")
      .text("Namespace Match")

    typeOptions.property("value", "namespace_match")
  }

  static useCacheForm(name: string, selectorDiv: d3_Selection<d3_BaseType, {}, HTMLElement, any>) {
    let useCache = selectorDiv.append("div")
      .classed("graph-attr", true);

    useCache.append("input")
      .attr("type", "checkbox")
      .attr("name", "use_cache")
      .attr("value", "on")
      .attr("checked", true)
      .classed("use-cache", true)
      .attr("id", name + "-use-cache")

    useCache.append("label")
      .attr("for", name + "-use-cache")
      .attr("title", "Select the graph type")
      .text("Use Cache")
  }

  static createNode(name:string, fn: (name: string, parent: d3_Selection<d3_BaseType, {}, HTMLElement, any>) => void = (parent) => null): HTMLElement {
    let node = document.createElement('div');
    let d3node = d3_select(node);

    let content = d3node.append('div')
      .classed('trial-content', true)

    let selectorDiv = content.append("div")
      .classed("graphselector", true)
      .classed("hide-toolbar", true);

    GraphWidget.graphTypeForm(name, selectorDiv);

    fn(name, selectorDiv);

    GraphWidget.useCacheForm(name, selectorDiv);

    let selectorReload = selectorDiv.append("a")
      .attr("href", "#")
      .classed("link-button reload-button", true)

    selectorReload.append('i')
      .classed("fa fa-refresh", true);

    selectorReload.append('span')
      .text('Reload');


    let sub = content.append('div')
      .classed('sub-content', true);

    return node;
  }

  setGraph(data: TrialGraphData, config: TrialConfig={}) {
    let sub = this.node.getElementsByClassName("sub-content")[0];
    sub.innerHTML = "";
    this.graph = new TrialGraph(this.cls, sub, config);
    this.graph.load(data, this.t1, this.t2);
  }

  configureGraph(selectedGraph: string = "namespace_match", useCache: boolean = true, data: TrialGraphData) {
    this.setGraph(data, {
      width: this.node.getBoundingClientRect().width - 24,
      height: this.node.getBoundingClientRect().height - 24,
      customForm: (graph, form) => {
        // Toggle Tooltips
        let selectorDiv = this.d3node.select(".trial-content .graphselector");

        let typeOptions = selectorDiv.select(".graph-type");
        typeOptions.property("value", selectedGraph);

        let useCacheDiv = selectorDiv.select(".use-cache");
        useCacheDiv.property("value", useCache);


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

  protected onResize(msg: Widget.ResizeMessage): void {
    if (this.graph) {
      this.graph.config.width = this.node.getBoundingClientRect().width - 24;
      this.graph.config.height = this.node.getBoundingClientRect().height - 24;
      this.graph.updateWindow();
    }
  }

}


export
class TrialGraphWidget extends GraphWidget {

  name: string;
  cls: string;
  t1: number;
  t2: number;
  graph: TrialGraph;
  d3node: d3_Selection<d3_BaseType, {}, HTMLElement, any>;

  static url(trialId: number, selectedGraph: string, useCache: boolean) {
    let cache = useCache ? "1" : "0"
    return ("http://127.0.0.1:5000/trials/"
      + trialId + "/" + selectedGraph + "/" + cache + ".json"
    );
  }

  constructor(name: string, cls: string, t1: number, t2: number) {
    super({ node: GraphWidget.createNode(cls) });
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

  setGraph(data: TrialGraphData, config: TrialConfig={}) {
    let sub = this.node.getElementsByClassName("sub-content")[0];
    sub.innerHTML = "";
    this.graph = new TrialGraph(this.cls, sub, config);
    this.graph.load(data, this.t1, this.t2);
  }

  configureGraph(selectedGraph: string = "namespace_match", useCache: boolean = true, data: TrialGraphData) {
    this.setGraph(data, {
      width: this.node.getBoundingClientRect().width - 24,
      height: this.node.getBoundingClientRect().height - 24,
      customForm: (graph, form) => {
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

export
class DiffGraphWidget extends GraphWidget {

  static url(trial1: number, trial2: number, selectedGraph: string, neighborhood: number, timeLimit: number, useCache: boolean): string {
    let cache = useCache ? "1" : "0"
    return ("http://127.0.0.1:5000/diff/"
      + trial1 + "/" + trial2 + "/" + selectedGraph + "/" +
      + timeLimit + "-" + neighborhood + "-" + cache + ".json"
    );
  }

  static createForm(name: string, parent: d3_Selection<d3_BaseType, {}, HTMLElement, any>): void {
    let graphNeighborhood = parent.append("div")
      .classed("graph-attr", true);

    graphNeighborhood.append("label")
      .attr("for", name + "-difflevel")
      .attr("title", "Select the deepness of diff")
      .text("Neighborhood:")

    let levelOptions = graphNeighborhood.append("select")
      .attr("id", name + "-difflevel")
      .classed("diff-level", true)
      .classed("select-style", true);

    levelOptions.append("option")
      .attr("value", "0")
      .attr("data-description", "Use LCS for basic matching")
      .text("0 - LCS")

    levelOptions.append("option")
      .attr("value", "1")
      .attr("data-description", "Match remaining nodes")
      .text("1 - Remaining nodes")

    levelOptions.append("option")
      .attr("value", "2")
      .attr("data-description", "Permutate nodes on the same height")
      .text("2 - Permutate on the same height")

    levelOptions.append("option")
      .attr("value", "3")
      .attr("data-description", "Permutate any node")
      .text("3 - Permutate anything")

    levelOptions.property("value", "2")


    let graphTimelimit = parent.append("div")
      .classed("graph-attr time-attr", true);

    graphTimelimit.append("label")
      .attr("for", name + "-graphlimit")
      .attr("title", "Limit the execution time (seconds)")
      .text("Time Limit:")

    graphTimelimit.append("input")
      .attr("id", name + "-graphlimit")
      .attr("type", "number")
      .attr("name", "graphlimit")
      .attr("value", "0")
      .classed("select-style timelimit", true)
      .text("Time Limit:");

  }

  constructor(name: string, cls: string, t1: number, t2: number) {
    super({ node: GraphWidget.createNode(cls, DiffGraphWidget.createForm) });
    this.d3node = d3_select(this.node);
    this.d3node.select('.reload-button')
      .on("click", () => {
        this.load(
          this.d3node.select(".graph-type").property("value"),
          this.d3node.select(".diff-level").property("value"),
          this.d3node.select(".timelimit").property("value"),
          this.d3node.select(".use-cache").property("checked"),
        )
      })
    this.addClass('content');
    this.addClass('diff-widget');
    this.title.label = name;
    this.title.closable = true;
    this.title.caption = `${name} Graph`;
    this.name = name;
    this.cls = cls;
    this.t1 = t1;
    this.t2 = t2;
  }

  load(selectedGraph: string = "namespace_match", neighborhood: number = 2, timeLimit: number = 0, useCache: boolean = true) {
    let sub = this.node.getElementsByClassName("sub-content")[0];
    json("Diff", sub, DiffGraphWidget.url(this.t1, this.t2, selectedGraph, neighborhood, timeLimit, useCache), (data: MultiGraphData) => {
      let selectorDiv = this.d3node.select(".trial-content .graphselector");

      let diffLevelOptions = selectorDiv.select(".diff-level");
      diffLevelOptions.property("value", neighborhood);

      let timeLimitInput = selectorDiv.select(".timelimit");
      timeLimitInput.property("value", timeLimit);

      let useCacheDiv = selectorDiv.select(".use-cache");
      useCacheDiv.property("checked", useCache);

      this.configureGraph(selectedGraph, useCache, data.diff);
    })
  }
}
