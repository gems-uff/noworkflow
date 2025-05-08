import {Widget} from '@lumino/widgets';
import '../style/bootstrap.min.css';

import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';
import { Message } from '@lumino/messaging';
interface IAddMember {
    userId: string;
  }
interface IUser {
    id: string;
    login: string
  }
interface IGroup {
  id: string;
  name: string;
  members: Array<IUser>;
}

export 
class GroupWidget extends Widget {

  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  tBody: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  successFeedback: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  errorFeedback: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  userIn: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  addMemberForm: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  groups: Array<IGroup>;
  users: Array<IUser>;
  currentGroup: String;

  static createNode(): HTMLElement {
    let node = document.createElement('div');
    return node;
  }

  constructor() {
    super({ node: GroupWidget.createNode() });
    this.d3node = d3_select(this.node);

  
    this.addClass('content');
    this.title.label = "Group Information";
    this.title.closable = false
    this.title.caption = `Group`;
    this.setNode();
  }
  protected onBeforeShow(msg: Message): void {
    if(!this.groups){
        this.setGroups();
        this.setUsers();
    }
        
  }
  async setUsers(){
    var _thiss=this;
    _thiss.userIn.html("");
    var response= await fetch("users", {
        method: 'GET', // *GET, POST, PUT, DELETE, etc.
        headers: {
          'Content-Type': 'application/json'
        },
      })
      if(response.status==200){
        _thiss.users= new Array<IUser>();

        var obj=await response.json();


        obj.forEach( function(item: any){
          
            _thiss.users.push(<IUser>{
                id: item.id,
                login: item.userLogin
            });
        });        
      }else{
        this.showNode(_thiss.errorFeedback);
      }
      _thiss.users.forEach(function (obj: IUser) {

        _thiss.userIn.append("option").attr("value",obj.id).text(obj.login);

      });

  }
  resfreshGroups(){
    this.tBody.html("");
    this.setGroups();
  }
  async setGroups(){
    var _thiss=this;
    var response= await fetch("groups", {
        method: 'GET', // *GET, POST, PUT, DELETE, etc.
        headers: {
          'Content-Type': 'application/json'
        },
      })
      if(response.status==200){
        _thiss.groups= new Array<IGroup>();

        var obj=await response.json();

        obj.forEach( function(item: any){
            var group=<IGroup>{
                id: item.id,
                name:item.name,
                members: new Array<IUser>()
            }
            item.members.forEach( function(user: any){
                group.members.push( <IUser>{
                    id: user.id,
                    login: user.userLogin
                });
            });
            _thiss.groups.push(group);
        });        
      }else{
        this.showNode(_thiss.errorFeedback);
      }

      this.groups.forEach(function (obj: any) {
        _thiss.addGrpRow(obj);
      });

  }
  async deleteGrp(grpId:String){
    var response= await fetch("/groups/" +grpId, {
        method: 'DELETE', // *GET, POST, PUT, DELETE, etc.
        headers: {
          'Content-Type': 'application/json'
        },
      })
      if(response.status==200){
        this.showNode(this.successFeedback);
        this.resfreshGroups();
     
      }else{
        this.showNode(this.errorFeedback);
      }


  }
  addGrpRow(grp : IGroup){
    let _thiss=this;
    let item=this.tBody.append("tr");
    item.append("th").attr("scope","row").text(grp.id);
    item.append("td").text(grp.name);
    var membersText="";
    grp.members.forEach( function(user: IUser){
        membersText+= user.login + " "
    });
    item.append("td").text(membersText);
    var actions =item.append("td")
    var addMemberButton=actions.append("button").classed("btn btn-primary",true)
    .attr("type","submit").text("Add User");
    addMemberButton.on("click",function(){
        _thiss.showNode(_thiss.addMemberForm);
        _thiss.currentGroup=grp.id

      });
    var deleteGroupButton=actions.append("button").classed("btn btn-primary",true)
    .attr("type","submit").text("Delete Group");
    deleteGroupButton.on("click",function(){

        if(confirm("Are you sure you want to delete group: " + grp.name + " ?" )){
            _thiss.deleteGrp(grp.id);
        }

      });
      deleteGroupButton.style("margin-left",4);
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
  createAddGroupForm(projectsDiv:d3_Selection<d3_BaseType, {}, HTMLElement | null, any>){
    var _thiss=this;
    let inputsDiv=projectsDiv.append("div");
    let nameIn=this.addFormInput(inputsDiv,"groupNameInput","Name: ","input");
      
    let confimButton=inputsDiv.append("button").classed("btn btn-primary",true)
      .attr("type","submit").text("Confirm");
    let addGrpButton=projectsDiv.append("button").classed("btn btn-primary",true)
      .attr("type","submit").text("Add Group");
       inputsDiv.classed("d-none",true);
    
    confimButton.on("click",function(){
      _thiss.hideNode(_thiss.errorFeedback);
      _thiss.hideNode(_thiss.successFeedback);
      let newGrp=<IGroup>{
        name:nameIn.property("value"),
        members: new Array<IUser>()
      };
      fetch("groups", {
        method: 'POST', // *GET, POST, PUT, DELETE, etc.
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(newGrp) // body data type must match "Content-Type" header
      }).then((response)=>{
        if(response.status==201){
          response.json().then((obj)=>{
            newGrp.id=obj.id;
            _thiss.addGrpRow(newGrp);
            _thiss.hideNode(inputsDiv);
            _thiss.showNode(addGrpButton);
            _thiss.showNode(_thiss.successFeedback);
          });
          
        }else{
          _thiss.showNode(_thiss.errorFeedback);
        }
      });  
      
      
    });

    addGrpButton.on("click",function(){
        _thiss.showNode(inputsDiv);
        _thiss.hideNode(addGrpButton);
      });

  }
  createAddMemberForm(projectsDiv:d3_Selection<d3_BaseType, {}, HTMLElement | null, any>){
    var _thiss=this;
    _thiss.addMemberForm=projectsDiv.append("div");
    var inputsDiv =_thiss.addMemberForm;
    this.userIn=this.addFormInput(inputsDiv,"groupUsersInput","User","select");
  
    let confimButton=inputsDiv.append("button").classed("btn btn-primary",true)
      .attr("type","submit").text("Confirm");
  
    
    confimButton.on("click",function(){
      _thiss.hideNode(_thiss.errorFeedback);
      _thiss.hideNode(_thiss.successFeedback);

      var select = _thiss.userIn.node() as HTMLSelectElement;
      if(select!=null){
        var option = select.options[select.selectedIndex];

   
        
       
        let newGrp=<IAddMember>{
            userId: option.value,
        };
        fetch("groups/"+_thiss.currentGroup+"/users", {
            method: 'POST', // *GET, POST, PUT, DELETE, etc.
            headers: {
            'Content-Type': 'application/json'
            },
            body: JSON.stringify(newGrp) // body data type must match "Content-Type" header
        }).then((response)=>{
            if(response.status==201){
            response.json().then((obj)=>{
                _thiss.hideNode(_thiss.addMemberForm);
                _thiss.showNode(_thiss.successFeedback);
                _thiss.resfreshGroups();
            });
            
            }else{
            _thiss.showNode(_thiss.errorFeedback);
            
            }
        });  
     }
      
    });
    _thiss.hideNode(_thiss.addMemberForm);

  }
  setNode(){

    let content = this.d3node.append('div')
      .classed('config-content', true)

    let projectsDiv = content.append("div")

    projectsDiv.append("h2")
      .text("Groups:")

    this.errorFeedback= this.addFeedBackinfo(projectsDiv,"alert-danger","Error!","A problem has been occurred while submitting your data.") ;
    this.successFeedback= this.addFeedBackinfo(projectsDiv,"alert-success","Success!","") ; 
    this.hideNode(this.errorFeedback);
    
    this.hideNode(this.successFeedback);

    this.createAddMemberForm(projectsDiv);
    projectsDiv.append("br");
    this.createAddGroupForm(projectsDiv);

    
    let table = projectsDiv.append("table").classed("table",true);
    
    let header=table.append("thead").append("tr");  
    
    header.append("th").attr("scope","col").text("id");
    header.append("th").attr("scope","col").text("name");
    header.append("th").attr("scope","col").text("Members");
    header.append("th").attr("scope","col").text("Actions");
    
    this.tBody=table.append("tbody");

      
  }

}