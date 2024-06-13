import 'd3-transition';

import {
  rgb as d3_rgb,
} from 'd3-color';

import {
  scaleOrdinal as d3_scaleOrdinal,
} from 'd3-scale';

import {
  schemeCategory10 as d3_schemeCategory10
} from 'd3-scale-chromatic';


import {
  BaseType as d3_BaseType,
  Selection as d3_Selection,
  select as d3_select,
} from 'd3-selection';

import {
  zoom as d3_zoom,
  zoomIdentity as d3_zoomIdentity,
} from 'd3-zoom';

import { instance } from "@viz-js/viz";

import * as fs from 'file-saver';
declare var require: any;
const pl = require("tau-prolog");

import { HistoryConfig, HistoryState } from './config';
import { VisibleHistoryNode, VisibleHistoryEdge } from './structures';
import { HistoryGraphData, HistoryNodeData, HistoryTrialNodeData } from './structures';
import { D3ZoomEvent } from 'd3';
import { event } from 'jquery';
import { config } from 'webpack';


export
  class HistoryGraph {

  config: HistoryConfig;
  state: HistoryState;
  graphId: string;
  zoom: any;
  transform: any;
  i: number;

  div: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  tooltipDiv: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  svg: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  g: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  hintElement: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  rightClickMenu: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;

  nodes: VisibleHistoryNode[] = [];
  versionNodes: VisibleHistoryNode[] = [];
  edges: VisibleHistoryEdge[] = [];
  maxX: number = 0;
  maxY: number = 0;
  maxId: number = 0;
  modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>;



  constructor(graphId: string, div: any, config: any = {}) {
    this.i = 0;
    var defaultConfig: HistoryConfig = {
      customSelectNode: (g: HistoryGraph, d: VisibleHistoryNode) => false,
      customCtrlClick: (g: HistoryGraph, d: VisibleHistoryNode) => false,
      customForm: (g: HistoryGraph, form: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>) => null,
      customSize: (g: HistoryGraph) => [g.config.width, g.config.height],
      customWindowTabCommand: (trialIdSimplified: string, trialId: string, command: string) => false,

      hintMessage: "Ctrl+Shift click or ⌘+Shift click to diff trials",

      width: 200,
      height: 100,

      radius: 20,
      moveX: 20,
      moveY: 25,
      moveY2: 10,
      spacing: 17,
      margin: 50,

      fontSize: 10,
      useTooltip: false,
    }
    this.config = (Object as any).assign({}, defaultConfig, config);

    this.graphId = graphId;

    this.zoom = d3_zoom<SVGSVGElement, any>()
      .on("zoom", (event: D3ZoomEvent<SVGSVGElement, any>) => {
        return this.zoomFunction(event);
      })
      .on("start", () => d3_select('body').style("cursor", "move"))
      .on("end", () => d3_select('body').style("cursor", "auto"))
      .wheelDelta(function () {
        const e = event as WheelEvent;
        return -e.deltaY * (e.deltaMode ? 120 : 1) / 2000;
      })

    this.div = d3_select(div);
    let form = d3_select<HTMLFormElement, any>(div)
      .append("form")
      .classed("history-toolbar", true);

    this.svg = d3_select<SVGSVGElement, any>(div)
      .append("div")
      .append("svg")
      .attr("width", this.config.width)
      .attr("height", this.config.height)
      .call(this.zoom)
      .on("mouseup", () => this.svgMouseUp());

    this.state = {
      selectedNode: null,
      mouseDownNode: null,
      justScale: false
    }

    // Tooltip
    this.tooltipDiv = d3_select<HTMLDivElement, any>("body").append("div")
      .classed("now-tooltip now-history-tooltip", true)
      .style("opacity", 0)
      .style("max-width", "250px")
      .on("mouseout", () => {
        this.closeTooltip();
      });

    this.createToolbar(form);

    this.createMarker('end-arrow', 'endarrow', '#000');

    this.g = this.svg.append("g")
      .attr("id", this._graphId())
      .attr("transform", "translate(0,0)")
      .classed('HistoryGraph', true);

    this.rightClickMenu = d3_select<SVGSVGElement, any>(div).append("div")
      .classed("dropdown-menu dropdown-menu-sm", true)
      .attr("id", "context-menu")
      .attr("selected-trial", "")
      .style("display", "block");

    this.buildModal(div);
    this.buildRightClickMenu();
  }

  private buildModal(div: any) {
    this.modal = d3_select<SVGSVGElement, any>(div).append("div")
      .classed("modal fade", true)
      .attr("id", "commandsModal")
      .attr("tabindex", "-1")
      .attr("role", "dialog")
      .attr("aria-labelledby", "commandsModalTitle")
      .style("display", "none")
      .attr("aria-hidden", "true");

    let modalContent = this.modal.append("div")
      .classed("modal-dialog", true)
      .attr("role", "document")
      .append("div").classed("modal-content", true); //modal content

    let modalHeader = modalContent.append("div")
      .classed("modal-header", true)//modal header
    modalHeader.append("h5")
      .classed("modal-title", true)
      .attr("id", "exampleModalTitle")
      .text("Change Temporary Title") //modal title

    this.modalBody = modalContent.append("div")
      .classed("modal-body", true);

    modalHeader.append("button").classed("close", true).attr("type", "button").text("x").style("float", "right")
      .on("click", () => cleanModalBodyAndClose(this.modal, this.modalBody)); //close modal
  }

  private buildRightClickMenu() {

    //let modal = document.getElementById("commandsModal");
    this.buildRestoreTrialCommand(this.modal, this.modalBody);
    this.buildRestoreFileCommand(this.modal, this.modalBody);
    this.buildProvCommand(this.config);
    this.buildExportPrologCommand(this.modal, this.modalBody, this.config)
    this.buildDataflowCommand(this.modal, this.modalBody, this.config)
  }

  buildDataflowCommand(modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>, config: HistoryConfig) {

    this.rightClickMenu.append("a")
      .classed("dropdown-item", true)
      .attr("href", "#")
      .attr("id", "dataflow-option")
      .text("export dataflow")
      .on("click", function () {

        let parent = this.parentNode as Element
        let trialId = parent.getAttribute("selected-trial");

        buildDataflowModal(modal, modalBody, parent, config, trialId);
      });

  };



  buildExportPrologCommand(modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>, config: HistoryConfig) {

    this.rightClickMenu.append("a")
      .classed("dropdown-item", true)
      .attr("href", "#")
      .attr("id", "export-option")
      .text("export prolog")
      .on("click", function () {

        let parent = this.parentNode as Element
        let trialId = parent.getAttribute("selected-trial");
        let exportUrl = "/commands/export/" + trialId;
        let exportWindowId = "Export window " + trialId;


        buildExportPrologModal(modal, modalBody, exportUrl, config, parent, exportWindowId, trialId);

      });
  }

  buildProvCommand(config: HistoryConfig) {
    this.rightClickMenu.append("a")
      .classed("dropdown-item", true)
      .attr("href", "#")
      .attr("id", "prov-option")
      .text("export prov")
      .on("click", function () {
        let parent = this.parentNode as Element;
        let trialId = parent.getAttribute("selected-trial");
        let provWindowId = "Prov window " + trialId;

        if (document.getElementById(provWindowId)) return;


        let provUrl = "/commands/prov/" + trialId;


        fetch(provUrl, {
          method: 'GET', // *GET, POST, PUT, DELETE, etc.
          headers: {
            'Content-Type': 'application/json'
          },
        }).then((response) => {
          response.json().then((json) => {

            config.customWindowTabCommand(parent.getAttribute("selected-trial-simplified")!, provWindowId, "Prov");
            let provWindow = d3_select(document.getElementById(provWindowId));


            if (response.status == 200) {
              provWindow.style("overflow-y", "auto");
              let prov_lines = json.prov.split("\n");
              for (var line in prov_lines) provWindow.append("p").text(prov_lines[line]);

            } else {
              window.alert("No prov to export");
            }

          });
        });
      });
  }

  private buildRestoreFileCommand(modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>) {
    this.rightClickMenu.append("a")
      .classed("dropdown-item", true)
      .attr("href", "#")
      .attr("id", "restore-file-option")
      .text("restore file")
      .on("click", function () {
        let parent = this.parentNode as Element;
        let trialId = parent.getAttribute("selected-trial");

        let trialFiles: string[];

        fetch("/files/" + trialId, {
          method: 'GET', // *GET, POST, PUT, DELETE, etc.
          headers: {
            'Content-Type': 'application/json'
          },
        }).then((response) => {
          response.json().then((json) => {

            trialFiles = json.files

            changeTitle(parent, "Restore file trial ")

            let submitButton;
            let form: d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>;

            showModal(modal);

            if (modalBody) {
              form = modalBody.append("form").attr("onsubmit", "return false;");
              //createFormTextInput(form, "restoreFile", "Restore file", "restoreFileHelp", "Write the name of the file you want to restore");
              createFormSelectInput(form, "restoreFile", "Restore file", 0, trialFiles.length - 1, 0, "", "", trialFiles);
              createFormTextInput(form, "restoreFileID", "File identifier", "restoreIDHelp", "(optional) Identifies the file to be restored. It can be either the timestamp, the number of access, or the code hash");
              createFormTextInput(form, "restoreFileTarget", "Target file path", "restoreTargetHelp", "(optional) specifies the target path of the restored file");

              submitButton = form.append("button").classed("btn btn-primary mb-2", true).attr("type", "submit").text("restore trial");

            }

            submitButton?.on("click", function () {
              //let fileToRestore : string | boolean = getTextInputFormByID("restoreFile", true);
              let fileToRestore = (<HTMLSelectElement>document.getElementById("restoreFile")).selectedOptions[0].value;
              let fileIdentifier: string | boolean = getTextInputFormByID("restoreFileID", true);
              let targetPath: string | boolean = getTextInputFormByID("restoreFileTarget", false);

              let restoreUrl = "/commands/restore/file/" + trialId + "/" + fileToRestore + "/" + fileIdentifier + "/" + targetPath;

              if (fileToRestore) getRestoreOrCollabCommand(restoreUrl, form, modalBody);
              else addAlert(modalBody, "alert-danger", "Error!", "The file's name is empty");

            });
          });

        });
      });
  }

  private buildRestoreTrialCommand(modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>) {

    this.rightClickMenu.append("a")
      .classed("dropdown-item", true)
      .attr("href", "#")
      .attr("id", "restore-trial-option")
      .text("restore trial")
      .on("click", function () {

        let parent = this.parentNode as Element;
        let trialId = parent.getAttribute("selected-trial");
        changeTitle(parent, "Restore trial ");

        let submitButton;
        let form: d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>;

        showModal(modal);

        if (modalBody) {
          form = modalBody.append("form").attr("onsubmit", "return false;");
          createFormCheckInput(form, "restoreSkipScript", "Skip Script");
          createFormCheckInput(form, "restoreSkipLocalModules", "Skip Local Modules");
          createFormCheckInput(form, "restoreSkipFileAccess", "Skip File Access");

          submitButton = form.append("button").classed("btn btn-primary mb-2", true).attr("type", "submit").text("restore trial");

        }

        submitButton?.on("click", function () {
          let skipScript = (<HTMLInputElement>document.getElementById("restoreSkipScript")).checked;
          let skipModules = (<HTMLInputElement>document.getElementById("restoreSkipLocalModules")).checked;
          let skipFileAccess = (<HTMLInputElement>document.getElementById("restoreSkipFileAccess")).checked;

          let restoreUrl = "/commands/restore/trial/" + trialId + "/" + skipScript + "/" + skipModules + "/" + skipFileAccess;

          getRestoreOrCollabCommand(restoreUrl, form, modalBody);

        });
      });
  }

  private buildAddRemote(modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>) {
    document.getElementById("exampleModalTitle")!.textContent = "Add new remote";

    let submitButton;
    let form: d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>;

    showModal(modal);

    if (modalBody) {
      form = modalBody.append("form").attr("onsubmit", "return false;");
      createFormTextInput(form, "inputAddRemoteUrl", "Remote URL: ");
      createFormTextInput(form, "inputAddRemoteName", "Remote name: ");
      submitButton = form.append("button").classed("btn btn-primary mb-2", true).text("Add remote");
    }

    submitButton?.on("click", function () {
      let remoteURL = (<HTMLInputElement>document.getElementById("inputAddRemoteUrl")).value;
      let remoteName = (<HTMLInputElement>document.getElementById("inputAddRemoteName")).value;

      let addRemoteURL = "/collab/remotes/add/" + remoteName + "/" + remoteURL;

      fetch(addRemoteURL, {
        method: 'POST', // *GET, POST, PUT, DELETE, etc.
        headers: {
          'Content-Type': 'application/json'
        },
      }).then((response) => {

        response.json().then((json) => {
          form.remove();
          if (response.status == 200) {
            addAlert(modalBody, "alert-success", "Success!", json.terminal_text);
          } else {
            addAlert(modalBody, "alert-danger", "Error!", "");
          }

        });
      });

    });
  }

  private buildEditRemote(modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>) {

    fetch("/collab/remotes/getall", {
      method: 'GET', // *GET, POST, PUT, DELETE, etc.
      headers: {
        'Content-Type': 'application/json'
      },
    }).then((response) => {

      response.json().then(async (json) => {
        if (response.status == 200) {
          this.executeCollabCommand(modal, modalBody, "editRemoteServerUrlId", "Edit remote", "edit", json.remotes);
        } else {
          console.log("Failed to get remotes");
        }

      });
    });

  }

  private buildPushCommand(modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>) {

    fetch("/collab/remotes/getall", {
      method: 'GET', // *GET, POST, PUT, DELETE, etc.
      headers: {
        'Content-Type': 'application/json'
      },
    }).then((response) => {

      response.json().then(async (json) => {
        if (response.status == 200) {
          this.executeCollabCommand(modal, modalBody, "pushServerUrlId", "Push experiment", "push", json.remotes);
        } else {
          console.log("Failed to get remotes");
        }

      });
    });

  }

  private buildPullCommand(modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>) {

    fetch("/collab/remotes/getall", {
      method: 'GET', // *GET, POST, PUT, DELETE, etc.
      headers: {
        'Content-Type': 'application/json'
      },
    }).then((response) => {

      response.json().then(async (json) => {
        if (response.status == 200) {
          this.executeCollabCommand(modal, modalBody, "pullServerUrlId", "Pull experiment", "pull", json.remotes);
        } else {
          console.log("Failed to get remotes");
        }

      });
    });

  }

  private executeCollabCommand(modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>, serverUrlId: string, title: string, command: string, remotes: any) {
    document.getElementById("exampleModalTitle")!.textContent = title;

    let submitButton;
    let form: d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>;

    showModal(modal);

    let select: d3_Selection<HTMLSelectElement, {}, HTMLElement | null, any>;

    if (modalBody) {
      form = modalBody.append("form").attr("onsubmit", "return false;");
      form.append("label").attr("for", "remotes").text("Remote: ");

      select = form.append("select").attr("name", "remotes").attr("id", "remotes");
      for (let i = 0; i < remotes.length; i++) {
        select.append("option").attr("value", remotes[i].server_url).text(remotes[i].name);
      }

      form.append("br");
      form.append("span").text("Remote URL: ");
      let remoteURLText = form.append("span").attr("id", serverUrlId + "Remote").text(remotes[0].server_url);
      select.on("change", () => {
        remoteURLText.text(select.node()!.value);
      })

      form.append("br");
      if (command == "edit") {
        createFormTextInput(form, "inputEditRemoteName", "Remote new name: ");
      }
      submitButton = form.append("button").classed("btn btn-primary mb-2", true).text(title);
    }

    submitButton?.on("click", function () {
      let serverUrl = select.node()!.value;

      let collabCommandUrl = "/commands/" + command + "/" + serverUrl;
      if (command == "edit") collabCommandUrl = "/collab/remotes/edit/" + (<HTMLInputElement>document.getElementById("inputEditRemoteName")).value + "/" + serverUrl;

      getRestoreOrCollabCommand(collabCommandUrl, form, modalBody);

    });
  }

  createToolbar(form: d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>) {
    let formdiv = form.append("div")
      .classed("buttons", true);
    this.config.customForm(this, formdiv);
    // Reset zoom
    formdiv.append("a")
      .classed("toollink", true)
      .attr("id", "history-" + this.graphId + "-history-zoom")
      .attr("href", "#")
      .attr("title", "Restore zoom")
      .on("click", () => this.restorePosition())
      .append("i")
      .classed("fa fa-eye", true)

    // Toggle Tooltips
    let tooltipsToggle = formdiv.append("input")
      .attr("id", "history-" + this.graphId + "-toolbar-tooltips")
      .attr("type", "checkbox")
      .attr("name", "history-toolbar-tooltips")
      .attr("value", "show")
      .property("checked", this.config.useTooltip)
      .on("change", () => {
        this.closeTooltip();
        this.config.useTooltip = tooltipsToggle.property("checked");
      });
    formdiv.append("label")
      .attr("for", "history-" + this.graphId + "-toolbar-tooltips")
      .attr("title", "Show tooltips on mouse hover")
      .append("i")
      .classed("fa fa-comment", true)

    // Download SVG
    formdiv.append("a")
      .classed("toollink", true)
      .attr("id", "history-" + this.graphId + "-download")
      .attr("href", "#")
      .attr("title", "Download graph SVG")
      .on("click", () => {
        this.download();
      })
      .append("i")
      .classed("fa fa-download", true)

    // Set Font Size
    let fontToggle = formdiv.append("input")
      .attr("id", "history-" + this.graphId + "-toolbar-fonts")
      .attr("type", "checkbox")
      .attr("name", "history-toolbar-fonts")
      .attr("value", "show")
      .property("checked", false)
      .on("change", () => {
        let display = fontToggle.property("checked") ? "inline-block" : "none";
        fontSize.style("display", display);
      });
    formdiv.append("label")
      .attr("for", "history-" + this.graphId + "-toolbar-fonts")
      .attr("title", "Set font size")
      .append("i")
      .classed("fa fa-font", true)
    let fontSize = formdiv.append("input")
      .attr("type", "number")
      .attr("value", this.config.fontSize)
      .style("width", "50px")
      .style("display", "none")
      .attr("title", "Node font size")
      .on("change", () => {
        this.config.fontSize = fontSize.property("value");
        this.svg.selectAll("text.trial-id")
          .attr("font-size", this.config.fontSize);
      })

    // Submit
    formdiv.append("input")
      .attr("type", "submit")
      .attr("name", "prevent-enter")
      .attr("onclick", "return false;")
      .style("display", "none");

    // Push trial
    formdiv.append("a")
      .classed("toollink", true)
      .attr("id", "history-" + this.graphId + "-push-trial")
      .attr("href", "#")
      .attr("title", "Push trial")
      .on("click", () => this.buildPushCommand(this.modal, this.modalBody))
      .append("i")
      .classed("fa fa-cloud-upload", true)

    // Pull trial
    formdiv.append("a")
      .classed("toollink", true)
      .attr("id", "history-" + this.graphId + "-pull-trial")
      .attr("href", "#")
      .attr("title", "Pull trial")
      .on("click", () => this.buildPullCommand(this.modal, this.modalBody))
      .append("i")
      .classed("fa fa-cloud-download", true)

    // Add remote
    formdiv.append("a")
      .classed("toollink", true)
      .attr("id", "history-" + this.graphId + "-add-remote")
      .attr("href", "#")
      .attr("title", "Add remote")
      .on("click", () => this.buildAddRemote(this.modal, this.modalBody))
      .append("i")
      .classed("fa fa-plus-circle", true)

    // Edit remote
    formdiv.append("a")
      .classed("toollink", true)
      .attr("id", "history-" + this.graphId + "-add-remote")
      .attr("href", "#")
      .attr("title", "Edit remote")
      .on("click", () => this.buildEditRemote(this.modal, this.modalBody))
      .append("i")
      .classed("fa fa-pencil-square", true)

    formdiv.append("div")
    formdiv.append("div")
      .text(this.config.hintMessage)
      .style('font-family', 'sans-serif')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
  }

  load(data: HistoryGraphData): VisibleHistoryNode[] {
    let
      nodes: VisibleHistoryNode[] = [],
      otherNodes: VisibleHistoryNode[] = [],
      edges: VisibleHistoryEdge[] = [],
      spacing = this.config.spacing,
      margin = this.config.margin;
    let spacing2 = 2 * spacing,
      spacing4 = 4 * spacing,
      start = margin,
      max = 0,
      id = 0,
      last = data.nodes.length - 1,
      tid = 0,
      useVersion = false;

    let levels = [];
    for (var i = 0; i <= last; i++) {
      let node: HistoryNodeData = data.nodes[i];
      var previous: any = levels[node.level];
      if (previous == undefined) {
        previous = -1;
      }
      var trials = node.trials;
      if (trials == undefined) {
        trials = [];
      }
      levels[node.level] = Math.max(previous, trials.length);
    }

    let levelsy = [];
    var current = margin;
    for (var i = 0; i <= levels.length; i++) {
      levelsy[i] = current
      current += spacing2 + levels[i] * spacing2;
    }

    for (var i = 0; i <= last; i++) {
      let node: HistoryNodeData = data.nodes[i];
      let x: number = start + spacing4 * id;
      let y: number = levelsy[node.level];
      var new_node: VisibleHistoryNode = {
        id: id,
        display: node.display,
        x: x,
        y: y,
        title: node.id.toString(),
        info: node,
        radius: this.config.radius,
        gradient: false,
        status: node.status
      };

      nodes.push(new_node)
      if (typeof (node.trials) != "undefined") {
        useVersion = true;
        for (var j = 0; j < node.trials.length; j++) {
          let trialNode: HistoryTrialNodeData = node.trials[j] as HistoryTrialNodeData;
          let ny = y + (j + 1) * spacing2 + spacing
          otherNodes.push({
            id: tid,
            display: trialNode.display,
            x: x + this.config.radius / 2,
            y: ny,
            title: trialNode.id.toString(),
            info: trialNode,
            tooltip: trialNode.tooltip,
            radius: this.config.radius / 2,
            gradient: true,
            status: trialNode.status
          });
          tid += 1;
          max = Math.max(max, y);
        }
      } else {
        new_node.tooltip = (node as HistoryTrialNodeData).tooltip;
      }
      max = Math.max(max, y);
      this.maxX = x;
      id += 1;
    }
    max += spacing2;
    this.maxY = max;
    this.maxId = Math.max(tid, id);

    for (var i = 0; i < data.edges.length; i++) {
      let edge: any = { ...data.edges[i] };
      edge.id = edge.source + "-" + edge.target;
      edge.source = nodes[edge.source];
      edge.target = nodes[edge.target];
      if (edge.source != edge.target) {
        edges.push(edge as VisibleHistoryEdge);
      }
    }

    if (useVersion) {
      this.nodes = otherNodes;
      this.versionNodes = nodes;
    } else {
      this.nodes = nodes;
      this.versionNodes = [];
    }
    this.edges = edges;
    this.updateWindow();
    this.restorePosition();
    this.update();
    this.menuOnRightClick();

    return nodes;
  }

  updateWindow(): void {
    let size = this.config.customSize(this);
    this.config.width = size[0];
    this.config.height = size[1];
    this.svg
      .attr("width", size[0])
      .attr("height", size[1]);
  }

  update() {
    var nodes = this.g.selectAll('g.node')
      .data(this.nodes, (d: any) => d.id);

    var edges = this.g.selectAll('g.link')
      .data(this.edges, (d: any) => d.id);

    var version = this.g.selectAll('g.version')
      .data(this.versionNodes, (d: any) => d.id);

    this.updateNodes(nodes);
    this.updateVersionNodes(version);
    this.updateLinks(edges);
  }

  restorePosition(): void {
    let scale = this.config.height / this.maxY;
    if (scale <= 1.0) {
      this.svg.call(this.zoom.transform,
        d3_zoomIdentity
          .translate(
            this.config.width
            - this.maxX * scale
            - this.config.margin, 0)
          .scale(scale)
      )
    } else {
      this.svg.call(this.zoom.transform,
        d3_zoomIdentity
          .scale(1)
          .translate(
            this.config.width
            - this.maxX
            - this.config.margin, 0)
      )
    }
    this.state.justScale = false;
  }

  selectNode(node: VisibleHistoryNode): void {
    this.state.selectedNode = node;
    this.config.customSelectNode(this, node);
    this.svg.selectAll('.node[attr-trial="' + node.title + '"] > rect')
      .attr('stroke', 'rgb(200, 238, 241)')
      .classed('selected', true);
  }

  selectTrial(trialId: string) {
    for (var node of this.nodes) {
      if (node.title == trialId) {
        this.selectNode(node);
        return;
      }
    }
  }

  download(name?: string) {
    var isFileSaverSupported = false;
    try {
      isFileSaverSupported = !!new Blob();
    } catch (e) {
      alert("blob not supported");
    }
    name = (name === undefined) ? "history.svg" : name;
    let gnode: any = this.g.node()
    var bbox = gnode.getBBox();
    var width = this.svg.attr("width"), height = this.svg.attr("height");
    this.g.attr("transform", "translate(" + (-bbox.x + 5) + ", " + (-bbox.y + 5) + ")");
    let svgNode: any = this.svg
      .attr("title", "Trial")
      .attr("version", 1.1)
      .attr("width", bbox.width + 10)
      .attr("height", bbox.height + 10)
      .attr("xmlns", "http://www.w3.org/2000/svg")
      .node();
    var html = svgNode.parentNode.innerHTML;
    html = '<svg xmlns:xlink="http://www.w3.org/1999/xlink" ' + html.slice(4);
    this.svg
      .attr("width", width)
      .attr("height", height);
    this.g.attr("transform", this.transform);
    if (isFileSaverSupported) {
      var blob = new Blob([html], { type: "image/svg+xml" });
      fs.saveAs(blob, name);
    }
  }


  private closeTooltip(): void {
    this.tooltipDiv.transition()
      .duration(500)
      .style("opacity", 0);
    this.tooltipDiv.classed("hidden", true);
  }

  private showTooltip(event: MouseEvent, d: VisibleHistoryNode) {
    if (typeof (d.tooltip) == "undefined") {
      return;
    }
    this.tooltipDiv.classed("hidden", false);
    this.tooltipDiv.transition()
      .duration(200)
      .style("opacity", 0.9);
    this.tooltipDiv.html(d.tooltip)
      .style("left", (event.pageX - 3) + "px")
      .style("top", (event.pageY - 28) + "px");
  }

  private createMarker(name: string, cls: string, fill: string) {
    this.svg.append("svg:defs").selectAll("marker")
      .data([name])
      .enter().append("svg:marker")
      .attr("id", String)
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 6)
      .attr("refY", 0)
      .attr("markerWidth", 3)
      .attr("markerHeight", 3)
      .attr("orient", "auto")
      .append("svg:path")
      .classed(cls, true)
      .attr("fill", fill)
      .attr("d", "M0,-5L10,0L0,5");
  }

  private unselectNode(): void {
    this.g.selectAll('g.node').filter((cd: VisibleHistoryNode) => {
      if (this.state.selectedNode == null) {
        return false;
      }
      return cd.id === this.state.selectedNode.id;
    }).select('rect')
      .classed('selected', false)
      .attr("stroke", "#000");
    this.state.selectedNode = null;
  }

  private nodeMouseDown(event: MouseEvent, d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, d: VisibleHistoryNode): void {
    event.stopPropagation();
    this.state.mouseDownNode = d;
    this.closeTooltip();
  }

  private nodeMouseUp(event: MouseEvent, d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, d: VisibleHistoryNode): void {
    event.stopPropagation();
    if (!this.state.mouseDownNode) {
      return;
    }

    if (this.state.justScale) {
      this.state.justScale = false;
    } else {
      if (event.ctrlKey || event.shiftKey || event.altKey) {
        this.config.customCtrlClick(this, d);
        return;
      }
      if (this.state.selectedNode) {
        this.unselectNode();
      }

      d3node
        .attr('stroke', 'rgb(200, 238, 241)')
        .classed('selected', true);
      this.state.selectedNode = d;
      this.config.customSelectNode(this, d);
    }

    this.state.mouseDownNode = null;
  }

  private svgMouseUp() {
    if (this.state.justScale) {
      this.state.justScale = false;
    }
  }

  private updateVersionNodes(nodes: any) {
    var nodeEnter = nodes.enter().append("g")
      .classed("version", true)
      .attr("attr-trialid", (d: VisibleHistoryNode) => d.title)
      .attr("transform", (d: VisibleHistoryNode) => {
        return "translate(" + 0 + "," + 0 + ")";
      })

    // Circle for new nodes
    nodeEnter.append('rect')
      .attr("transform", (d: VisibleHistoryNode) => {
        return "translate(" + d.x + "," + d.y + ")";
      })
      .attr('width', (d: VisibleHistoryNode) => 2 * d.radius)
      .attr('height', (d: VisibleHistoryNode) => 2 * d.radius)
      .attr('rx', 0)
      .attr('ry', 0)
      //.attr('r', )
      .attr("stroke", "#000")
      .attr("stroke-width", "2.5px")
      .attr("fill", "#F6FBFF")
      .attr("stroke", "#000")
      .attr("stroke-width", "2.5px")

    nodeEnter.append('text')
      .classed('trial-id', true)
      .attr('font-family', 'sans-serif')
      .attr('font-size', this.config.fontSize + 'px')
      .attr('pointer-events', 'none')
      .attr('x', (d: VisibleHistoryNode) => d.radius)
      .attr('y', (d: VisibleHistoryNode) => d.radius + 4)
      .attr('stroke', '#000')
      .attr('text-anchor', 'middle')
      //.attr('font-weight', 'bold')
      .attr("transform", (d: VisibleHistoryNode) => {
        return "translate(" + d.x + "," + d.y + ")";
      }).text((d: VisibleHistoryNode) => d.display);

    nodeEnter.merge(nodes);  // nodeUpdate


    nodes.exit().remove();  // nodeExit
  }

  private updateNodes(nodes: any) {
    let self = this;
    var nodeEnter = nodes.enter().append("g")
      .classed("node", true)
      .attr("attr-trialid", (d: VisibleHistoryNode) => d.title)
      .attr("cursor", "pointer")
      .attr("transform", (d: VisibleHistoryNode) => {
        return "translate(" + 0 + "," + 0 + ")";
      })

    // Circle for new nodes
    nodeEnter.append('rect')
      .attr("transform", (d: VisibleHistoryNode) => {
        return "translate(" + d.x + "," + d.y + ")";
      })
      .attr('cursor', 'pointer')
      .attr('title', (d: VisibleHistoryNode) => d.info.display)
      .attr('width', (d: VisibleHistoryNode) => 2 * d.radius)
      .attr('height', (d: VisibleHistoryNode) => 2 * d.radius)
      .attr('rx', (d: VisibleHistoryNode) => 2 * d.radius)
      .attr('ry', (d: VisibleHistoryNode) => 2 * d.radius)
      //.attr('r', )
      .attr("stroke", "#000")
      .attr("stroke-width", "2.5px")
      .attr("fill", function (d: VisibleHistoryNode) {
        var proportion = Math.round(200 * (1.0 - (parseInt(d.title) / self.maxId)) + 50);
        if (d.status === 'unfinished') {
          return d.gradient ? d3_rgb(255, proportion, proportion, 255).toString() : "rgb(238, 200, 241)";
        }
        if (d.status === 'finished') {
          return d.gradient ? d3_rgb(proportion, proportion, proportion, 255).toString() : "#F6FBFF";
        }
        if (d.status === 'backup') {
          return d.gradient ? d3_rgb(255, 255, proportion, 255).toString() : "rgb(241, 238, 200)";
        }
        return '#666';
      })
      .attr("stroke", function (d: VisibleHistoryNode) {
        return (d3_select(this).classed('selected')) ? 'rgb(200, 238, 241)' : "#000";
      })
      .attr("stroke-width", "2.5px")
      .on('mousedown', function (event: MouseEvent, d: VisibleHistoryNode) {
        self.nodeMouseDown(event, d3_select(this), d);
      }).on('click', function (event: MouseEvent, d: VisibleHistoryNode) {
        self.nodeMouseUp(event, d3_select(this), d);
      }).on('mouseover', function (event: MouseEvent, d: VisibleHistoryNode) {
        if (!self.state.mouseDownNode && self.config.useTooltip) {
          self.closeTooltip();
          self.showTooltip(event, d);
        }
        d3_select(this)
          .attr('stroke', 'rgb(200, 238, 241)')
      }).on('mouseout', function (event: MouseEvent, d: VisibleHistoryNode) {
        d3_select(this)
          .attr("stroke", (d: VisibleHistoryNode) => {
            return (d3_select(this).classed('selected')) ? 'rgb(200, 238, 241)' : "#000";
          });
      })
      .classed("custom-menu", true);

    nodeEnter.append('text')
      .classed('trial-id', true)
      .attr('font-family', 'sans-serif')
      .attr('font-size', this.config.fontSize + 'px')
      .attr('pointer-events', 'none')
      .attr('x', (d: VisibleHistoryNode) => d.radius)
      .attr('y', (d: VisibleHistoryNode) => d.radius + 4)
      .attr('stroke', '#000')
      .attr('text-anchor', 'middle')
      //.attr('font-weight', 'bold')
      .attr("transform", (d: VisibleHistoryNode) => {
        return "translate(" + d.x + "," + d.y + ")";
      }).text((d: VisibleHistoryNode) => d.gradient ? "" : d.display);

    nodeEnter.merge(nodes); // nodeUpdate

    nodes.exit().remove(); // nodeExit
  }

  private updateLinks(link: any) {
    // Enter any new links
    let colors = d3_scaleOrdinal(d3_schemeCategory10);


    var linkEnter = link.enter().insert('path', 'g')
      .classed('link', true)
      .attr('cursor', 'crosshair')
      .attr('fill', 'none')
      .attr('stroke', '#000')
      .attr('stroke-width', '4px');

    linkEnter
      .attr("d", (d: VisibleHistoryEdge) => {
        var deltaX = d.target.x - d.source.x,
          deltaY = d.target.y - d.source.y,
          dist = Math.sqrt(deltaX * deltaX + deltaY * deltaY),
          normX = deltaX / dist,
          normY = deltaY / dist,
          sourcePadding = this.config.radius - 5,
          targetPadding = this.config.radius + (d.right ? 3 : -5),
          sourceX = d.source.x + this.config.radius + (sourcePadding * normX),
          sourceY = d.source.y + this.config.radius + (sourcePadding * normY),
          targetX = d.target.x + this.config.radius - (targetPadding * normX),
          targetY = d.target.y + this.config.radius - (targetPadding * normY);
        var step = 0;
        if (d.level > 0) {
          step += this.config.moveY;
          step += (d.level - 1) * this.config.moveY2;
        }
        return `M ${sourceX}, ${sourceY}
          C ${(sourceX - this.config.moveX / 2)} ${sourceY}
            ${(sourceX - this.config.moveX / 2)} ${(sourceY + 3 * step / 4)}
            ${(sourceX - this.config.moveX)} ${(sourceY + step)}
          L ${(sourceX - this.config.moveX)} ${(sourceY + step)}
            ${(targetX + this.config.moveX)} ${(sourceY + step)}
          C ${(targetX + this.config.moveX / 2)} ${(sourceY + 3 * step / 4)}
            ${(targetX + this.config.moveX / 2)} ${sourceY}
            ${targetX}, ${targetY}`;
      })
      .attr('marker-end', (d: VisibleHistoryEdge) => {
        return d.right ? 'url(#end-arrow)' : ''
      })
      .attr('stroke', (d: VisibleHistoryEdge) => {
        return d3_rgb(colors(d.level.toString())).darker().toString();
      });
    // Update
    linkEnter.merge(link); // linkUpdate

    // Remove any exiting links
    link.exit().remove(); // linkExit
  }

  private zoomFunction(event: D3ZoomEvent<SVGSVGElement, any>) {
    this.state.justScale = true;
    this.closeTooltip();
    this.transform = event.transform;
    this.g.attr("transform", event.transform as any);
  }

  private _graphId(): string {
    return "history-graph-" + this.graphId;
  }

  private menuOnRightClick() {
    let rightClickMenu = document.getElementById("context-menu");

    // Set up an event handler for the documnt right click
    document.addEventListener("contextmenu", function (event) {
      //open right click menu
      let target = event.target as Element;
      if (target && target.classList.contains("custom-menu")) {
        event.preventDefault();
        if (rightClickMenu) {
          rightClickMenu.setAttribute("selected-trial", target.parentElement?.getAttribute("attr-trialid")!);
          rightClickMenu.setAttribute("selected-trial-simplified", target.getAttribute("title")!);
          rightClickMenu.style.top = (event.pageY - 10).toString();
          rightClickMenu.style.left = (event.pageX - 90).toString();
          rightClickMenu.style.display = "block";
          rightClickMenu.classList.add("show");
        }


      }

    });

    // close the menu
    document.addEventListener("click", function (event) {
      if (rightClickMenu) {
        rightClickMenu.style.display = "none";
        rightClickMenu.classList.remove("show");
      }
    });
  }
}

function buildExportPrologModal(modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>, exportUrl: string, config: HistoryConfig, parent: Element, exportWindowId: string, trialId: string | null) {
  let submitButton;
  let form: d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>;
  document.getElementById("exampleModalTitle")!.textContent = "Prolog";

  showModal(modal);

  if (modalBody) {
    form = modalBody.append("form").attr("onsubmit", "return false;");

    createFormCheckInput(form, "exportProvRules", "Also exports inference rules");
    createFormCheckInput(form, "exportProvHideTimestamps", "Hide timestamps");

    submitButton = form.append("button").classed("btn btn-primary mb-2", true).text("Generate prolog");

  }

  submitButton?.on("click", () => {
    let inferenceRules = (<HTMLInputElement>document.getElementById("exportProvRules")).checked;
    let hideTimestamps = (<HTMLInputElement>document.getElementById("exportProvHideTimestamps")).checked;

    exportUrl += "/" + inferenceRules + "/" + hideTimestamps;

    buildExportPrologTab(exportUrl, config, parent, exportWindowId, trialId);
    cleanModalBodyAndClose(modal, modalBody);
  });
}

function buildExportPrologTab(exportUrl: string, config: HistoryConfig, parent: Element, exportWindowId: string, trialId: string | null) {

  if (document.getElementById(exportWindowId)) {
    window.alert("Close trial " + trialId + " prolog tab before generating a new prolog");
    return;
  }



  fetch(exportUrl, {
    method: 'GET', // *GET, POST, PUT, DELETE, etc.
    headers: {
      'Content-Type': 'application/json'
    },
  }).then((response: any) => {
    response.json().then((json: any) => {

      if (response.status == 200) {


        config.customWindowTabCommand(parent.getAttribute("selected-trial-simplified")!, exportWindowId, "Prolog");
        let exportWindow = d3_select(document.getElementById(exportWindowId));

        let form: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any> = (exportWindow.append("form").attr("onsubmit", "return false;") as d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>)
          .append("div").classed("form-row", true);
        createFormTextInput(form, "exportPrologProgram" + trialId, "Prolog").classed("col-7", true);
        createFormTextInput(form, "exportPrologQuery" + trialId, "Query").classed("col", true);

        let submitButton = form.append("div").classed("col-auto", true).style("padding-top", "5vh")
          .append("button").classed("btn btn-primary mb-2", true).text("Execute Query");


        (<HTMLInputElement>document.getElementById("exportPrologProgram" + trialId))!.value = json.export;

        let prologSession = pl.create(1000);

        let answerCallback = (answer: any, answerString: string) => {
          if (answer == false) {

            let answerCardTextId = "Answers prolog card text " + trialId;
            let answerCardText = document.getElementById(answerCardTextId) ? d3_select(document.getElementById(answerCardTextId)) : null;
            if (answerCardText == null) {
              let answerWindow = exportWindow.append("div");
              answerWindow.classed("card", true).append("div").classed("card-header", true).text("Answers");
              answerCardText = answerWindow.append("div").classed("card-body", true)
                .append("p").classed("card-text", true).attr("id", answerCardTextId)
                .style("overflow-y", "auto").style("max-height", "35vh");
            }

            answerCardText!.html(answerString);
            return;
          }
          answerString += prologSession.format_answer(answer).toString() + "<br>";

          prologSession.answer((answer: any) => answerCallback(answer, answerString));
        };

        submitButton.on("click", () => {
          let prologProgram = getTextInputFormByID("exportPrologProgram" + trialId);
          let userQuery = getTextInputFormByID("exportPrologQuery" + trialId);
          if (prologProgram && userQuery) {

            prologSession.consult(prologProgram, {
              success: () => {
                console.log("Prolog consult success");
                prologSession.query(userQuery, {
                  success: () => {
                    prologSession.answer((answer: any) => answerCallback(answer, ""));
                  },
                  error: () => {
                    console.log("Erro query");
                  }
                });
              },
              error: () => {
                console.log("Prolog consult error");
              }
            });
          }


        });

      } else {
        console.log("Export error");
      }

    });
  });
}

function scrollableModal(modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>) {
  let modalDialog = (document.getElementsByClassName("modal-dialog") as HTMLCollectionOf<HTMLElement>)[0];
  modalDialog.style.overflowY = "initial";
  modalDialog.style.maxHeight = "85%";
  modalBody.style("overflow-y", "auto").style("height", "80vh");
}

function getDataflow(response: any, config: HistoryConfig, parent: Element, dataflowWindowId: string, dataflowUrl: string) {
  response.json().then((json: any) => {
    if (response.status == 200) {

      config.customWindowTabCommand(parent.getAttribute("selected-trial-simplified")!, dataflowWindowId, "Dataflow");
      console.log(json.dataflow);

      instance().then(viz => {
        const dataflowWindow = document.getElementById(dataflowWindowId);

        // Download SVG Button
        downloadDataflow(dataflowWindow, dataflowWindowId);
        excludePriorProvenanceHint(dataflowWindow);

        let selectedNode: Element | undefined;

        dataflowWindow!.style.overflowY = dataflowWindow!.style.overflowX = "auto";
        let svgElement = viz.renderSVGElement(json.dataflow);
        for (let nodeIndex = 0; nodeIndex < svgElement.children[0].children.length; nodeIndex++) {

          let presentNode : Element | undefined = svgElement.children[0].children[nodeIndex];
          if (presentNode.getAttribute("class") == "node" && presentNode.children[1].tagName.toLowerCase() == "polygon") {
            d3_select(presentNode).on("click", (event: MouseEvent) => {

              if (selectedNode) { selectedNode.children[1].setAttribute("stroke", "black"); }

              if (selectedNode && (event.ctrlKey || event.shiftKey)) {
                deletePriorNodes(selectedNode, presentNode!, json.dataflow, viz, dataflowWindow, dataflowUrl);
                selectedNode = undefined;
                presentNode = undefined;
              } else {
                selectedNode = svgElement.children[0].children[nodeIndex];
                selectedNode.children[1].setAttribute("stroke", "red");
              }
            });
          }
        }
        dataflowWindow!.appendChild(svgElement);
      });


    } else {
      console.log("Dataflow error");
    }

  });

}

function excludePriorProvenanceHint(dataflowWindow: HTMLElement | null) {
  d3_select(dataflowWindow).append("div").append("div")
    .text("Click on a function call, then (Ctrl or Shift)+click on another one to exclude prior provenience")
    .style('font-family', 'sans-serif')
    .style('font-size', '12px')
    .style('pointer-events', 'none');
}

function deletePriorNodes(selectedNode: Element, presentNode: Element, dataflow: string, viz: any, dataflowWindow: HTMLElement | null, dataflowUrl: string) {

  dataflowUrl = dataflowUrl.substring(0, dataflowUrl.lastIndexOf("/"));
  dataflowUrl = dataflowUrl.substring(0, dataflowUrl.lastIndexOf("/")) + "/true/";

  let selectedNodeEvaluationTitle = selectedNode.children[0].innerHTML;
  let presentNodeOrderEvaluationTitle = presentNode.children[0].innerHTML;

  let firstEvaluationOrder = Number(selectedNodeEvaluationTitle.replace("e_", ""));
  let lastEvaluationOrder = Number(presentNodeOrderEvaluationTitle.replace("e_", ""));
  if (firstEvaluationOrder > lastEvaluationOrder) {
    lastEvaluationOrder = firstEvaluationOrder;
    firstEvaluationOrder = Number(presentNodeOrderEvaluationTitle.replace("e_", ""));
  }

  let dataflowUrlLastEvaluation = dataflowUrl + lastEvaluationOrder;
  let dataflowUrlFirstEvaluation = dataflowUrl + firstEvaluationOrder;

  dataflowWindow!.textContent = "Loading...";

  fetch(dataflowUrlLastEvaluation, {
    method: 'GET', // *GET, POST, PUT, DELETE, etc.
    headers: {
      'Content-Type': 'application/json'
    },
  }).then((responseLastEvaluation: any) => {
    responseLastEvaluation.json().then((jsonLastEvaluation: any) => {
      let dataflowLastEvaluation = jsonLastEvaluation.dataflow;
      fetch(dataflowUrlFirstEvaluation, {
        method: 'GET', // *GET, POST, PUT, DELETE, etc.
        headers: {
          'Content-Type': 'application/json'
        },
      }).then((responseFirstEvaluation: any) => {
        responseFirstEvaluation.json().then((jsonFirstEvaluation: any) => {
          let dataflowFirstEvaluation = jsonFirstEvaluation.dataflow;

          let linesDataflowLastEvaluation = dataflowLastEvaluation.split("\n");
          let linesDataflowFirstEvaluation = dataflowFirstEvaluation.split("\n");
          let newDataflow = linesDataflowLastEvaluation.slice(0);

          removesLinesInDataflowFirstEvaluationFromDataflowLastEvaluation(linesDataflowFirstEvaluation, newDataflow, firstEvaluationOrder);

          let dataflowIsAligned = addsDeletedNodeSettingsAndChecksIfDataflowIsAligned(newDataflow, firstEvaluationOrder, linesDataflowLastEvaluation);

          removesDeletedEvaluationsFromAligment(dataflowIsAligned, newDataflow);

          console.log("------");
          console.log(newDataflow.join("\n"));
          console.log("------");

          dataflowWindow!.textContent = "";

          dataflowWindow!.appendChild(viz.renderSVGElement(newDataflow.join("\n")));

        });
      });
    });
  });
  /* 
    let lines = dataflow.split("\n");
    let newLines = lines.slice(0, 3);
    for (let i = 4; i < lines.length; i++) {
  
      if (sameEvaluationOrEvaluationLatterEvalatuion(firstEvaluationOrder, lastEvaluationOrder, lines[i]) || (i >= lines.length - 2)) {
        if (lines[i].includes("->")) {
          let words = lines[i].split(" ");
          let evaluation1 = words[4];
          let evaluation2 = words[6];
          let priorEvaluationTitle = Number(evaluation1.replace("e_", "").replace("a_", "")) > Number(evaluation2.replace("e_", "").replace("a_", "")) ? evaluation2 : evaluation1;
  
          if (Number(priorEvaluationTitle.replace("e_", "").replace("a_", "")) < firstEvaluationOrder) {
            let evaluationSettingsDataflowLine = lines.find((string) => string.includes(priorEvaluationTitle + " [label="));
            newLines.splice(3, 0, evaluationSettingsDataflowLine!);
          }
        }
        newLines.push(lines[i])
      };
    }
  
    let newDataflowString = newLines.join("\n");
  
    console.log(newDataflowString);
  
    dataflowWindow!.textContent = "";
  
    dataflowWindow!.appendChild(viz.renderSVGElement(newDataflowString)); */

}

function removesDeletedEvaluationsFromAligment(dataflowIsAligned: boolean, newDataflow: any) {
  if (dataflowIsAligned) {

    let evaluations : any = [];
    
    for (let lineIndex = 3; lineIndex < newDataflow.length; lineIndex++) {
      let line = newDataflow[lineIndex];
      if (line.includes("label")) evaluations.push(line.replace(/\[[^\]]*?\];/, "").split(" ")[4].trim());

      else if (line.includes("{rank=")) {
        let alignedEvaluations = line.split(" ");

        for(let alignedEvalIndex = 5; alignedEvalIndex < alignedEvaluations.length; alignedEvalIndex++){
          let alignedEval = alignedEvaluations[alignedEvalIndex].replace("}\r", "").trim();

          if(!evaluations.includes(alignedEval)) newDataflow[lineIndex] = newDataflow[lineIndex].replace(alignedEval, "");
        }
      }

      else if (line.includes("->")) break;
    }
  }
}

function removesLinesInDataflowFirstEvaluationFromDataflowLastEvaluation(linesDataflowFirstEvaluation: any, newDataflow: any, firstEvaluationOrder: number) {
  for (let i = 3; i < linesDataflowFirstEvaluation.length - 2; i++) {
    let indexOfDataflowLineToRemove;

    if (linesDataflowFirstEvaluation[i].includes("->") && linesDataflowFirstEvaluation[i].includes("[")) {

      let lineToRemove = linesDataflowFirstEvaluation[i].replace(/\[[^\]]*\]/, "");

      indexOfDataflowLineToRemove = newDataflow.findIndex((dataflowLine: string) => {
        return dataflowLine.replace(/\[[^\]]*\]/, "") == lineToRemove;
      });


    } else indexOfDataflowLineToRemove = newDataflow.indexOf(linesDataflowFirstEvaluation[i]);

    if (indexOfDataflowLineToRemove > -1 && (!linesDataflowFirstEvaluation[i].includes("_" + firstEvaluationOrder + " ["))) newDataflow.splice(indexOfDataflowLineToRemove, 1);

  }
}

function addsDeletedNodeSettingsAndChecksIfDataflowIsAligned(newDataflow: any, firstEvaluationOrder: number, linesDataflowLastEvaluation: any) {
  let tempArray: any[] = [];
  let isAligned = false;

  newDataflow.forEach((line: string) => {
    if(!isAligned && line.includes("{rank")) isAligned = true;


    if (line.includes("->")) {
      let evaluationWithoutSettings = line.split(" ")[6];
      if (Number(evaluationWithoutSettings.replace("e_", "").replace("a_", "")) < firstEvaluationOrder) { // TODO revise if firstEvaluationOrder is right
        tempArray.push(linesDataflowLastEvaluation.find((string: string) => string.includes(evaluationWithoutSettings + " [")));
      }
    }
  });

  tempArray.forEach(item => newDataflow.splice(3, 0, item));

  return isAligned
}

/* function sameEvaluationOrEvaluationLatterEvalatuion(firstEvaluationOrder: number, lastEvaluationOrder: number, dataflowStringLine: string): boolean {
  let words = dataflowStringLine.split(" ");
  for (let wordIndex = 0; wordIndex < words.length; wordIndex++) {
    let word = words[wordIndex];
    let evaluationOrder = Number(word.replace("e_", ""));

    if (word.includes("e_") && (evaluationOrder > lastEvaluationOrder)) return false;
    if (word.includes("e_") && (evaluationOrder >= firstEvaluationOrder)) return true;
  }
  return false
} */

function buildDataflowModal(modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>,
  parent: Element, config: HistoryConfig, trialId: string) {

  let submitButton;
  let evaluationList;
  let form: d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>;
  document.getElementById("exampleModalTitle")!.textContent = "Dataflow";

  fetch("/dataflow/evaluations/" + trialId, {
    method: 'GET', // *GET, POST, PUT, DELETE, etc.
    headers: {
      'Content-Type': 'application/json'
    },
  }).then((response) => {
    response.json().then((json) => {
      evaluationList = json.evaluations;
      let selectedEvaluation: number | undefined;
      let dataflowTextInputEvaluation: HTMLSelectElement;

      showModal(modal);

      if (modalBody) {

        scrollableModal(modalBody);

        form = modalBody.append("form").attr("onsubmit", "return false;");
        createFormCheckInput(form, "dataFlowShowType", "Show type nodes");
        createFormCheckInput(form, "dataFlowHideTimestamps", "Hide timestamps");
        createFormCheckInput(form, "dataFlowHideInternals", "Show variables and functions which name starts with a leading underscore");

        createFormSelectInput(form, "dataflowShowAccesses", "Show file accesses", 0, 4, 1, "dataflowShowAccessesHelp",
          "(default: Shows each file once (hide external accesses))",
          ["Hides file accesses", "Shows each file once (hide external accesses)", "Shows each file once (show external accesses)",
            "Shows all accesses (except external accesses)", "Shows all accesses (including external accesses)"]);

        createFormSelectInput(form, "dataflowEvaluation", "Combine evaluation nodes", 0, 2, 1, "dataflowEvaluationHelp",
          "(default: Combines evaluation nodes by assignment)",
          ["Not combine evaluation nodes", "Combines evaluation nodes by assignment", "Combines evaluation nodes by value"]);

        createFormSelectInput(form, "dataflowGroup", "Align evalutions in the same column", 0, 2, 0,
          "dataflowGroupHelp",
          "(default: Does no align). With this option, all variables in a loop appear grouped, reducing the width of the graph. It may affect the graph legibility. The alignment is independent for each activation.",
          ["Does no align", "Aligns by line", "Aligns by line and column"]);

        createFormSelectInput(form, "dataflowMode", "Graph mode", 0, 3, 3, "dataflowModeHelp",
          "(default: prospective). 'simulation' presents a dataflow graph with all relevant evaluations. 'activation' presents only activations. 'dependency' presents a graph with a single cluster, with all evaluations and activations. 'prospective' presents only parameters, calls, and assignments to calls.",
          ["simulation", "activation", "dependency", "prospective"]);

        createFormNumberInput(form, "dataflowDepth", "Visualization depth", 0, 0, "dataflowDepthHelp", "(default: 0) 0 represents infinity");
        createFormNumberInput(form, "dataflowValueLength", "Maximum length of values", 0, 0, "dataflowValueLengthHelp",
          "(default: 0). 0 indicates that values should be hidden.The values appear on the second line of node lables. E.g. if it is set to '10', it will show 'data.dat',  but it will transform 'data2.dat' in to 'da...dat' to respect the length restriction (note that '' is part of the value). Minimum displayable value: 5. Suggested: 55.");
        createFormNumberInput(form, "dataflowName", "Maximum length of names", 0, 55, "dataflowNameHelp",
          "(default: 55). 0 indicates that values should be hidden. Minimum displayable value: 5. Suggested: 55.");

        let dataflowEvaluationInput = createFormTextInput(form, "dataflowTextInputEvaluation", "Evaluation was derived from: ", "dataflowSelectEvaluationHelp", "Filter that shows only one evaluation and the ones that derived it");

        form.append("div").attr("id", "autocompleteSuggestionsResults");

        dataflowTextInputEvaluation = (<HTMLSelectElement>document.getElementById("dataflowTextInputEvaluation"))


        dataflowEvaluationInput.on("keyup", () => {

          let input = dataflowTextInputEvaluation.value;
          let autocompleteSuggestionsResults = (<HTMLSelectElement>document.getElementById("autocompleteSuggestionsResults"));
          let evaluationInputHint = (<HTMLSelectElement>document.getElementById("dataflowSelectEvaluationHelp"));

          autocompleteSuggestionsResults.innerHTML = "";

          let suggestions: any[];

          if (input == "") {
            autocompleteSuggestionsResults.setAttribute("style", "");
            evaluationInputHint.style.opacity = "1";
            suggestions = [];
            selectedEvaluation = undefined;
          }
          else {
            autocompleteSuggestionsResults.style.border = "1px solid #ccc";
            autocompleteSuggestionsResults.style.padding = "3px";
            autocompleteSuggestionsResults.style.marginTop = "-3rem";
            evaluationInputHint.style.opacity = "0";

            suggestions = evaluationList!.filter((evaluation: any) => {
              if (evaluation.name.includes(input)) return evaluation;
            });

            autocompleteSuggestionsResults.innerHTML = "<ul id=\"dataflowEvaluationSuggestionsBoxId\" style=\"list-style-type: none; padding: 0; margin: 0;\"></ul>";


            for (let i = 0; i < suggestions.length; i++) {
              let evaluationSuggestionId = suggestions[i].evaluation_id + " " + "evaluationSuggestionItem"

              d3_select(document.getElementById("dataflowEvaluationSuggestionsBoxId")).append("li").attr("id", evaluationSuggestionId)
                .style("padding", "5px 0")
                .style("z-index", 1)
                .text("Evaluation: " + suggestions[i].name + "         " + "Code_line: " + suggestions[i].first_char_line)
                .on("click", () => {
                  dataflowTextInputEvaluation.value = suggestions[i].name;
                  input = suggestions[i].name;
                  selectedEvaluation = suggestions[i].evaluation_id;
                })
                .on("mouseover", () => { d3_select(document.getElementById(evaluationSuggestionId)).style("background-color", "#eee") })
                .on("mouseout", () => { d3_select(document.getElementById(evaluationSuggestionId)).style("background-color", "") });
            }



          }

        });

        submitButton = form.append("button").classed("btn btn-primary mb-2", true).text("Generate dataflow");

      }

      submitButton!.on("click", function () {
        let dataFlowShowType = (<HTMLInputElement>document.getElementById("dataFlowShowType")).checked;
        let dataFlowHideTimestamps = (<HTMLSelectElement>document.getElementById("dataflowMode")).checked;
        let dataFlowHideInternals = (<HTMLInputElement>document.getElementById("dataFlowHideInternals")).checked;

        let dataflowFileAccesses = (<HTMLSelectElement>document.getElementById("dataflowShowAccesses")).selectedOptions[0].index;
        let dataflowEvaluation = (<HTMLSelectElement>document.getElementById("dataflowEvaluation")).selectedOptions[0].index;
        let dataflowGroup = (<HTMLSelectElement>document.getElementById("dataflowGroup")).selectedOptions[0].index;
        let dataflowMode = (<HTMLSelectElement>document.getElementById("dataflowMode")).selectedOptions[0].value;

        let dataflowDepth = (<HTMLInputElement>document.getElementById("dataflowDepth")).value;
        let dataflowValueLength = (<HTMLInputElement>document.getElementById("dataflowValueLength")).value;
        let dataflowName = (<HTMLInputElement>document.getElementById("dataflowName")).value;

        let trialId = parent.getAttribute("selected-trial");

        let dataflowUrl = "/commands/dataflow/" + trialId + "/" + dataFlowShowType + "/" + dataFlowHideTimestamps + "/" +
          dataFlowHideInternals + "/" + dataflowFileAccesses + "/" + dataflowEvaluation + "/" + dataflowGroup + "/" +
          dataflowDepth + "/" + dataflowValueLength + "/" + dataflowName + "/" + dataflowMode;
        dataflowUrl += selectedEvaluation ? "/true/" + selectedEvaluation : "/false/0";

        let dataflowWindowId = "Dataflow window " + trialId;

        if (document.getElementById(dataflowWindowId)) {
          window.alert("Close trial " + trialId + " dataflow tab before generating a new dataflow");
          return;
        }

        fetch(dataflowUrl, {
          method: 'GET', // *GET, POST, PUT, DELETE, etc.
          headers: {
            'Content-Type': 'application/json'
          },
        }).then((response: any) => {
          console.log(dataflowMode);
          cleanModalBodyAndClose(modal, modalBody);
          getDataflow(response, config, parent, dataflowWindowId, dataflowUrl);
        });



      });

    });
  });


}

function downloadDataflow(dataflowWindow: HTMLElement | null, dataflowWindowId: string) {
  d3_select(dataflowWindow).append("div").append("a")
    .classed("toollink", true)
    .attr("id", dataflowWindowId + "-download")
    .attr("href", "#")
    .style("color", "black")
    .attr("title", "Download dataflow SVG")
    .on("click", () => {
      fs.saveAs(new Blob([dataflowWindow!.children[1].outerHTML], { type: "image/svg+xml" }), "dataflow.svg");
    })
    .append("i")
    .classed("fa fa-download", true);
}

function getRestoreOrCollabCommand(serverUrl: string, form: d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>,
  modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>) {
  fetch(serverUrl, {
    method: 'GET', // *GET, POST, PUT, DELETE, etc.
    headers: {
      'Content-Type': 'application/json'
    },
  }).then((response) => {

    response.json().then((json) => {
      form.remove();
      if (response.status == 200 && (!json.terminal_text.includes("not") || (serverUrl.includes("edit")))) {
        addAlert(modalBody, "alert-success", "Success!", json.terminal_text);
      } else {
        addAlert(modalBody, "alert-danger", "Error!", json.terminal_text);
      }

    });
  });
}

function changeTitle(parent: Element, commandTitle: string) {
  let trialIdTitle = parent.getAttribute("selected-trial-simplified");
  document.getElementById("exampleModalTitle")!.textContent = commandTitle + trialIdTitle;
}

function cleanModalBodyAndClose(modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
  modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>) {
  document.getElementsByClassName("modal-body")[0].textContent = "";
  modalBody.style("height", null);
  hideModal(modal);
}

function addAlert(div: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, alertType: string, title: string, text: string) {
  let feedbackAlert = div.append("div").classed("alert " + alertType, true).attr("role", "alert");
  feedbackAlert.append("h4").text(title).append("button").classed("close", true).attr("type", "button").text("x").on("click", () => {
    feedbackAlert.remove();
  });
  feedbackAlert.append("p").text(text);
}

function createFormCheckInput(form: d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>, checkInputId: string, text: string) {
  let checkDiv = form.append("div").classed("form-check", true);
  checkDiv.append("input").classed("form-check-input", true).attr("value", "").attr("id", checkInputId)
    .attr("type", "checkbox");
  checkDiv.append("label").classed("form-check-label", true).attr("for", checkInputId)
    .text(text);
}

function createFormTextInput(form: d3_Selection<HTMLFormElement | HTMLDivElement, {}, HTMLElement | null, any>, textInputId: string, text: string, helpId?: string, helpText?: string) {
  let textDiv = form.append("div").classed("form-group", true);
  textDiv.append("label").attr("for", textInputId).text(text);
  let textInput = textDiv.append("textarea").classed("form-control", true).attr("id", textInputId);
  if (helpId && helpText) {
    textInput.attr("aria-describedby", helpId);
    textDiv.append("small").classed("form-text text-muted", true).attr("id", helpId).text(helpText);
  }

  return textDiv;
}

function createFormSelectInput(form: d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>,
  selectId: string, selectText: string, minOptionNumber: number, maxOptionNumber: number, defaultOption?: number,
  helpId?: string, helpText?: string, optionsLabels?: Array<string>) {
  let selectDiv = form.append("div").classed("form-group", true);
  let selectInput = selectDiv.append("label").attr("for", selectId).text(selectText)
    .append("select").classed("form-control", true).attr("id", selectId);

  if (helpId && helpText) {
    selectInput.attr("aria-describedby", helpId);
    selectDiv.append("small").classed("form-text text-muted", true).attr("id", helpId).text(helpText);
  }

  for (var optionNumber = minOptionNumber; optionNumber <= maxOptionNumber; optionNumber++) {
    let inputLabel = optionsLabels ? optionsLabels[optionNumber] : optionNumber;
    let input = selectInput.append("option").text(inputLabel);
    if (defaultOption && optionNumber == defaultOption) input.attr("selected", "selected");
  }
}

function createFormNumberInput(form: d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>, id: string, text: string, minValue: number, defaultValue: number,
  helpId?: string, helpText?: string) {
  let numberDiv = form.append("div").classed("form-group", true);
  numberDiv.append("label").classed("form-check-label", true).attr("for", id)
    .text(text);

  numberDiv.append("input").attr("type", "number").attr("id", id).attr("min", minValue).attr("value", defaultValue)
    .attr("oninput", "validity.valid||(value='');").attr("aria-describedby", "dataflowDepthHelp");

  if (helpId && helpText) {
    numberDiv.attr("aria-describedby", helpId);
    numberDiv.append("small").classed("form-text text-muted", true).attr("id", helpId).text(helpText);
  }

}

function getTextInputFormByID(id: string, replace?: boolean) {
  let formTextInput: string | boolean = (<HTMLInputElement>document.getElementById(id)).value
  if (replace) formTextInput.replace("/", "%2F").replace("\\", "%5C");
  if (!formTextInput) formTextInput = false;
  return formTextInput;
}

function hideModal(modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>) {
  if (modal) modal.style("display", "none").style("padding-right", "").classed("show", false).attr("aria-hidden", "true");
}

function showModal(modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>) {
  if (modal) modal.style("display", "block").style("padding-right", "17px").classed("show", true).attr("aria-hidden", "false");
}

