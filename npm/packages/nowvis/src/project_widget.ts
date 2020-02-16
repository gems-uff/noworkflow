import {Widget} from '@phosphor/widgets';

import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';

interface IExperiment {
  id: string;
  name: string;
}

export
class ProjectWidget extends Widget {

  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;

  experiments: Array<IExperiment>;
  static createNode(): HTMLElement {
    let node = document.createElement('div');
 
    return node;
  }

  constructor(experiments: Array<IExperiment>) {
    super({ node: ProjectWidget.createNode() });
    this.d3node = d3_select(this.node);
    this.experiments=experiments;
    
    this.setNode();
    this.addClass('content');
    this.title.label = "Experiment Selection";
    this.title.closable = false
    this.title.caption = `Experiment`;
  }
  setNode(){

    let content = this.d3node.append('div')
      .classed('config-content', true)

    let projectsDiv = content.append("div")

    projectsDiv.append("h2")
      .text("Experiments:")

    let projectList = projectsDiv.append("ul")
      .classed("graph-attr", true);

    this.experiments.forEach(function (obj) {

        let item=projectList.append("li").append("a")
        item.attr("href","experiments/"+obj.name)
        item.text(obj.name)
        
    });
    
    
  }

}