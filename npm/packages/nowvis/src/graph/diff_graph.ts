import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';

import {json} from '@noworkflow/utils';

import {BaseActivationGraphWidget} from './base_activation_graph';

import {MultiGraphData} from '@noworkflow/trial';


export
class DiffGraphWidget extends BaseActivationGraphWidget {

  static url(trial1: number, trial2: number, selectedGraph: string, neighborhood: number, timeLimit: number, useCache: boolean): string {
    let cache = useCache ? "1" : "0"
    return ("diff/"
      + trial1 + "/" + trial2 + "/" + selectedGraph + "/" +
      + timeLimit + "-" + neighborhood + "-" + cache + ".json"
    );
  }

  static createForm(name: string, parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>): void {
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
    super({ node: BaseActivationGraphWidget.createNode(cls, DiffGraphWidget.createForm) });
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
