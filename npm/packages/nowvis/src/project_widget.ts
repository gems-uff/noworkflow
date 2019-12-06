import {Widget} from '@phosphor/widgets';

import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';


export
class ProjectWidget extends Widget {

  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;

  folders: Array<String>;
  static createNode(): HTMLElement {
    let node = document.createElement('div');
 
    return node;
  }

  constructor(folders: Array<string>) {
    super({ node: ProjectWidget.createNode() });
    this.d3node = d3_select(this.node);
    this.folders=folders;
    //this.setFlag(Widget.Flag.DisallowLayout);
    this.setNode();
    this.addClass('content');
    this.title.label = "Project Selection";
    this.title.closable = false
    this.title.caption = `Project`;
  }
  setNode(){

    let content = this.d3node.append('div')
      .classed('config-content', true)

    let projectsDiv = content.append("div")

    projectsDiv.append("h2")
      .text("Projects")

    let projectList = projectsDiv.append("ul")
      .classed("graph-attr", true);

    this.folders.forEach(function (value) {
        let t="";
        if(value)
            t=value.toString()
        let item=projectList.append("li").append("a")
        item.attr("href",t)
        item.text(t)
        
    });
    
    
  }

}