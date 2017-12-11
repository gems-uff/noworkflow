import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';

import {json} from '@noworkflow/utils';

import {BaseActivationGraphWidget} from './base_activation_graph';

import {TrialGraphData} from '@noworkflow/trial';


export
class DiffGraphWidget extends BaseActivationGraphWidget {

  static url(trial1: number, trial2: number, selectedGraph: string, useCache: boolean): string {
    let cache = useCache ? "1" : "0"
    return ("diff/"
      + trial1 + "/" + trial2 + "/" + selectedGraph + "-" + cache + ".json"
    );
  }

  static createForm(name: string, parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>): void {
  }

  constructor(name: string, cls: string, t1: number, t2: number) {
    super({ node: BaseActivationGraphWidget.createNode(cls, DiffGraphWidget.createForm) });
    this.d3node = d3_select(this.node);
    this.d3node.select('.reload-button')
      .on("click", () => {
        this.load(
          this.d3node.select(".graph-type").property("value"),
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

  load(selectedGraph: string = "namespace_match", useCache: boolean = true) {
    let sub = this.node.getElementsByClassName("sub-content")[0];
    json("Diff", sub, DiffGraphWidget.url(this.t1, this.t2, selectedGraph, useCache), (data: TrialGraphData) => {
      let selectorDiv = this.d3node.select(".trial-content .graphselector");

      let useCacheDiv = selectorDiv.select(".use-cache");
      useCacheDiv.property("checked", useCache);

      this.configureGraph(selectedGraph, useCache, data);
    })
  }
}
