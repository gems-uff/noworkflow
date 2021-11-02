import {Widget} from '@phosphor/widgets';
import '../style/bootstrap.min.css';

import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';

interface IExperiment {
  id: string;
  name: string;
  description: string;
}

export
class ProjectWidget extends Widget {

  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  expTBody: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  successFeedback: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  errorFeedback: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
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
  addExpRow(exp : IExperiment){
    var link=window.location.href + "experiments/"+exp.id;
    let item=this.expTBody.append("tr");
    item.append("th").attr("scope","row").text(exp.id);
    item.append("td").text(exp.name);
    item.append("td").text(exp.description);
    item.append("td").append("a").attr("href",link).text(link);   
  }
  addFormInput(form:d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
      fieldId:string,fieldLabel:string,fieldType:string){
    let grp=form.append("div").classed("form-group row",true);
    grp.append("label").classed("col-sm-2 col-form-label",true).attr("for",fieldId).text(fieldLabel + ": ");
    let divIn=grp.append("div").classed("col-sm-10",true)
    let inp=divIn.append(fieldType);
      inp.classed("form-control",true).attr("id",fieldId);
    return inp;
  }
  addFeedBackinfo(baseNode: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
      cls:string,txt:string,desc:string){
    let _thiss=this;
    let feedbackNode=baseNode.append("div")
      .classed("alert",true)
      .classed(cls,true)
      .classed("alert-dismissible",true)
      .classed("fade",true)
      .classed("show",true);
    feedbackNode.append("strong").text(txt);
    feedbackNode.append("span").text(" "+desc)
      .append("button").attr("type","button").classed("close",true)
      .attr("data-dismiss","alert").text("x")
      .on("click",function(){
        _thiss.hideNode(feedbackNode);
      });
      return feedbackNode;
  }
  hideNode(node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>){
    node.classed("d-none",true);  
  }
  showNode(node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>){
    node.classed("d-none",false);  
  }
  setNode(){

    let content = this.d3node.append('div')
      .classed('config-content', true)

    let projectsDiv = content.append("div")

    projectsDiv.append("h2")
      .text("Experiments:")

    this.errorFeedback= this.addFeedBackinfo(projectsDiv,"alert-danger","Error!","A problem has been occurred while submitting your data.") ;
    this.successFeedback= this.addFeedBackinfo(projectsDiv,"alert-success","Success!","Experiment created successfully") ; 
    this.hideNode(this.errorFeedback);
    this.hideNode(this.successFeedback);

    let inputsDiv=projectsDiv.append("div");
    let nameIn=this.addFormInput(inputsDiv,"experimentNameInput","Name","input");
    let descIn=this.addFormInput(inputsDiv,"experimentDescInput","Description","textarea");
    let confimButton=inputsDiv.append("button").classed("btn btn-primary",true)
      .attr("type","submit").text("Confirm");
    let addExpButton=projectsDiv.append("button").classed("btn btn-primary",true)
      .attr("type","submit").text("Add Experiment");


    let table = projectsDiv.append("table").classed("table",true);
    
    let header=table.append("thead").append("tr");  
    
    header.append("th").attr("scope","col").text("id");
    header.append("th").attr("scope","col").text("name");
    header.append("th").attr("scope","col").text("description");
    header.append("th").attr("scope","col").text("url");
    
    this.expTBody=table.append("tbody");

   
    inputsDiv.classed("d-none",true);
    
    confimButton.on("click",function(){
      _thiss.hideNode(_thiss.errorFeedback);
      _thiss.hideNode(_thiss.successFeedback);
      let newExp=<IExperiment>{
        name:nameIn.property("value"),
        description:descIn.property("value")
      };
      fetch("experiments", {
        method: 'POST', // *GET, POST, PUT, DELETE, etc.
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(newExp) // body data type must match "Content-Type" header
      }).then((response)=>{
        if(response.status==201){
          response.json().then((obj)=>{
            newExp.id=obj.id;
            _thiss.addExpRow(newExp);
            _thiss.hideNode(inputsDiv);
            _thiss.showNode(addExpButton);
            _thiss.showNode(_thiss.successFeedback);
          });
          
        }else{
          _thiss.showNode(_thiss.errorFeedback);
        }
      });  
      
      
    });
    var _thiss=this;
    addExpButton.on("click",function(){
      _thiss.showNode(inputsDiv);
        _thiss.hideNode(addExpButton);
      });
    
    this.experiments.forEach(function (obj) {
      _thiss.addExpRow(obj);
    });
  }

}