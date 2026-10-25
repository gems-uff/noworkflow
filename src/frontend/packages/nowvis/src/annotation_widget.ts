import { Widget } from '@lumino/widgets';
import '../style/bootstrap.min.css';
import { Message } from '@lumino/messaging';
import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType
} from 'd3-selection';
import { NowVisPanel } from './nowpanel';
interface IAnnotation {
  id: string;
  annotationFormat: string;
  annotation: string;
  description: string;
  annotationLevel: string;
  provenanceType: string;
  relatedTrial: string;
  relatedExperiment: string;
}
export class AnnontationWidget extends Widget {
  d3node: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>;
  tBody: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>;
  table: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>;
  successFeedback: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>;
  errorFeedback: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>;
  anntTitle: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>;
  expId: string;
  trialId: string;
  fetchUrl: string;
  annotationLevel: string;
  annotations: Array<IAnnotation>;

  static createNode(): HTMLElement {
    const node = document.createElement('div');
    return node;
  }

  constructor(expId: string) {
    super({ node: AnnontationWidget.createNode() });
    this.d3node = d3_select(this.node);
    this.expId = expId;

    this.addClass('content');
    this.title.label = 'Annotation';
    this.title.closable = false;
    this.title.caption = `Annontation`;
    this.setNode();
    this.setAnnotationLevelToExperiment();
  }

  protected onBeforeHide(msg: Message): void {
    this.setAnnotationLevelToExperiment();
  }
  setAnnotationLevelToExperiment() {
    this.trialId = '';
    this.fetchUrl = '/experiments/' + this.expId + '/extendedAnnotation';
    this.annotationLevel = 'Experiment';
    this.anntTitle.text('Annotations for Experiment: ' + this.expId);
    this.setAnnotations();
  }
  setAnnotationLevelToTrial(trialId: string) {
    this.trialId = trialId;
    this.anntTitle.text('Annotations for Trial: ' + this.trialId);
    this.fetchUrl = '/trials/' + this.trialId + '/extendedAnnotation';
    this.annotationLevel = 'Trial';
    this.setAnnotations();
  }
  activeAnnotation(trialId: string) {
    const parentDock: NowVisPanel = this.parent as NowVisPanel;
    parentDock.activateWidget(this);
    this.setAnnotationLevelToTrial(trialId);
  }
  async fillAnnotations() {
    this.annotations = new Array<IAnnotation>();
    const response = await fetch(this.fetchUrl, {
      method: 'GET', // *GET, POST, PUT, DELETE, etc.
      headers: {
        'Content-Type': 'application/json'
      }
    });
    if (response.status === 200) {
      this.annotations = new Array<IAnnotation>();
      const obj = await response.json();

      obj.forEach((item: any) => {
        const annt = <IAnnotation>{
          id: item.id,
          provenanceType: item.provenanceType,
          annotationFormat: item.annotationFormat,
          description: item.description,
          annotationLevel: item.annotationLevel,
          relatedTrial: item.relatedTrial,
          relatedExperiment: item.relatedExperiment
        };

        this.annotations.push(annt);
      });
    } else {
      if (response.status !== 404) {
        this.showNode(this.errorFeedback);
      }
    }
  }
  addAnntRow(
    annt: IAnnotation,
    tBody: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>
  ) {
    const item = tBody.append('tr');
    item.append('th').attr('scope', 'row').text(annt.id);
    item.append('td').text(annt.description);
    item.append('td').text(annt.annotationFormat);

    item.append('td').text(annt.provenanceType);

    const actions = item.append('td');
    const addMemberButton = actions
      .append('button')
      .classed('btn btn-primary', true)
      .attr('type', 'submit')
      .text('Download Content');
    addMemberButton.on('click', () => {
      window.open('/extendedAnnotation/' + annt.id + '/annotation');
    });
  }
  async setAnnotations() {
    this.table.html('');
    const header = this.table.append('thead').append('tr');

    header.append('th').attr('scope', 'col').text('id');
    header.append('th').attr('scope', 'col').text('description');
    header.append('th').attr('scope', 'col').text('annotation Format');
    header.append('th').attr('scope', 'col').text('provenance Type');
    header.append('th').attr('scope', 'col').text('Actions');
    const tBody = this.table.append('tbody');

    await this.fillAnnotations();

    this.annotations.forEach((obj: any) => {
      this.addAnntRow(obj, tBody);
    });
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
  getValueFromSelect(
    node: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>,
    defaultVale: string
  ): string {
    let option = defaultVale;

    const select = node.node() as HTMLSelectElement;
    if (select != null) {
      option = select.options[select.selectedIndex].value;
    }
    return option;
  }
  createAddGroupForm(
    projectsDiv: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>
  ) {
    const inputsDiv = projectsDiv.append('div');
    const descIn = this.addFormInput(
      inputsDiv,
      'descriptionAnntInput',
      'Description',
      'textarea'
    );
    const annotationIn = this.addFormInput(
      inputsDiv,
      'annotationNameInput',
      'Annotation',
      'textarea'
    );
    const annotationFormatIn = this.addFormInput(
      inputsDiv,
      'annotationFormatInput',
      'Annotation Format',
      'select'
    );
    const provenanceTypeIn = this.addFormInput(
      inputsDiv,
      'provenanceTypeInput',
      'Provenance Type',
      'select'
    );

    provenanceTypeIn.append('option').attr('value', 'Data').text('Data');
    provenanceTypeIn
      .append('option')
      .attr('value', 'Interaction')
      .text('Interaction');
    provenanceTypeIn.append('option').attr('value', 'Insight').text('Insight');
    provenanceTypeIn.append('option').attr('value', 'Other').text('Other');
    provenanceTypeIn
      .append('option')
      .attr('value', 'Rationale')
      .text('Rationale');
    provenanceTypeIn
      .append('option')
      .attr('value', 'Visualization')
      .text('Visualization');

    annotationFormatIn
      .append('option')
      .attr('value', 'plainText')
      .text('plain text');
    annotationFormatIn.append('option').attr('value', 'base64').text('base64');
    annotationFormatIn.append('option').attr('value', 'JSON').text('JSON');
    annotationFormatIn.append('option').attr('value', 'XML').text('XML');

    const confimButton = inputsDiv
      .append('button')
      .classed('btn btn-primary', true)
      .attr('type', 'submit')
      .text('Confirm');
    const addAnntButton = projectsDiv
      .append('button')
      .classed('btn btn-primary', true)
      .attr('type', 'submit')
      .text('Add Annotation');
    inputsDiv.classed('d-none', true);

    confimButton.on('click', () => {
      const annotationFormat = this.getValueFromSelect(
        annotationFormatIn,
        'plainText'
      );
      const provenanceType = this.getValueFromSelect(provenanceTypeIn, 'Other');

      this.hideNode(this.errorFeedback);
      this.hideNode(this.successFeedback);

      const newAnnotation = <IAnnotation>{
        annotation: annotationIn.property('value'),
        description: descIn.property('value'),
        annotationFormat: annotationFormat,
        annotationLevel: this.annotationLevel,
        provenanceType: provenanceType
      };

      fetch(this.fetchUrl, {
        method: 'POST', // *GET, POST, PUT, DELETE, etc.
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(newAnnotation) // body data type must match "Content-Type" header
      }).then(response => {
        if (response.status === 201) {
          response.json().then(obj => {
            this.showNode(this.successFeedback);
            this.hideNode(inputsDiv);
            this.showNode(addAnntButton);
            this.setAnnotations();
          });
        } else {
          this.showNode(this.errorFeedback);
        }
      });
    });

    addAnntButton.on('click', () => {
      this.showNode(inputsDiv);
      this.hideNode(addAnntButton);
    });
  }

  setNode() {
    const content = this.d3node.append('div').classed('config-content', true);

    const projectsDiv = content.append('div');

    this.anntTitle = projectsDiv.append('h2');

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

    this.createAddGroupForm(projectsDiv);

    this.table = projectsDiv.append('table').classed('table', true);
  }
}
