import { Widget } from '@lumino/widgets';
import '../style/bootstrap.min.css';

import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType
} from 'd3-selection';
import { Message } from '@lumino/messaging';
interface IAddMember {
  userId: string;
}
interface IUser {
  id: string;
  login: string;
}
interface IGroup {
  id: string;
  name: string;
  members: Array<IUser>;
}

export class GroupWidget extends Widget {
  d3node: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>;
  tBody: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>;
  successFeedback: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>;
  errorFeedback: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>;
  userIn: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>;
  addMemberForm: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>;
  groups: Array<IGroup>;
  users: Array<IUser>;
  currentGroup: string;

  static createNode(): HTMLElement {
    const node = document.createElement('div');
    return node;
  }

  constructor() {
    super({ node: GroupWidget.createNode() });
    this.d3node = d3_select(this.node);

    this.addClass('content');
    this.title.label = 'Group Information';
    this.title.closable = false;
    this.title.caption = `Group`;
    this.setNode();
  }
  protected onBeforeShow(msg: Message): void {
    if (!this.groups) {
      this.setGroups();
      this.setUsers();
    }
  }
  async setUsers() {
    this.userIn.html('');
    const response = await fetch('users', {
      method: 'GET', // *GET, POST, PUT, DELETE, etc.
      headers: {
        'Content-Type': 'application/json'
      }
    });
    if (response.status === 200) {
      this.users = new Array<IUser>();

      const obj = await response.json();

      obj.forEach((item: any) => {
        this.users.push(<IUser>{
          id: item.id,
          login: item.userLogin
        });
      });
    } else {
      this.showNode(this.errorFeedback);
    }
    this.users.forEach((obj: IUser) => {
      this.userIn.append('option').attr('value', obj.id).text(obj.login);
    });
  }
  resfreshGroups() {
    this.tBody.html('');
    this.setGroups();
  }
  async setGroups() {
    const response = await fetch('groups', {
      method: 'GET', // *GET, POST, PUT, DELETE, etc.
      headers: {
        'Content-Type': 'application/json'
      }
    });
    if (response.status === 200) {
      this.groups = new Array<IGroup>();

      const obj = await response.json();

      obj.forEach((item: any) => {
        const group = <IGroup>{
          id: item.id,
          name: item.name,
          members: new Array<IUser>()
        };
        item.members.forEach((user: any) => {
          group.members.push(<IUser>{
            id: user.id,
            login: user.userLogin
          });
        });
        this.groups.push(group);
      });
    } else {
      this.showNode(this.errorFeedback);
    }

    this.groups.forEach((obj: any) => {
      this.addGrpRow(obj);
    });
  }
  async deleteGrp(grpId: string) {
    const response = await fetch('/groups/' + grpId, {
      method: 'DELETE', // *GET, POST, PUT, DELETE, etc.
      headers: {
        'Content-Type': 'application/json'
      }
    });
    if (response.status === 200) {
      this.showNode(this.successFeedback);
      this.resfreshGroups();
    } else {
      this.showNode(this.errorFeedback);
    }
  }
  addGrpRow(grp: IGroup) {
    const item = this.tBody.append('tr');
    item.append('th').attr('scope', 'row').text(grp.id);
    item.append('td').text(grp.name);
    let membersText = '';
    grp.members.forEach((user: IUser) => {
      membersText += user.login + ' ';
    });
    item.append('td').text(membersText);
    const actions = item.append('td');
    const addMemberButton = actions
      .append('button')
      .classed('btn btn-primary', true)
      .attr('type', 'submit')
      .text('Add User');
    addMemberButton.on('click', () => {
      this.showNode(this.addMemberForm);
      this.currentGroup = grp.id;
    });
    const deleteGroupButton = actions
      .append('button')
      .classed('btn btn-primary', true)
      .attr('type', 'submit')
      .text('Delete Group');
    deleteGroupButton.on('click', () => {
      if (
        confirm('Are you sure you want to delete group: ' + grp.name + ' ?')
      ) {
        this.deleteGrp(grp.id);
      }
    });
    deleteGroupButton.style('margin-left', 4);
  }
  addFormInput(
    form: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>,
    fieldId: string,
    fieldLabel: string,
    fieldType: string
  ) {
    const grp = form.append('div').classed('form-group row', true);
    grp
      .append('label')
      .classed('col-sm-2 col-form-label', true)
      .attr('for', fieldId)
      .text(fieldLabel + ': ');
    const divIn = grp.append('div').classed('col-sm-10', true);
    const inp = divIn.append(fieldType);
    inp.classed('form-control', true).attr('id', fieldId);
    return inp;
  }
  addFeedBackinfo(
    baseNode: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>,
    cls: string,
    txt: string,
    desc: string
  ) {
    const feedbackNode = baseNode
      .append('div')
      .classed('alert', true)
      .classed(cls, true)
      .classed('alert-dismissible', true)
      .classed('fade', true)
      .classed('show', true);
    feedbackNode.append('strong').text(txt);
    feedbackNode
      .append('span')
      .text(' ' + desc)
      .append('button')
      .attr('type', 'button')
      .classed('close', true)
      .attr('data-dismiss', 'alert')
      .text('x')
      .on('click', () => {
        this.hideNode(feedbackNode);
      });
    return feedbackNode;
  }
  hideNode(node: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>) {
    node.classed('d-none', true);
  }
  showNode(node: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>) {
    node.classed('d-none', false);
  }
  createAddGroupForm(
    projectsDiv: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>
  ) {
    const inputsDiv = projectsDiv.append('div');
    const nameIn = this.addFormInput(
      inputsDiv,
      'groupNameInput',
      'Name: ',
      'input'
    );

    const confimButton = inputsDiv
      .append('button')
      .classed('btn btn-primary', true)
      .attr('type', 'submit')
      .text('Confirm');
    const addGrpButton = projectsDiv
      .append('button')
      .classed('btn btn-primary', true)
      .attr('type', 'submit')
      .text('Add Group');
    inputsDiv.classed('d-none', true);

    confimButton.on('click', () => {
      this.hideNode(this.errorFeedback);
      this.hideNode(this.successFeedback);
      const newGrp = <IGroup>{
        name: nameIn.property('value'),
        members: new Array<IUser>()
      };
      fetch('groups', {
        method: 'POST', // *GET, POST, PUT, DELETE, etc.
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(newGrp) // body data type must match "Content-Type" header
      }).then(response => {
        if (response.status === 201) {
          response.json().then(obj => {
            newGrp.id = obj.id;
            this.addGrpRow(newGrp);
            this.hideNode(inputsDiv);
            this.showNode(addGrpButton);
            this.showNode(this.successFeedback);
          });
        } else {
          this.showNode(this.errorFeedback);
        }
      });
    });

    addGrpButton.on('click', () => {
      this.showNode(inputsDiv);
      this.hideNode(addGrpButton);
    });
  }
  createAddMemberForm(
    projectsDiv: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>
  ) {
    this.addMemberForm = projectsDiv.append('div');
    const inputsDiv = this.addMemberForm;
    this.userIn = this.addFormInput(
      inputsDiv,
      'groupUsersInput',
      'User',
      'select'
    );

    const confimButton = inputsDiv
      .append('button')
      .classed('btn btn-primary', true)
      .attr('type', 'submit')
      .text('Confirm');

    confimButton.on('click', () => {
      this.hideNode(this.errorFeedback);
      this.hideNode(this.successFeedback);

      const select = this.userIn.node() as HTMLSelectElement;
      if (select != null) {
        const option = select.options[select.selectedIndex];

        const newGrp = <IAddMember>{
          userId: option.value
        };
        fetch('groups/' + this.currentGroup + '/users', {
          method: 'POST', // *GET, POST, PUT, DELETE, etc.
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(newGrp) // body data type must match "Content-Type" header
        }).then(response => {
          if (response.status === 201) {
            response.json().then(obj => {
              this.hideNode(this.addMemberForm);
              this.showNode(this.successFeedback);
              this.resfreshGroups();
            });
          } else {
            this.showNode(this.errorFeedback);
          }
        });
      }
    });
    this.hideNode(this.addMemberForm);
  }
  setNode() {
    const content = this.d3node.append('div').classed('config-content', true);

    const projectsDiv = content.append('div');

    projectsDiv.append('h2').text('Groups:');

    this.errorFeedback = this.addFeedBackinfo(
      projectsDiv,
      'alert-danger',
      'Error!',
      'A problem has been occurred while submitting your data.'
    );
    this.successFeedback = this.addFeedBackinfo(
      projectsDiv,
      'alert-success',
      'Success!',
      ''
    );
    this.hideNode(this.errorFeedback);

    this.hideNode(this.successFeedback);

    this.createAddMemberForm(projectsDiv);
    projectsDiv.append('br');
    this.createAddGroupForm(projectsDiv);

    const table = projectsDiv.append('table').classed('table', true);

    const header = table.append('thead').append('tr');

    header.append('th').attr('scope', 'col').text('id');
    header.append('th').attr('scope', 'col').text('name');
    header.append('th').attr('scope', 'col').text('Members');
    header.append('th').attr('scope', 'col').text('Actions');

    this.tBody = table.append('tbody');
  }
}
