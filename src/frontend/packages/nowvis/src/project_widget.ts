import { Widget } from '@lumino/widgets';
import '../style/bootstrap.min.css';

import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType
} from 'd3-selection';

interface IExperiment {
  id: string;
  name: string;
  description: string;
}

export class ProjectWidget extends Widget {
  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  expTBody: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  successFeedback: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  errorFeedback: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  experiments: Array<IExperiment>;

  static createNode(): HTMLElement {
    const node = document.createElement('div');
    return node;
  }

  constructor(experiments: Array<IExperiment>) {
    super({ node: ProjectWidget.createNode() });
    this.d3node = d3_select(this.node);
    this.experiments = experiments;
    this.setNode();
    this.addClass('content');
    this.title.label = 'Experiment Selection';
    this.title.closable = false;
    this.title.caption = `Experiment`;
  }
  addExpRow(exp: IExperiment) {
    const link = window.location.href + 'experiments/' + exp.id;
    const item = this.expTBody.append('tr');
    item.append('th').attr('scope', 'row').text(exp.id);
    item.append('td').text(exp.name);
    item.append('td').text(exp.description);
    item.append('td').append('a').attr('href', link).text(link);

    const cloneCommandText = 'now pull --url ' + link;
    item
      .append('td')
      .text(cloneCommandText + ' ')
      .append('i')
      .classed('fa fa-clone', true)
      .attr('aria-hidden', 'true')
      .attr('id', exp.id + 'CopyIcon')
      .on('click', () => {
        navigator.clipboard.writeText(cloneCommandText).then(() => {
          const divCopied = d3_select(
            document.getElementById(exp.id + 'CopyIcon')!
          )
            .append('small')
            .classed('alert alert-secondary p-0', true)
            .text('Copied!');
          setTimeout(() => {
            divCopied.remove();
          }, 3000);
        });
      });
  }
  addFormInput(
    form: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
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
    baseNode: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    cls: string,
    txt: string,
    desc: string
  ) {
    const _thiss = this;
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
        _thiss.hideNode(feedbackNode);
      });
    return feedbackNode;
  }
  hideNode(node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>) {
    node.classed('d-none', true);
  }
  showNode(node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>) {
    node.classed('d-none', false);
  }
  setNode() {
    const content = this.d3node.append('div').classed('config-content', true);

    const projectsDiv = content.append('div');

    projectsDiv.append('h2').text('Experiments:');

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
      'Experiment created successfully'
    );
    this.hideNode(this.errorFeedback);
    this.hideNode(this.successFeedback);

    const inputsDiv = projectsDiv.append('div');
    const nameIn = this.addFormInput(
      inputsDiv,
      'experimentNameInput',
      'Name',
      'input'
    );
    const descIn = this.addFormInput(
      inputsDiv,
      'experimentDescInput',
      'Description',
      'textarea'
    );
    const confimButton = inputsDiv
      .append('button')
      .classed('btn btn-primary', true)
      .attr('type', 'submit')
      .text('Confirm');
    const addExpButton = projectsDiv
      .append('button')
      .classed('btn btn-primary', true)
      .attr('type', 'submit')
      .text('Add Experiment');

    const table = projectsDiv.append('table').classed('table', true);

    const header = table.append('thead').append('tr');

    header.append('th').attr('scope', 'col').text('id');
    header.append('th').attr('scope', 'col').text('name');
    header.append('th').attr('scope', 'col').text('description');
    header.append('th').attr('scope', 'col').text('url');
    header
      .append('th')
      .attr('scope', 'col')
      .html('<i class="fa fa-terminal" aria-hidden="true"></i> clone ')
      .append('i')
      .classed('fa fa-question-circle-o', true)
      .attr('aria-hidden', 'true')
      .attr(
        'title',
        'Run this command on the command line, in the desired folder, to clone the experiment.'
      );

    this.expTBody = table.append('tbody');

    inputsDiv.classed('d-none', true);

    confimButton.on('click', () => {
      _thiss.hideNode(_thiss.errorFeedback);
      _thiss.hideNode(_thiss.successFeedback);
      const newExp = <IExperiment>{
        name: nameIn.property('value'),
        description: descIn.property('value')
      };
      fetch('experiments', {
        method: 'POST', // *GET, POST, PUT, DELETE, etc.
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(newExp) // body data type must match "Content-Type" header
      }).then(response => {
        if (response.status == 201) {
          response.json().then(obj => {
            newExp.id = obj.id;
            _thiss.addExpRow(newExp);
            _thiss.hideNode(inputsDiv);
            _thiss.showNode(addExpButton);
            _thiss.showNode(_thiss.successFeedback);
          });
        } else {
          _thiss.showNode(_thiss.errorFeedback);
        }
      });
    });
    var _thiss = this;
    addExpButton.on('click', () => {
      _thiss.showNode(inputsDiv);
      _thiss.hideNode(addExpButton);
    });

    this.experiments.forEach(obj => {
      _thiss.addExpRow(obj);
    });
  }
}
