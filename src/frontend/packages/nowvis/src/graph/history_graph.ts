import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from "d3-selection";

import { DockPanel, Widget } from "@lumino/widgets";

import {
  HistoryGraph,
  VisibleHistoryNode,
  HistoryGraphData,
  HistoryConfig,
} from "@noworkflow/history";

import { json, makeid } from "@noworkflow/utils";

import { TrialGraphWidget } from "./trial_graph";
import { DiffGraphWidget } from "./diff_graph";
import { ProspectiveGraphWidget } from "./prospective_graph";
import { NowVisPanel } from "../nowpanel";
import { TrialInfoWidget } from "../info/trial_info";
import { DiffInfoWidget } from "../info/diff_info";
import { ConfigWidget } from "../config_widget";
import { AnnontationWidget } from "../annotation_widget";

import { functionDiffWindow } from "./function_diff";

import * as fs from "file-saver";
import { instance } from "@viz-js/viz";
declare var require: any;
const pl = require("tau-prolog");
const svgPanZoom = require("svg-pan-zoom");
("svg-pan-zoom");

export class HistoryWidget extends Widget {
  name: string;
  expId: string;
  cls: string;
  graph: HistoryGraph;
  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  config: ConfigWidget;
  annontationWidget: AnnontationWidget;
  rightClickMenu: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>;
  functionDiffWindow = functionDiffWindow;

  static url(script = "*", execution = "*", summarize = false) {
    return (
      "trials.json" +
      "?script=" +
      encodeURIComponent(script) +
      "&execution=" +
      encodeURIComponent(execution) +
      "&summarize=" +
      (summarize ? "1" : "0")
    );
  }

  static createNode(): HTMLElement {
    let node = document.createElement("div");
    let content = document.createElement("div");
    node.appendChild(content);
    let d3node = d3_select(content);

    let d3content = d3node.append("div").classed("history-content", true);

    let filterDiv = d3content
      .append("div")
      //let filterDiv = form.insert("div", ":first-child")
      .classed("filter", true)
      .classed("hide-toolbar", true);

    let filterInternal = filterDiv.append("div").classed("internal", true);
    let scriptOptions = filterInternal
      .append("select")
      .attr("name", "script")
      .classed("select-style script-options", true);

    scriptOptions.append("option").attr("value", "*").text("All Scripts");

    let executionOptions = filterInternal
      .append("select")
      .attr("name", "execution")
      .classed("select-style exec-selection", true);

    executionOptions.append("option").attr("value", "*").text("All Statuses");
    executionOptions
      .append("option")
      .attr("value", "finished")
      .text("Finished Trials");
    executionOptions
      .append("option")
      .attr("value", "unfinished")
      .text("Unfinished Trials");
    executionOptions
      .append("option")
      .attr("value", "backup")
      .text("Backup Trials");

    let summarize = filterInternal.append("div").classed("graph-attr", true);

    summarize
      .append("input")
      .attr("type", "checkbox")
      .attr("name", "summarize")
      .attr("value", "")
      .attr("checked", false)
      .classed("summarize", true)
      .attr("id", "history-summarize");

    summarize
      .append("label")
      .attr("for", "history-summarize")
      .attr("title", "Summarize History")
      .text("Summarize");

    let filterReload = filterInternal
      .append("a")
      .attr("href", "#")
      .classed("link-button reload-button", true);

    filterReload.append("i").classed("fa fa-refresh", true);

    filterReload.append("span").text("Reload");

    d3content.append("div").classed("sub-content", true);

    return node;
  }

  constructor(
    config: ConfigWidget,
    name: string,
    cls: string,
    expId: string,
    annontationWidget: AnnontationWidget,
  ) {
    super({ node: HistoryWidget.createNode() });
    this.expId = expId;
    this.config = config;
    this.annontationWidget = annontationWidget;
    this.d3node = d3_select(this.node);
    this.d3node.select(".reload-button").on("click", () => {
      this.load(
        this.d3node.select(".script-options").property("value"),
        this.d3node.select(".exec-selection").property("value"),
        this.d3node.select(".summarize").property("checked"),
      );
    });
    this.rightClickMenu = this.d3node
      .append("div")
      .classed("dropdown-menu dropdown-menu-sm", true)
      .attr("id", "context-menu")
      .attr("selected-trial", "")
      .style("display", "block");
    this.buildModal(this.node);
    this.buildRightClickMenu();

    //this.setFlag(Widget.Flag.DisallowLayout);
    this.addClass("content");
    this.addClass("trial-widget");
    this.title.label = name;
    this.title.closable = false;
    this.title.caption = `${name} Graph`;
    this.name = name;
    this.cls = cls;
  }

  setGraph(data: HistoryGraphData, config: any = {}) {
    let sub = this.node.getElementsByClassName("sub-content")[0];
    sub.innerHTML = "";
    this.graph = new HistoryGraph(this.cls, sub, config);
    this.graph.load(data);
  }

  load(script = "*", execution = "*", summarize = false) {
    let sub = this.node.getElementsByClassName("sub-content")[0];

    json(
      "History",
      sub,
      HistoryWidget.url(script, execution, summarize),
      (data: HistoryGraphData) => {
        this.setGraph(data, {
          width: this.node.getBoundingClientRect().width - 24,
          height: this.node.getBoundingClientRect().height - 24,
          customCtrlClick: (g: HistoryGraph, d: VisibleHistoryNode) => {
            var redTrial = g.state.selectedNode;
            if (redTrial == null) {
              return true;
            }
            var greenTrial = d;
            let diffGraphWidget = new DiffGraphWidget(
              "Diff " + redTrial.display + "-" + greenTrial.display,
              "diff-" + redTrial.title + "-" + greenTrial.title + makeid(),
              redTrial.title,
              greenTrial.title,
              this.functionDiffWindow,
              this.parent as NowVisPanel,
            );
            diffGraphWidget.d3node
              .append("span")
              .text(
                "Ctrl+(left click) on a function overlap to see the functions' diff",
              )
              .style("font-family", "sans-serif")
              .style("font-size", "12px")
              .style("pointer-events", "none")
              .lower();
            let parentDock: NowVisPanel = this.parent as NowVisPanel;

            if (this.config.showInfo()) {
              let diffInfoWidget = new DiffInfoWidget(
                redTrial.display,
                greenTrial.display,
                redTrial.title,
                greenTrial.title,
              );
              parentDock.addInfoWidget(diffInfoWidget);
              parentDock.activateWidget(diffInfoWidget);
            }

            if (this.config.showTrial()) {
              parentDock.addGraphWidget(diffGraphWidget);
              parentDock.activateWidget(diffGraphWidget);
              diffGraphWidget.load(
                this.config.graphType(),
                this.config.useCache(),
              );
            }
            return true;
          },
          customWindowTabCommand: (
            trialIdSimplified: string,
            windowId: string,
            command: string,
          ) => {
            let trialExportWidget = new Widget();
            trialExportWidget.title.label =
              command + " trial " + trialIdSimplified;
            trialExportWidget.title.closable = true;
            trialExportWidget.id = windowId;
            let parentDock: NowVisPanel = this.parent as NowVisPanel;
            parentDock.addGraphWidget(trialExportWidget);
            parentDock.activateWidget(trialExportWidget);
            return true;
          },
          customSelectNode: (g: HistoryGraph, d: VisibleHistoryNode) => {
            let trialGraphWidget = new TrialGraphWidget(
              "Trial " + d.display,
              "trial-" + d.title + makeid(),
              d.title,
              d.title,
            );
            let parentDock: NowVisPanel = this.parent as NowVisPanel;

            if (this.config.showInfo()) {
              let trialInfoWidget = new TrialInfoWidget(
                d,
                this.annontationWidget,
              );
              parentDock.addInfoWidget(trialInfoWidget);
              parentDock.activateWidget(trialInfoWidget);
            }
            if (this.config.showTrial()) {
              parentDock.addGraphWidget(trialGraphWidget);
              parentDock.activateWidget(trialGraphWidget);
              trialGraphWidget.load(
                this.config.graphType(),
                this.config.useCache(),
              );
            }
            return true;
          },
          customForm: (
            graph: HistoryGraph,
            form: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
          ) => {
            // Toggle Tooltips
            let filterDiv = this.d3node.select(".history-content .filter");

            let scriptOptions = filterDiv.select(".script-options");

            let currentScript = scriptOptions.property("value");

            scriptOptions.html("");

            scriptOptions
              .append("option")
              .attr("value", "*")
              .text("All Scripts");

            for (let script of data.scripts) {
              scriptOptions.append("option").attr("value", script).text(script);
            }

            scriptOptions.property("value", currentScript);

            let filterToggle = form
              .append("input")
              .attr("id", "history-" + graph.graphId + "-toolbar-filter-check")
              .attr("type", "checkbox")
              .attr("name", "history-toolbar-filter-check")
              .attr("value", "show")
              .property("checked", filterDiv.classed("visible"))
              .on("change", () => {
                let visible = filterToggle.property("checked");
                filterToggleI
                  .classed("fa-circle-o", visible)
                  .classed("fa-circle", !visible);
                filterDiv
                  .classed("visible", visible)
                  .classed("show-toolbar", visible)
                  .classed("hide-toolbar", !visible);
              });
            let filterLabel = form
              .append("label")
              .attr(
                "for",
                "history-" + graph.graphId + "-toolbar-filter-check",
              );
            let filterToggleI = filterLabel
              .append("i")
              .classed("fa", true)
              .classed("fa-circle", !filterDiv.classed("visible"))
              .classed("fa-circle-o", filterDiv.classed("visible"));

            // Push trial
            form
              .append("a")
              .classed("toollink", true)
              .attr("id", "history-" + graph.graphId + "-push-trial")
              .attr("href", "#")
              .attr("title", "Push trial")
              .on("click", () =>
                this.buildPushCommand(this.modal, this.modalBody),
              )
              .append("i")
              .classed("fa fa-cloud-upload", true);

            // Pull trial
            form
              .append("a")
              .classed("toollink", true)
              .attr("id", "history-" + graph.graphId + "-pull-trial")
              .attr("href", "#")
              .attr("title", "Pull trial")
              .on("click", () =>
                this.buildPullCommand(this.modal, this.modalBody),
              )
              .append("i")
              .classed("fa fa-cloud-download", true);

            // Add remote
            form
              .append("a")
              .classed("toollink", true)
              .attr("id", "history-" + graph.graphId + "-add-remote")
              .attr("href", "#")
              .attr("title", "Add remote")
              .on("click", () =>
                this.buildAddRemote(this.modal, this.modalBody),
              )
              .append("i")
              .classed("fa fa-plus-circle", true);

            // Edit remote
            form
              .append("a")
              .classed("toollink", true)
              .attr("id", "history-" + graph.graphId + "-edit-remote")
              .attr("href", "#")
              .attr("title", "Edit remote")
              .on("click", () =>
                this.buildEditRemote(this.modal, this.modalBody),
              )
              .append("i")
              .classed("fa fa-pencil-square", true);

            // Delete remote
            form
              .append("a")
              .classed("toollink", true)
              .attr("id", "history-" + graph.graphId + "-delete-remote")
              .attr("href", "#")
              .attr("title", "Delete remote")
              .on("click", () =>
                this.buildDeleteRemote(this.modal, this.modalBody),
              )
              .append("i")
              .classed("fa fa-trash", true);
          },
        });
      },
    );
  }

  protected onResize(msg: Widget.ResizeMessage): void {
    if (!this.graph) {
      return;
    }
    this.graph.config.width = this.node.getBoundingClientRect().width - 24;
    this.graph.config.height = this.node.getBoundingClientRect().height - 24;
    this.graph.updateWindow();
  }

  private buildModal(div: any) {
    this.modal = d3_select<SVGSVGElement, any>(div)
      .append("div")
      .classed("modal fade", true)
      .attr("id", "commandsModal")
      .attr("tabindex", "-1")
      .attr("role", "dialog")
      .attr("aria-labelledby", "commandsModalTitle")
      .style("display", "none")
      .attr("aria-hidden", "true");

    let modalContent = this.modal
      .append("div")
      .classed("modal-dialog", true)
      .attr("role", "document")
      .append("div")
      .classed("modal-content", true); //modal content

    let modalHeader = modalContent.append("div").classed("modal-header", true); //modal header
    modalHeader
      .append("h5")
      .classed("modal-title", true)
      .attr("id", "exampleModalTitle")
      .text("Change Temporary Title"); //modal title

    this.modalBody = modalContent.append("div").classed("modal-body", true);

    modalHeader
      .append("button")
      .classed("close", true)
      .attr("type", "button")
      .text("x")
      .style("float", "right")
      .on("click", () => cleanModalBodyAndClose(this.modal, this.modalBody)); //close modal
  }

  private buildRightClickMenu() {
    //let modal = document.getElementById("commandsModal");
    this.buildRestoreTrialCommand(this.modal, this.modalBody);
    this.buildRestoreFileCommand(this.modal, this.modalBody);
    this.buildProvCommand();
    this.buildProspectiveCommand();
    this.buildExportPrologCommand(this.modal, this.modalBody);
    this.buildDataflowCommand(this.modal, this.modalBody);
    this.buildTrialFunctionDiffCommand(
      this.modal,
      this.modalBody,
      this.functionDiffWindow,
    );
  }

  buildTrialFunctionDiffCommand(
    modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>,
    functionDiffWindow: any,
  ) {
    let self = this;

    this.rightClickMenu
      .append("a")
      .classed("dropdown-item", true)
      .attr("href", "#")
      .attr("id", "trial-function-diff-option")
      .text("function activation diff")
      .on("click", function () {
        let parent = this.parentNode as Element;
        let trialId = parent.getAttribute("selected-trial") ?? "";

        buildTrialFunctionDiffModal(
          modal,
          modalBody,
          parent,
          trialId,
          functionDiffWindow,
          self,
        );
      });
  }

  buildDataflowCommand(
    modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>,
  ) {
    let self = this;
    this.rightClickMenu
      .append("a")
      .classed("dropdown-item", true)
      .attr("href", "#")
      .attr("id", "dataflow-option")
      .text("generate dataflow")
      .on("click", function () {
        let parent = this.parentNode as Element;
        let trialId = parent.getAttribute("selected-trial") ?? "";

        buildDataflowModal(
          modal,
          modalBody,
          parent,
          self.graph.config,
          trialId,
        );
      });
  }

  buildExportPrologCommand(
    modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>,
  ) {
    let self = this;
    this.rightClickMenu
      .append("a")
      .classed("dropdown-item", true)
      .attr("href", "#")
      .attr("id", "export-option")
      .text("generate prolog")
      .on("click", function () {
        let parent = this.parentNode as Element;
        let trialId = parent.getAttribute("selected-trial");
        let exportUrl = "/commands/export/" + trialId;
        let exportWindowId = "Export window " + trialId;

        buildExportPrologModal(
          modal,
          modalBody,
          exportUrl,
          self.graph.config,
          parent,
          exportWindowId,
          trialId,
        );
      });
  }

  buildProspectiveCommand() {
    let self = this;
    this.rightClickMenu
      .append("a")
      .classed("dropdown-item", true)
      .attr("href", "#")
      .attr("id", "prospective-option")
      .text("generate prospective graph")
      .on("click", function () {
        let parent = this.parentNode as Element;
        let trialId = parent.getAttribute("selected-trial");
        let trialDisplay = parent.getAttribute("selected-trial-simplified");

        if (!trialId) return;

        let prospectiveGraphWidget = new ProspectiveGraphWidget(
          "Prospective " + trialDisplay,
          "prospective-" + trialId + makeid(),
          trialId,
        );
        let parentDock: NowVisPanel = self.parent as NowVisPanel;

        parentDock.addGraphWidget(prospectiveGraphWidget);
        parentDock.activateWidget(prospectiveGraphWidget);
        prospectiveGraphWidget.load();
      });
  }

  buildProvCommand() {
    let self = this;
    this.rightClickMenu
      .append("a")
      .classed("dropdown-item", true)
      .attr("href", "#")
      .attr("id", "prov-option")
      .text("generate prov")
      .on("click", function () {
        let parent = this.parentNode as Element;
        let trialId = parent.getAttribute("selected-trial");
        let provWindowId = "Prov window " + trialId;

        if (document.getElementById(provWindowId)) return;

        let provUrl = "/commands/prov/" + trialId;

        fetch(provUrl, {
          method: "GET", // *GET, POST, PUT, DELETE, etc.
          headers: {
            "Content-Type": "application/json",
          },
        }).then((response) => {
          response.json().then((json) => {
            self.graph.config.customWindowTabCommand(
              parent.getAttribute("selected-trial-simplified")!,
              provWindowId,
              "Prov",
            );
            let provWindow = d3_select(document.getElementById(provWindowId));

            if (response.status == 200) {
              provWindow.style("overflow-y", "auto");
              let prov_lines = json.prov.split("\n");
              for (var line in prov_lines)
                provWindow.append("p").text(prov_lines[line]);
            } else {
              window.alert("No prov to export");
            }
          });
        });
      });
  }

  private buildRestoreFileCommand(
    modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>,
  ) {
    this.rightClickMenu
      .append("a")
      .classed("dropdown-item", true)
      .attr("href", "#")
      .attr("id", "restore-file-option")
      .text("restore file")
      .on("click", function () {
        let parent = this.parentNode as Element;
        let trialId = parent.getAttribute("selected-trial");

        let trialFiles: string[];

        fetch("/files/" + trialId, {
          method: "GET", // *GET, POST, PUT, DELETE, etc.
          headers: {
            "Content-Type": "application/json",
          },
        }).then((response) => {
          response.json().then((json) => {
            trialFiles = json.files;

            changeTitle(parent, "Restore file trial ");

            let submitButton;
            let form: d3_Selection<
              HTMLFormElement,
              {},
              HTMLElement | null,
              any
            >;

            showModal(modal);

            if (modalBody) {
              form = modalBody.append("form").attr("onsubmit", "return false;");
              //createFormTextInput(form, "restoreFile", "Restore file", "restoreFileHelp", "Write the name of the file you want to restore");
              createFormSelectInput(
                form,
                "restoreFile",
                "Restore file",
                0,
                trialFiles.length - 1,
                0,
                "",
                "",
                trialFiles,
              );
              createFormTextInput(
                form,
                "restoreFileID",
                "File identifier",
                "restoreIDHelp",
                "(optional) Identifies the file to be restored. It can be either the timestamp, the number of access, or the code hash",
              );
              createFormTextInput(
                form,
                "restoreFileTarget",
                "Target file path",
                "restoreTargetHelp",
                "(optional) specifies the target path of the restored file",
              );

              submitButton = form
                .append("button")
                .classed("btn btn-primary mb-2", true)
                .attr("type", "submit")
                .text("restore trial");
            }

            submitButton?.on("click", function () {
              //let fileToRestore : string | boolean = getTextInputFormByID("restoreFile", true);
              let fileToRestore = (<HTMLSelectElement>(
                document.getElementById("restoreFile")
              )).selectedOptions[0].value;
              let fileIdentifier: string | boolean = getTextInputFormByID(
                "restoreFileID",
                true,
              );
              let targetPath: string | boolean = getTextInputFormByID(
                "restoreFileTarget",
                false,
              );

              let restoreUrl =
                "/commands/restore/file/" +
                trialId +
                "/" +
                fileToRestore +
                "/" +
                fileIdentifier +
                "/" +
                targetPath;

              if (fileToRestore)
                getRestoreOrCollabCommand(restoreUrl, form, modalBody);
              else
                addAlert(
                  modalBody,
                  "alert-danger",
                  "Error!",
                  "The file's name is empty",
                );
            });
          });
        });
      });
  }

  private buildRestoreTrialCommand(
    modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>,
  ) {
    this.rightClickMenu
      .append("a")
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
          createFormCheckInput(
            form,
            "restoreSkipLocalModules",
            "Skip Local Modules",
          );
          createFormCheckInput(
            form,
            "restoreSkipFileAccess",
            "Skip File Access",
          );

          submitButton = form
            .append("button")
            .classed("btn btn-primary mb-2", true)
            .attr("type", "submit")
            .text("restore trial");
        }

        submitButton?.on("click", function () {
          let skipScript = (<HTMLInputElement>(
            document.getElementById("restoreSkipScript")
          )).checked;
          let skipModules = (<HTMLInputElement>(
            document.getElementById("restoreSkipLocalModules")
          )).checked;
          let skipFileAccess = (<HTMLInputElement>(
            document.getElementById("restoreSkipFileAccess")
          )).checked;

          let restoreUrl =
            "/commands/restore/trial/" +
            trialId +
            "/" +
            skipScript +
            "/" +
            skipModules +
            "/" +
            skipFileAccess;

          getRestoreOrCollabCommand(restoreUrl, form, modalBody);
        });
      });
  }

  private buildAddRemote(
    modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>,
  ) {
    document.getElementById("exampleModalTitle")!.textContent =
      "Add new remote";

    let submitButton;
    let form: d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>;

    showModal(modal);

    if (modalBody) {
      form = modalBody.append("form").attr("onsubmit", "return false;");
      createFormTextInput(form, "inputAddRemoteUrl", "Remote URL: ");
      createFormTextInput(form, "inputAddRemoteName", "Remote name: ");
      submitButton = form
        .append("button")
        .classed("btn btn-primary mb-2", true)
        .text("Add remote");
    }

    submitButton?.on("click", function () {
      let remoteURL = (<HTMLInputElement>(
        document.getElementById("inputAddRemoteUrl")
      )).value;
      let remoteName = (<HTMLInputElement>(
        document.getElementById("inputAddRemoteName")
      )).value;

      let addRemoteURL = "/collab/remotes/add/" + remoteName + "/" + remoteURL;

      fetch(addRemoteURL, {
        method: "POST", // *GET, POST, PUT, DELETE, etc.
        headers: {
          "Content-Type": "application/json",
        },
      }).then((response) => {
        response.json().then((json) => {
          form.remove();
          if (response.status == 200) {
            addAlert(
              modalBody,
              "alert-success",
              "Success!",
              json.terminal_text,
            );
          } else {
            addAlert(modalBody, "alert-danger", "Error!", "");
          }
        });
      });
    });
  }

  private buildDeleteRemote(
    modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>,
  ) {
    fetch("/collab/remotes/getall", {
      method: "GET", // *GET, POST, PUT, DELETE, etc.
      headers: {
        "Content-Type": "application/json",
      },
    }).then((response) => {
      response.json().then(async (json) => {
        if (response.status == 200) {
          this.executeCollabCommand(
            modal,
            modalBody,
            "editDeleteServerUrlId",
            "Delete remote",
            "delete",
            json.remotes,
          );
        } else {
          console.log("Failed to get remotes");
        }
      });
    });
  }

  private buildEditRemote(
    modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>,
  ) {
    fetch("/collab/remotes/getall", {
      method: "GET", // *GET, POST, PUT, DELETE, etc.
      headers: {
        "Content-Type": "application/json",
      },
    }).then((response) => {
      response.json().then(async (json) => {
        if (response.status == 200) {
          this.executeCollabCommand(
            modal,
            modalBody,
            "editRemoteServerUrlId",
            "Edit remote",
            "edit",
            json.remotes,
          );
        } else {
          console.log("Failed to get remotes");
        }
      });
    });
  }

  private buildPushCommand(
    modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>,
  ) {
    fetch("/collab/remotes/getall", {
      method: "GET", // *GET, POST, PUT, DELETE, etc.
      headers: {
        "Content-Type": "application/json",
      },
    }).then((response) => {
      response.json().then(async (json) => {
        if (response.status == 200) {
          this.executeCollabCommand(
            modal,
            modalBody,
            "pushServerUrlId",
            "Push experiment",
            "push",
            json.remotes,
          );
        } else {
          console.log("Failed to get remotes");
        }
      });
    });
  }

  private buildPullCommand(
    modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>,
  ) {
    fetch("/collab/remotes/getall", {
      method: "GET", // *GET, POST, PUT, DELETE, etc.
      headers: {
        "Content-Type": "application/json",
      },
    }).then((response) => {
      response.json().then(async (json) => {
        if (response.status == 200) {
          this.executeCollabCommand(
            modal,
            modalBody,
            "pullServerUrlId",
            "Pull experiment",
            "pull",
            json.remotes,
          );
        } else {
          console.log("Failed to get remotes");
        }
      });
    });
  }

  private executeCollabCommand(
    modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
    modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>,
    serverUrlId: string,
    title: string,
    command: string,
    remotes: any,
  ) {
    document.getElementById("exampleModalTitle")!.textContent = title;

    let submitButton;
    let form: d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>;

    showModal(modal);

    let select: d3_Selection<HTMLSelectElement, {}, HTMLElement | null, any>;

    if (modalBody) {
      form = modalBody.append("form").attr("onsubmit", "return false;");
      form.append("label").attr("for", "remotes").text("Remote: ");

      select = form
        .append("select")
        .attr("name", "remotes")
        .attr("id", "remotes");
      for (let i = 0; i < remotes.length; i++) {
        select
          .append("option")
          .attr("value", remotes[i].server_url)
          .text(remotes[i].name);
      }

      form.append("br");
      form.append("span").text("Remote URL: ");
      let remoteURLText = form
        .append("span")
        .attr("id", serverUrlId + "Remote")
        .text(remotes[0].server_url);
      select.on("change", () => {
        remoteURLText.text(select.node()!.value);
      });

      form.append("br");
      if (command == "edit") {
        createFormTextInput(form, "inputEditRemoteName", "Remote new name: ");
      }
      submitButton = form
        .append("button")
        .classed("btn btn-primary mb-2", true)
        .text(title);
    }

    submitButton?.on("click", function () {
      let serverUrl = select.node()!.value;

      let collabCommandUrl = "/commands/" + command + "/" + serverUrl;
      if (command == "edit")
        collabCommandUrl =
          "/collab/remotes/edit/" +
          (<HTMLInputElement>document.getElementById("inputEditRemoteName"))
            .value +
          "/" +
          serverUrl;
      if (command == "delete")
        collabCommandUrl = "/collab/remotes/delete/" + serverUrl;

      getRestoreOrCollabCommand(collabCommandUrl, form, modalBody);
    });
  }
}

function buildTrialFunctionDiffModal(
  modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
  modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>,
  parent: Element,
  trialId: string,
  functionDiffWindow: any,
  self: any,
) {
  let secondTrialId: string;
  changeTitle(parent, "Function activation diff trial");
  //document.getElementById("exampleModalTitle")!.textContent = "Function activation diff trial " + trialId;

  fetch("/getFunctionActivations/" + trialId, {
    method: "GET", // *GET, POST, PUT, DELETE, etc.
    headers: {
      "Content-Type": "application/json",
    },
  }).then((response) => {
    response.json().then((json) => {
      showModal(modal);

      if (modalBody) {
        //scrollableModal(modalBody);

        modalBody.append("span").text("Select this trial's activation: ");
        let firstTrialSelectActivation = modalBody
          .append("select")
          .classed("form-select", true)
          .attr("arial-label", "firstTrialFunctionActivations")
          .attr("id", "firstTrialFunctionActivations")
          .style("max-width", "480px");

        for (let activation in json["function_activations"]) {
          firstTrialSelectActivation
            .append("option")
            .attr("value", json["function_activations"][activation].id)
            .text(
              JSON.stringify(json["function_activations"][activation])
                .replace(/{|}/g, "")
                .substring(0, 70),
            );
        }

        modalBody.append("br");

        modalBody.append("span").text("Select the other trial: ");

        let secondTrialSelect = modalBody
          .append("select")
          .classed("form-select", true)
          .attr("arial-label", "secondTrialSelect")
          .attr("id", "secondTrialSelect");

        fetch("/getAllTrialsIdsAndTags", {
          method: "GET", // *GET, POST, PUT, DELETE, etc.
          headers: {
            "Content-Type": "application/json",
          },
        }).then((response) => {
          response.json().then((json) => {
            for (let trial in json) {
              secondTrialSelect
                .append("option")
                .attr("value", json[trial].id)
                .text(json[trial].tag);
            }

            modalBody.append("br");

            modalBody
              .append("span")
              .text("Select the other trial's activation: ");

            let secondTrialSelectActivation = modalBody
              .append("select")
              .classed("form-select", true)
              .attr("arial-label", "secondTrialFunctionActivations")
              .attr("id", "secondTrialFunctionActivations")
              .style("max-width", "480px");

            getSecondTrialFunctionActivations(secondTrialSelectActivation);

            secondTrialSelect.on("change", () => {
              getSecondTrialFunctionActivations(secondTrialSelectActivation);
            });

            modalBody.append("br");

            let submitButton = modalBody
              .append("button")
              .classed("btn btn-primary mb-2", true)
              .style("margin-top", "10px")
              .text("Confirm");

            submitButton!.on("click", function () {
              let firstTrialFunctionId = (<HTMLSelectElement>(
                document.getElementById("firstTrialFunctionActivations")
              )).selectedOptions[0].value;
              let secondTrialFunctionId = (<HTMLSelectElement>(
                document.getElementById("secondTrialFunctionActivations")
              )).selectedOptions[0].value;

              let url =
                "/commands/diff/" +
                trialId +
                "/" +
                firstTrialFunctionId +
                "/" +
                secondTrialId +
                "/" +
                secondTrialFunctionId;

              fetch(url, {
                method: "GET", // *GET, POST, PUT, DELETE, etc.
                headers: {
                  "Content-Type": "application/json",
                },
              }).then((response) => {
                response.json().then((json) => {
                  functionDiffWindow(
                    json,
                    "Diff trial " +
                      trialId +
                      " activation_id " +
                      firstTrialFunctionId +
                      " trial " +
                      secondTrialId +
                      " activation_id " +
                      secondTrialFunctionId,
                    self.parent as NowVisPanel,
                  );
                });
              });

              cleanModalBodyAndClose(modal, modalBody);
            });
          });
        });
      }
    });
  });

  function getSecondTrialFunctionActivations(
    secondTrialSelectActivation: d3_Selection<
      HTMLSelectElement,
      {},
      HTMLElement | null,
      any
    >,
  ) {
    secondTrialId = (<HTMLSelectElement>(
      document.getElementById("secondTrialSelect")
    )).selectedOptions[0].value;

    fetch("/getFunctionActivations/" + secondTrialId, {
      method: "GET", // *GET, POST, PUT, DELETE, etc.
      headers: {
        "Content-Type": "application/json",
      },
    }).then((response) => {
      response.json().then((json) => {
        secondTrialSelectActivation.html("");

        for (let activation in json["function_activations"]) {
          secondTrialSelectActivation
            .append("option")
            .attr("value", json["function_activations"][activation].id)
            .text(
              JSON.stringify(json["function_activations"][activation])
                .replace(/{|}/g, "")
                .substring(0, 70),
            );
        }
      });
    });
  }
}

function buildExportPrologModal(
  modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
  modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>,
  exportUrl: string,
  config: HistoryConfig,
  parent: Element,
  exportWindowId: string,
  trialId: string | null,
) {
  let submitButton;
  let form: d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>;
  document.getElementById("exampleModalTitle")!.textContent = "Prolog";

  showModal(modal);

  if (modalBody) {
    form = modalBody.append("form").attr("onsubmit", "return false;");

    createFormCheckInput(
      form,
      "exportProvRules",
      "Also exports inference rules",
    );
    createFormCheckInput(form, "exportProvHideTimestamps", "Hide timestamps");

    submitButton = form
      .append("button")
      .classed("btn btn-primary mb-2", true)
      .text("Generate prolog");
  }

  submitButton?.on("click", () => {
    let inferenceRules = (<HTMLInputElement>(
      document.getElementById("exportProvRules")
    )).checked;
    let hideTimestamps = (<HTMLInputElement>(
      document.getElementById("exportProvHideTimestamps")
    )).checked;

    exportUrl += "/" + inferenceRules + "/" + hideTimestamps;

    buildExportPrologTab(exportUrl, config, parent, exportWindowId, trialId);
    cleanModalBodyAndClose(modal, modalBody);
  });
}

function buildExportPrologTab(
  exportUrl: string,
  config: HistoryConfig,
  parent: Element,
  exportWindowId: string,
  trialId: string | null,
) {
  if (document.getElementById(exportWindowId)) {
    window.alert(
      "Close trial " + trialId + " prolog tab before generating a new prolog",
    );
    return;
  }

  fetch(exportUrl, {
    method: "GET", // *GET, POST, PUT, DELETE, etc.
    headers: {
      "Content-Type": "application/json",
    },
  }).then((response: any) => {
    response.json().then((json: any) => {
      if (response.status == 200) {
        config.customWindowTabCommand(
          parent.getAttribute("selected-trial-simplified")!,
          exportWindowId,
          "Prolog",
        );
        let exportWindow = d3_select(document.getElementById(exportWindowId));

        let form: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any> = (
          exportWindow
            .append("form")
            .attr("onsubmit", "return false;") as d3_Selection<
            HTMLFormElement,
            {},
            HTMLElement | null,
            any
          >
        )
          .append("div")
          .classed("form-row", true);
        createFormTextInput(
          form,
          "exportPrologProgram" + trialId,
          "Prolog",
        ).classed("col-7", true);
        createFormTextInput(
          form,
          "exportPrologQuery" + trialId,
          "Query",
        ).classed("col", true);

        let submitButton = form
          .append("div")
          .classed("col-auto", true)
          .style("padding-top", "5vh")
          .append("button")
          .classed("btn btn-primary mb-2", true)
          .text("Execute Query");

        (<HTMLInputElement>(
          document.getElementById("exportPrologProgram" + trialId)
        ))!.value = json.export;

        let prologSession = pl.create(1000);

        let answerCallback = (answer: any, answerString: string) => {
          if (answer == false) {
            let answerCardTextId = "Answers prolog card text " + trialId;
            let answerCardText = document.getElementById(answerCardTextId)
              ? d3_select(document.getElementById(answerCardTextId))
              : null;
            if (answerCardText == null) {
              let answerWindow = exportWindow.append("div");
              answerWindow
                .classed("card", true)
                .append("div")
                .classed("card-header", true)
                .text("Answers");
              answerCardText = answerWindow
                .append("div")
                .classed("card-body", true)
                .append("p")
                .classed("card-text", true)
                .attr("id", answerCardTextId)
                .style("overflow-y", "auto")
                .style("max-height", "35vh");
            }

            answerCardText!.html(answerString);
            return;
          }
          answerString +=
            prologSession.format_answer(answer).toString() + "<br>";

          prologSession.answer((answer: any) =>
            answerCallback(answer, answerString),
          );
        };

        submitButton.on("click", () => {
          let prologProgram = getTextInputFormByID(
            "exportPrologProgram" + trialId,
          );
          let userQuery = getTextInputFormByID("exportPrologQuery" + trialId);
          if (prologProgram && userQuery) {
            prologSession.consult(prologProgram, {
              success: () => {
                console.log("Prolog consult success");
                prologSession.query(userQuery, {
                  success: () => {
                    prologSession.answer((answer: any) =>
                      answerCallback(answer, ""),
                    );
                  },
                  error: () => {
                    console.log("Erro query");
                  },
                });
              },
              error: () => {
                console.log("Prolog consult error");
              },
            });
          }
        });
      } else {
        console.log("Export error");
      }
    });
  });
}

function scrollableModal(
  modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>,
) {
  let modalDialog = (
    document.getElementsByClassName(
      "modal-dialog",
    ) as HTMLCollectionOf<HTMLElement>
  )[0];
  modalDialog.style.overflowY = "initial";
  modalDialog.style.maxHeight = "85%";
  modalBody.style("overflow-y", "auto").style("height", "80vh");
}

function getDataflow(
  response: any,
  config: HistoryConfig,
  parent: Element,
  dataflowWindowId: string,
  dataflowUrl: string,
) {
  response.json().then((json: any) => {
    if (response.status == 200) {
      let trialIdSimplified = parent.getAttribute("selected-trial-simplified")!;

      config.customWindowTabCommand(
        trialIdSimplified,
        dataflowWindowId,
        "Dataflow",
      );
      console.log(json.dataflow);

      instance().then((viz) => {
        const dataflowWindow = document.getElementById(dataflowWindowId);

        // Download SVG Button, excluding hint, and excluding checkbox
        dataflowButtons(
          dataflowWindow,
          dataflowWindowId,
          "Click on a function call, then (Ctrl or Shift)+click on another one to exclude prior provenience",
          json.dataflow,
        );

        let selectedNode: Element | undefined;
        let selectedEdge: Element | undefined;

        //dataflowWindow!.style.overflowY = dataflowWindow!.style.overflowX = "auto";
        let svgElement = viz.renderSVGElement(json.dataflow);
        dataflowWindow!.appendChild(svgElement);
        svgPanZoom(svgElement, {
          preventMouseEventsDefault: false,
          dblClickZoomEnabled: false,
        });

        for (
          let nodeIndex = 0;
          nodeIndex < svgElement.children[0].children[0].children.length;
          nodeIndex++
        ) {
          let presentNode: Element | undefined =
            svgElement.children[0].children[0].children[nodeIndex];
          if (
            presentNode.getAttribute("class") == "node" &&
            presentNode.children[1].tagName.toLowerCase() == "polygon"
          ) {
            let presentNodeSelection = d3_select(presentNode);

            presentNodeSelection.style("cursor", "pointer");

            presentNodeSelection.on("click", (event: MouseEvent) => {
              if (selectedNode) {
                selectedNode.children[1].setAttribute("stroke", "black");
              }

              if (selectedNode && (event.ctrlKey || event.shiftKey)) {
                deletePriorNodes(
                  selectedNode,
                  presentNode!,
                  viz,
                  dataflowUrl,
                  config,
                  trialIdSimplified,
                  dataflowWindowId,
                );
              } else {
                selectedNode =
                  svgElement.children[0].children[0].children[nodeIndex];
                selectedNode.children[1].setAttribute("stroke", "red");
              }
            });
          } else if (
            presentNode.getAttribute("class") == "edge" &&
            presentNode.children[1].tagName.toLowerCase() == "path"
          ) {
            let presentNodeSelection = d3_select(presentNode);

            presentNodeSelection.style("cursor", "pointer");

            presentNodeSelection.on("click", () => {
              if (selectedEdge) {
                selectedEdge.children[1].setAttribute("stroke", "black");
              }
              selectedEdge =
                svgElement.children[0].children[0].children[nodeIndex];
              selectedEdge.children[1].setAttribute("stroke", "red");
            });
          }
        }
      });
    } else {
      console.log("Dataflow error");
    }
  });
}

function checkboxOpenDataflowExcludeProvenanceNewWindow(
  dataflowWindow: HTMLElement,
) {
  let dataflowWindowD3Select = d3_select(dataflowWindow);
  let checkboxID = dataflowWindow.getAttribute("id") + "OpenNewWindowOption";

  dataflowWindowD3Select
    .append("input")
    .attr("id", checkboxID)
    .attr("type", "checkbox");

  dataflowWindowD3Select
    .append("label")
    .attr("for", checkboxID)
    .text("Don't open dataflow with excluded provenance in a new tab")
    .style("font-family", "sans-serif")
    .style("font-size", "12px")
    .style("pointer-events", "none");
}

function excludePriorProvenanceHint(
  dataflowWindow: HTMLElement | null,
  text: string,
) {
  d3_select(dataflowWindow)
    .append("div")
    .append("div")
    .text(text)
    .style("font-family", "sans-serif")
    .style("font-size", "12px")
    .style("pointer-events", "none");
}

function chooseDataflowExcludedProvenanceWindowId(
  presentWindowId: string,
  newWindowId: string,
) {
  if (
    (
      document.getElementById(
        presentWindowId + "OpenNewWindowOption",
      ) as HTMLInputElement
    ).checked
  )
    return presentWindowId;
  return newWindowId;
}

function deletePriorNodes(
  selectedNode: Element,
  presentNode: Element,
  viz: any,
  dataflowUrl: string,
  config: HistoryConfig,
  trialIdSimplified: string,
  presentWindowId: string,
) {
  dataflowUrl = dataflowUrl.substring(0, dataflowUrl.lastIndexOf("/"));
  dataflowUrl =
    dataflowUrl.substring(0, dataflowUrl.lastIndexOf("/")) + "/true/";

  let selectedNodeEvaluationTitle = selectedNode.children[0].innerHTML;
  let presentNodeOrderEvaluationTitle = presentNode.children[0].innerHTML;

  let firstEvaluationOrder = Number(
    selectedNodeEvaluationTitle.replace("e_", ""),
  );
  let lastEvaluationOrder = Number(
    presentNodeOrderEvaluationTitle.replace("e_", ""),
  );
  if (firstEvaluationOrder > lastEvaluationOrder) {
    lastEvaluationOrder = firstEvaluationOrder;
    firstEvaluationOrder = Number(
      presentNodeOrderEvaluationTitle.replace("e_", ""),
    );
  }

  let dataflowUrlLastEvaluation = dataflowUrl + lastEvaluationOrder;
  let dataflowUrlFirstEvaluation = dataflowUrl + firstEvaluationOrder;

  let excludingProvenanceWindow = getDataflowWindowExcludeSomeProvenance(
    presentWindowId,
    "Dataflow excluding prior " +
      presentNodeOrderEvaluationTitle +
      " " +
      selectedNodeEvaluationTitle +
      " window " +
      trialIdSimplified,
    trialIdSimplified,
    config,
  );

  excludingProvenanceWindow!.textContent = "Loading...";

  fetch(dataflowUrlLastEvaluation, {
    method: "GET", // *GET, POST, PUT, DELETE, etc.
    headers: {
      "Content-Type": "application/json",
    },
  }).then((responseLastEvaluation: any) => {
    responseLastEvaluation.json().then((jsonLastEvaluation: any) => {
      let dataflowLastEvaluation = jsonLastEvaluation.dataflow;
      fetch(dataflowUrlFirstEvaluation, {
        method: "GET", // *GET, POST, PUT, DELETE, etc.
        headers: {
          "Content-Type": "application/json",
        },
      }).then((responseFirstEvaluation: any) => {
        responseFirstEvaluation.json().then((jsonFirstEvaluation: any) => {
          let dataflowFirstEvaluation = jsonFirstEvaluation.dataflow;

          dataflowAMinusDataflowB(
            dataflowLastEvaluation,
            dataflowFirstEvaluation,
            firstEvaluationOrder,
            excludingProvenanceWindow,
            viz,
            dataflowUrl,
            config,
            lastEvaluationOrder,
          );
        });
      });
    });
  });
}

function getDataflowWindowExcludeSomeProvenance(
  presentWindowId: string,
  newWindowId: string,
  trialIdSimplified: string,
  config: HistoryConfig,
) {
  let excludingProvenanceWindowId = chooseDataflowExcludedProvenanceWindowId(
    presentWindowId,
    newWindowId,
  );

  let excludingProvenanceWindow = document.getElementById(
    excludingProvenanceWindowId,
  );

  if (!excludingProvenanceWindow) {
    config.customWindowTabCommand(
      trialIdSimplified,
      excludingProvenanceWindowId,
      "Dataflow excluding some provenance",
    );

    excludingProvenanceWindow = document.getElementById(
      excludingProvenanceWindowId,
    );
  }
  return excludingProvenanceWindow;
}

function dataflowAMinusDataflowB(
  dataflowA: any,
  dataflowB: any,
  selectedEvaluationOrder: number,
  excludingProvenanceWindow: HTMLElement | null,
  viz: any,
  dataflowUrl: string,
  config: HistoryConfig,
  lastEvaluationId: number,
) {
  //SET MINUS OPERATION A-B "The set A−B consists of elements that are in A but not in B. For example if A={1,2,3} and B={3,5}, then A−B={1,2}."
  let linesDataflowA = dataflowA.split("\n");
  let linesDataflowB = dataflowB.split("\n");
  let newDataflow = linesDataflowA.slice(0);

  removesLinesInDataflowFirstEvaluationFromDataflowLastEvaluation(
    linesDataflowB,
    newDataflow,
    selectedEvaluationOrder,
  );

  let dataflowIsAligned = addsDeletedNodeSettingsAndChecksIfDataflowIsAligned(
    newDataflow,
    selectedEvaluationOrder,
    linesDataflowA,
  );

  removesDeletedEvaluationsFromAligment(dataflowIsAligned, newDataflow);

  console.log("------");
  let newDataflowString = newDataflow.join("\n");
  console.log(newDataflowString);
  console.log("------");

  excludingProvenanceWindow!.textContent = "";

  dataflowButtons(
    excludingProvenanceWindow,
    excludingProvenanceWindow!.getAttribute("id")!,
    "(Ctrl or Shift)+click on a function call to exclude prior provenience",
    newDataflowString,
  );

  let svgElement = viz.renderSVGElement(newDataflowString);
  excludingProvenanceWindow!.appendChild(svgElement);
  svgPanZoom(svgElement, {
    preventMouseEventsDefault: false,
    dblClickZoomEnabled: false,
  });

  addsOptionToDeletePriorNodesToDeletedPriorNodesDataflow(
    svgElement,
    viz,
    dataflowUrl,
    newDataflowString,
    excludingProvenanceWindow,
    config,
    lastEvaluationId,
  );
}

function addsOptionToDeletePriorNodesToDeletedPriorNodesDataflow(
  svgElement: any,
  viz: any,
  dataflowUrl: string,
  newDataflowString: any,
  excludingProvenanceWindow: HTMLElement | null,
  config: HistoryConfig,
  lastEvaluationId: number,
) {
  let selectedEdge: Element | undefined;

  for (
    let nodeIndex = 0;
    nodeIndex < svgElement.children[0].children[0].children.length;
    nodeIndex++
  ) {
    let selectedNode: Element =
      svgElement.children[0].children[0].children[nodeIndex];
    if (
      selectedNode.getAttribute("class") == "node" &&
      selectedNode.children[1].tagName.toLowerCase() == "polygon"
    ) {
      let selectedNodeSelection = d3_select(selectedNode);

      selectedNodeSelection.style("cursor", "pointer");

      selectedNodeSelection.on("click", (event: MouseEvent) => {
        if (event.ctrlKey || event.shiftKey)
          deletePriorNodesAfterDeletingPriorNodes(
            selectedNode,
            viz,
            dataflowUrl,
            newDataflowString,
            excludingProvenanceWindow,
            config,
            lastEvaluationId,
          );
      });
    } else if (
      selectedNode.getAttribute("class") == "edge" &&
      selectedNode.children[1].tagName.toLowerCase() == "path"
    ) {
      let selectedNodeSelection = d3_select(selectedNode);

      selectedNodeSelection.style("cursor", "pointer");

      selectedNodeSelection.on("click", () => {
        if (selectedEdge) {
          selectedEdge.children[1].setAttribute("stroke", "black");
        }
        selectedEdge = svgElement.children[0].children[0].children[nodeIndex];
        selectedEdge!.children[1].setAttribute("stroke", "red");
      });
    }
  }
}

function deletePriorNodesAfterDeletingPriorNodes(
  selectedNode: Element,
  viz: any,
  dataflowUrl: string,
  newDataflowString: any,
  excludingProvenanceWindow: HTMLElement | null,
  config: HistoryConfig,
  lastEvaluationId: number,
) {
  let selectedNodeOrderEvaluationTitle = selectedNode.children[0].innerHTML;
  let selectedEvaluationOrder = Number(
    selectedNodeOrderEvaluationTitle.replace("e_", ""),
  );

  if (lastEvaluationId == selectedEvaluationOrder) {
    window.alert("You can't remove everything.");
    return undefined;
  }

  dataflowUrl = dataflowUrl.substring(0, dataflowUrl.lastIndexOf("/"));
  dataflowUrl =
    dataflowUrl.substring(0, dataflowUrl.lastIndexOf("/")) + "/true/";

  let dataflowUrlPresentEvaluation = dataflowUrl + selectedEvaluationOrder;

  let excludingProvenanceWindowId =
    excludingProvenanceWindow?.getAttribute("id");
  excludingProvenanceWindow = getDataflowWindowExcludeSomeProvenance(
    excludingProvenanceWindowId!,
    excludingProvenanceWindowId + "OneMore",
    "",
    config,
  ); //TODO get simplifiedtrialid from wxcludingprovenancewindow

  excludingProvenanceWindow!.textContent = "Loading...";

  fetch(dataflowUrlPresentEvaluation, {
    method: "GET", // *GET, POST, PUT, DELETE, etc.
    headers: {
      "Content-Type": "application/json",
    },
  }).then((responseLastEvaluation: any) => {
    responseLastEvaluation.json().then((json: any) => {
      let selectedEvaluationDataflow = json.dataflow;

      dataflowAMinusDataflowB(
        newDataflowString,
        selectedEvaluationDataflow,
        selectedEvaluationOrder,
        excludingProvenanceWindow,
        viz,
        dataflowUrl,
        config,
        lastEvaluationId,
      );
    });
  });
}

function removesDeletedEvaluationsFromAligment(
  dataflowIsAligned: boolean,
  newDataflow: any,
) {
  if (dataflowIsAligned) {
    let evaluations: any = [];

    for (let lineIndex = 3; lineIndex < newDataflow.length; lineIndex++) {
      let line = newDataflow[lineIndex];
      if (line.includes("label"))
        evaluations.push(
          line
            .replace(/\[[^\]]*?\];/, "")
            .split(" ")[4]
            .trim(),
        );
      else if (line.includes("{rank=")) {
        let alignedEvaluations = line.split(" ");

        for (
          let alignedEvalIndex = 5;
          alignedEvalIndex < alignedEvaluations.length;
          alignedEvalIndex++
        ) {
          let alignedEval = alignedEvaluations[alignedEvalIndex]
            .replace("}\r", "")
            .trim();

          if (!evaluations.includes(alignedEval))
            newDataflow[lineIndex] = newDataflow[lineIndex].replace(
              alignedEval,
              "",
            );
        }
      } else if (line.includes("->")) break;
    }
  }
}

function removesLinesInDataflowFirstEvaluationFromDataflowLastEvaluation(
  linesDataflowB: any,
  newDataflow: any,
  selectedEvaluationOrder: number,
) {
  for (let i = 3; i < linesDataflowB.length - 2; i++) {
    let indexOfDataflowLineToRemove;

    if (linesDataflowB[i].includes("->") && linesDataflowB[i].includes("[")) {
      let lineToRemove = linesDataflowB[i].replace(/\[[^\]]*\]/, "");

      indexOfDataflowLineToRemove = newDataflow.findIndex(
        (dataflowLine: string) => {
          return dataflowLine.replace(/\[[^\]]*\]/, "") == lineToRemove;
        },
      );
    } else indexOfDataflowLineToRemove = newDataflow.indexOf(linesDataflowB[i]);

    if (
      indexOfDataflowLineToRemove > -1 &&
      !linesDataflowB[i].includes("_" + selectedEvaluationOrder + " [")
    )
      newDataflow.splice(indexOfDataflowLineToRemove, 1);
  }
}

function addsDeletedNodeSettingsAndChecksIfDataflowIsAligned(
  newDataflow: any,
  selectedEvaluationOrder: number,
  linesDataflowA: any,
) {
  let tempArray: any[] = [];
  let isAligned = false;

  newDataflow.forEach((line: string) => {
    if (!isAligned && line.includes("{rank")) isAligned = true;

    if (line.includes("->")) {
      let evaluationWithoutSettings = line.split(" ")[6];
      if (
        Number(evaluationWithoutSettings.replace("e_", "").replace("a_", "")) <
        selectedEvaluationOrder
      ) {
        // TODO revise if firstEvaluationOrder is right
        let lineToAdd = linesDataflowA.find((string: string) =>
          string.includes(evaluationWithoutSettings + " ["),
        );
        if (newDataflow.indexOf(lineToAdd) < 0) tempArray.push(lineToAdd);
      }
    }
  });

  tempArray.forEach((item) => newDataflow.splice(3, 0, item));

  return isAligned;
}

function buildDataflowModal(
  modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
  modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>,
  parent: Element,
  config: HistoryConfig,
  trialId: string,
) {
  let submitButton;
  let evaluationList;
  let form: d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>;
  document.getElementById("exampleModalTitle")!.textContent = "Dataflow";

  fetch("/dataflow/evaluations/" + trialId, {
    method: "GET", // *GET, POST, PUT, DELETE, etc.
    headers: {
      "Content-Type": "application/json",
    },
  }).then((response) => {
    response.json().then((json) => {
      evaluationList = json.evaluations;
      let selectedEvaluation: string | null;
      let dataflowTextInputEvaluation: HTMLSelectElement;

      showModal(modal);

      if (modalBody) {
        scrollableModal(modalBody);

        form = modalBody.append("form").attr("onsubmit", "return false;");
        createFormCheckInput(form, "dataFlowShowType", "Show type nodes");
        createFormCheckInput(form, "dataFlowHideTimestamps", "Hide timestamps");
        createFormCheckInput(
          form,
          "dataFlowHideInternals",
          "Show variables and functions which name starts with a leading underscore",
        );
        createFormCheckInput(
          form,
          "dataFlowHideNotCode",
          "Hide evaluations that aren't from the code",
        );
        createFormCheckInput(
          form,
          "dataFlowActivationNames",
          "Display nodes with their activation names instead",
        );
        createFormCheckInput(
          form,
          "dataFlowHideFunc",
          "Hide func type evaluations",
        );

        createFormSelectInput(
          form,
          "dataflowShowAccesses",
          "Show file accesses",
          0,
          4,
          1,
          "dataflowShowAccessesHelp",
          "(default: Shows each file once (hide external accesses))",
          [
            "Hides file accesses",
            "Shows each file once (hide external accesses)",
            "Shows each file once (show external accesses)",
            "Shows all accesses (except external accesses)",
            "Shows all accesses (including external accesses)",
          ],
        );

        createFormSelectInput(
          form,
          "dataflowEvaluation",
          "Combine evaluation nodes",
          0,
          2,
          1,
          "dataflowEvaluationHelp",
          "(default: Combines evaluation nodes by assignment)",
          [
            "Not combine evaluation nodes",
            "Combines evaluation nodes by assignment",
            "Combines evaluation nodes by value",
          ],
        );

        createFormSelectInput(
          form,
          "dataflowGroup",
          "Align evalutions in the same column",
          0,
          2,
          0,
          "dataflowGroupHelp",
          "(default: Does no align). With this option, all variables in a loop appear grouped, reducing the width of the graph. It may affect the graph legibility. The alignment is independent for each activation.",
          ["Does no align", "Aligns by line", "Aligns by line and column"],
        );

        createFormSelectInput(
          form,
          "dataflowMode",
          "Graph mode",
          0,
          4,
          1,
          "dataflowModeHelp",
          "(default: coarseGrain). 'activation' presents only function activations and file accesses. Dependencies on the dataflow are clustered by depth(-d). 'coarseGrain' is the same as the activation dataflow, but with the addition of parameters and variable assignment of function activations. 'looplessCoarseGrain' is the same as the coarseGrain dataflow, but it doesn't repeat function activations when they're in the same line in a loop. 'fineGrain' is the same as the coarseGrain dataflow with the addition of variables, all user defined evaluations and data values. 'all' presents a dataflow with all evaluations and function activations. Dependencies on the dataflow are not clustered.",
          [
            "activation",
            "coarseGrain",
            "looplessCoarseGrain",
            "fineGrain",
            "all",
          ],
        );

        createFormNumberInput(
          form,
          "dataflowDepth",
          "Visualization depth",
          0,
          0,
          "dataflowDepthHelp",
          '(default: 0) 0 represents infinity. This parameter is ignored when the mode is "all"',
        );
        createFormNumberInput(
          form,
          "dataflowValueLength",
          "Maximum length of values",
          0,
          0,
          "dataflowValueLengthHelp",
          "(default: 0). 0 indicates that values should be hidden.The values appear on the second line of node lables. E.g. if it is set to '10', it will show 'data.dat',  but it will transform 'data2.dat' in to 'da...dat' to respect the length restriction (note that '' is part of the value). Minimum displayable value: 5. Suggested: 55.",
        );
        createFormNumberInput(
          form,
          "dataflowName",
          "Maximum length of names",
          0,
          55,
          "dataflowNameHelp",
          "(default: 55). 0 indicates that values should be hidden. Minimum displayable value: 5. Suggested: 55.",
        );

        let dataflowEvaluationInput = createFormTextInput(
          form,
          "dataflowTextInputEvaluation",
          "Evaluation was derived from: ",
          "dataflowSelectEvaluationHelp",
          "Filter that shows only one evaluation and the ones that derived it",
        );

        form.append("div").attr("id", "autocompleteSuggestionsResults");

        dataflowTextInputEvaluation = <HTMLSelectElement>(
          document.getElementById("dataflowTextInputEvaluation")
        );

        addsAutocompleteToDataflowWDF(
          dataflowEvaluationInput,
          dataflowTextInputEvaluation,
          evaluationList,
        );

        submitButton = form
          .append("button")
          .classed("btn btn-primary mb-2", true)
          .text("Generate dataflow");
      }

      submitButton!.on("click", function () {
        let dataFlowShowType = (<HTMLInputElement>(
          document.getElementById("dataFlowShowType")
        )).checked;
        let dataFlowHideTimestamps = (<HTMLInputElement>(
          document.getElementById("dataflowMode")
        )).checked;
        let dataFlowHideInternals = (<HTMLInputElement>(
          document.getElementById("dataFlowHideInternals")
        )).checked;
        let dataFlowHideNotCode = (<HTMLInputElement>(
          document.getElementById("dataFlowHideNotCode")
        )).checked;
        let dataFlowActivationNames = (<HTMLInputElement>(
          document.getElementById("dataFlowActivationNames")
        )).checked;
        let dataFlowHideFunc = (<HTMLInputElement>(
          document.getElementById("dataFlowHideFunc")
        )).checked;

        let dataflowFileAccesses = (<HTMLSelectElement>(
          document.getElementById("dataflowShowAccesses")
        )).selectedOptions[0].index;
        let dataflowEvaluation = (<HTMLSelectElement>(
          document.getElementById("dataflowEvaluation")
        )).selectedOptions[0].index;
        let dataflowGroup = (<HTMLSelectElement>(
          document.getElementById("dataflowGroup")
        )).selectedOptions[0].index;
        let dataflowMode = (<HTMLSelectElement>(
          document.getElementById("dataflowMode")
        )).selectedOptions[0].value;

        let dataflowDepth = (<HTMLInputElement>(
          document.getElementById("dataflowDepth")
        )).value;
        let dataflowValueLength = (<HTMLInputElement>(
          document.getElementById("dataflowValueLength")
        )).value;
        let dataflowName = (<HTMLInputElement>(
          document.getElementById("dataflowName")
        )).value;

        let trialId = parent.getAttribute("selected-trial");

        selectedEvaluation = dataflowTextInputEvaluation.getAttribute(
          "selectedEvaluationID",
        );

        let dataflowUrl =
          "/commands/dataflow/" +
          trialId +
          "/" +
          dataFlowShowType +
          "/" +
          dataFlowHideTimestamps +
          "/" +
          dataFlowHideInternals +
          "/" +
          dataFlowHideNotCode +
          "/" +
          dataFlowActivationNames +
          "/" +
          dataFlowHideFunc +
          "/" +
          dataflowFileAccesses +
          "/" +
          dataflowEvaluation +
          "/" +
          dataflowGroup +
          "/" +
          dataflowDepth +
          "/" +
          dataflowValueLength +
          "/" +
          dataflowName +
          "/" +
          dataflowMode;
        dataflowUrl +=
          selectedEvaluation && !selectedEvaluation.includes("undefined")
            ? "/true/" + selectedEvaluation
            : "/false/0";

        let dataflowWindowId = "Dataflow window " + trialId;

        /* if (document.getElementById(dataflowWindowId)) {
          window.alert("Close trial " + trialId + " dataflow tab before generating a new dataflow");
          return;
        } */

        if (document.getElementById(dataflowWindowId))
          dataflowWindowId += crypto.randomUUID();

        fetch(dataflowUrl, {
          method: "GET", // *GET, POST, PUT, DELETE, etc.
          headers: {
            "Content-Type": "application/json",
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

function addsAutocompleteToDataflowWDF(
  dataflowEvaluationInput: d3_Selection<
    HTMLDivElement,
    {},
    HTMLElement | null,
    any
  >,
  dataflowTextInputEvaluation: HTMLSelectElement,
  evaluationList: any,
) {
  dataflowEvaluationInput.on("keyup", () => {
    let input = dataflowTextInputEvaluation.value;
    let autocompleteSuggestionsResults = <HTMLSelectElement>(
      document.getElementById("autocompleteSuggestionsResults")
    );
    let evaluationInputHint = <HTMLSelectElement>(
      document.getElementById("dataflowSelectEvaluationHelp")
    );

    autocompleteSuggestionsResults.innerHTML = "";

    let suggestions: any[];

    if (input == "") {
      autocompleteSuggestionsResults.setAttribute("style", "");
      evaluationInputHint.style.opacity = "1";
      suggestions = [];
      dataflowTextInputEvaluation.setAttribute(
        "selectedEvaluationID",
        "undefined",
      );
    } else {
      autocompleteSuggestionsResults.style.border = "1px solid #ccc";
      autocompleteSuggestionsResults.style.padding = "3px";
      autocompleteSuggestionsResults.style.marginTop = "-3rem";
      evaluationInputHint.style.opacity = "0";

      suggestions = evaluationList!.filter((evaluation: any) => {
        if (evaluation.name.includes(input)) return evaluation;
      });

      autocompleteSuggestionsResults.innerHTML =
        '<ul id="dataflowEvaluationSuggestionsBoxId" style="list-style-type: none; padding: 0; margin: 0;"></ul>';

      for (let i = 0; i < suggestions.length; i++) {
        let evaluationSuggestionId =
          suggestions[i].evaluation_id + " " + "evaluationSuggestionItem";

        d3_select(document.getElementById("dataflowEvaluationSuggestionsBoxId"))
          .append("li")
          .attr("id", evaluationSuggestionId)
          .style("padding", "5px 0")
          .style("z-index", 1)
          .text(
            "Evaluation: " +
              suggestions[i].name +
              "         " +
              "Code_line: " +
              suggestions[i].first_char_line,
          )
          .on("click", () => {
            dataflowTextInputEvaluation.value = suggestions[i].name;
            input = suggestions[i].name;
            dataflowTextInputEvaluation.setAttribute(
              "selectedEvaluationID",
              suggestions[i].evaluation_id,
            );
          })
          .on("mouseover", () => {
            d3_select(document.getElementById(evaluationSuggestionId)).style(
              "background-color",
              "#eee",
            );
          })
          .on("mouseout", () => {
            d3_select(document.getElementById(evaluationSuggestionId)).style(
              "background-color",
              "",
            );
          });
      }
    }
  });
}

function downloadDataflowAsSVG(
  dataflowWindow: HTMLElement | null,
  dataflowWindowId: string,
  dataflowDOT: string,
  appendDiv: boolean,
) {
  let div = appendDiv
    ? d3_select(dataflowWindow)
        .append("div")
        .attr("id", dataflowWindowId + "-downloadDiv")
    : d3_select(document.getElementById(dataflowWindowId + "-downloadDiv"));
  div
    .append("a")
    .classed("toollink", true)
    .attr("id", dataflowWindowId + "-downloadSVG")
    .attr("href", "#")
    .style("color", "black")
    .style("margin-right", "10px")
    .attr("title", "Download dataflow SVG")
    .on("click", () => {
      instance().then((viz) => {
        let svgElement = viz.renderSVGElement(dataflowDOT);
        fs.saveAs(
          new Blob([svgElement.outerHTML], { type: "image/svg+xml" }),
          "dataflow.svg",
        );
      });
      //fs.saveAs(new Blob([dataflowWindow!.getElementsByTagName("svg")[0].outerHTML], { type: "image/svg+xml" }), "dataflow.svg");
    })
    .append("i")
    .classed("fa fa-download", true);
}

function downloadDataflowAsDOT(
  dataflowWindow: HTMLElement | null,
  dataflowWindowId: string,
  dataflowDOT: string,
  appendDiv: boolean,
) {
  let div = appendDiv
    ? d3_select(dataflowWindow)
        .append("div")
        .attr("id", dataflowWindowId + "-downloadDiv")
    : d3_select(document.getElementById(dataflowWindowId + "-downloadDiv"));
  div
    .append("a")
    .classed("toollink", true)
    .attr("id", dataflowWindowId + "-downloadDOT")
    .attr("href", "#")
    .style("color", "black")
    .attr("title", "Download dataflow DOT")
    .on("click", () => {
      fs.saveAs(
        new Blob([dataflowDOT.trim()], { type: "text/plain;charset=utf-8" }),
        "dataflow.dot",
      );
    })
    .append("i")
    .classed("fa fa-file-text", true);
}

function dataflowButtons(
  dataflowWindow: HTMLElement | null,
  dataflowWindowId: string,
  excludeProvenanceHint: string,
  dataflowDOT: string,
) {
  downloadDataflowAsSVG(dataflowWindow, dataflowWindowId, dataflowDOT, true);
  downloadDataflowAsDOT(dataflowWindow, dataflowWindowId, dataflowDOT, false);
  excludePriorProvenanceHint(dataflowWindow, excludeProvenanceHint);
  checkboxOpenDataflowExcludeProvenanceNewWindow(dataflowWindow!);
}

function getRestoreOrCollabCommand(
  serverUrl: string,
  form: d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>,
  modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>,
) {
  fetch(serverUrl, {
    method: "GET", // *GET, POST, PUT, DELETE, etc.
    headers: {
      "Content-Type": "application/json",
    },
  }).then((response) => {
    response.json().then((json) => {
      form.remove();
      if (
        response.status == 200 &&
        (!json.terminal_text.includes("not") || serverUrl.includes("edit"))
      ) {
        addAlert(modalBody, "alert-success", "Success!", json.terminal_text);
      } else {
        addAlert(modalBody, "alert-danger", "Error!", json.terminal_text);
      }
    });
  });
}

function changeTitle(parent: Element, commandTitle: string) {
  let trialIdTitle = parent.getAttribute("selected-trial-simplified");
  document.getElementById("exampleModalTitle")!.textContent =
    commandTitle + trialIdTitle;
}

function cleanModalBodyAndClose(
  modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
  modalBody: d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>,
) {
  document.getElementsByClassName("modal-body")[0].textContent = "";
  modalBody.style("height", null);
  hideModal(modal);
}

function addAlert(
  div: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
  alertType: string,
  title: string,
  text: string,
) {
  let feedbackAlert = div
    .append("div")
    .classed("alert " + alertType, true)
    .attr("role", "alert");
  feedbackAlert
    .append("h4")
    .text(title)
    .append("button")
    .classed("close", true)
    .attr("type", "button")
    .text("x")
    .on("click", () => {
      feedbackAlert.remove();
    });
  feedbackAlert.append("p").text(text);
}

function createFormCheckInput(
  form: d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>,
  checkInputId: string,
  text: string,
) {
  let checkDiv = form.append("div").classed("form-check", true);
  checkDiv
    .append("input")
    .classed("form-check-input", true)
    .attr("value", "")
    .attr("id", checkInputId)
    .attr("type", "checkbox");
  checkDiv
    .append("label")
    .classed("form-check-label", true)
    .attr("for", checkInputId)
    .text(text);
}

function createFormTextInput(
  form: d3_Selection<
    HTMLFormElement | HTMLDivElement,
    {},
    HTMLElement | null,
    any
  >,
  textInputId: string,
  text: string,
  helpId?: string,
  helpText?: string,
) {
  let textDiv = form.append("div").classed("form-group", true);
  textDiv.append("label").attr("for", textInputId).text(text);
  let textInput = textDiv
    .append("textarea")
    .classed("form-control", true)
    .attr("id", textInputId);
  if (helpId && helpText) {
    textInput.attr("aria-describedby", helpId);
    textDiv
      .append("small")
      .classed("form-text text-muted", true)
      .attr("id", helpId)
      .text(helpText);
  }

  return textDiv;
}

function createFormSelectInput(
  form: d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>,
  selectId: string,
  selectText: string,
  minOptionNumber: number,
  maxOptionNumber: number,
  defaultOption?: number,
  helpId?: string,
  helpText?: string,
  optionsLabels?: Array<string>,
) {
  let selectDiv = form.append("div").classed("form-group", true);
  let selectInput = selectDiv
    .append("label")
    .attr("for", selectId)
    .text(selectText)
    .append("select")
    .classed("form-control", true)
    .attr("id", selectId);

  if (helpId && helpText) {
    selectInput.attr("aria-describedby", helpId);
    selectDiv
      .append("small")
      .classed("form-text text-muted", true)
      .attr("id", helpId)
      .text(helpText);
  }

  for (
    var optionNumber = minOptionNumber;
    optionNumber <= maxOptionNumber;
    optionNumber++
  ) {
    let inputLabel = optionsLabels ? optionsLabels[optionNumber] : optionNumber;
    let input = selectInput.append("option").text(inputLabel);
    if (defaultOption && optionNumber == defaultOption)
      input.attr("selected", "selected");
  }
}

function createFormNumberInput(
  form: d3_Selection<HTMLFormElement, {}, HTMLElement | null, any>,
  id: string,
  text: string,
  minValue: number,
  defaultValue: number,
  helpId?: string,
  helpText?: string,
) {
  let numberDiv = form.append("div").classed("form-group", true);
  numberDiv
    .append("label")
    .classed("form-check-label", true)
    .attr("for", id)
    .text(text);

  numberDiv
    .append("input")
    .attr("type", "number")
    .attr("id", id)
    .attr("min", minValue)
    .attr("value", defaultValue)
    .attr("oninput", "validity.valid||(value='');")
    .attr("aria-describedby", "dataflowDepthHelp");

  if (helpId && helpText) {
    numberDiv.attr("aria-describedby", helpId);
    numberDiv
      .append("small")
      .classed("form-text text-muted", true)
      .attr("id", helpId)
      .text(helpText);
  }
}

function getTextInputFormByID(id: string, replace?: boolean) {
  let formTextInput: string | boolean = (<HTMLInputElement>(
    document.getElementById(id)
  )).value;
  if (replace) formTextInput.replace("/", "%2F").replace("\\", "%5C");
  if (!formTextInput) formTextInput = false;
  return formTextInput;
}

function hideModal(
  modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
) {
  if (modal)
    modal
      .style("display", "none")
      .style("padding-right", "")
      .classed("show", false)
      .attr("aria-hidden", "true");
}

function showModal(
  modal: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>,
) {
  if (modal)
    modal
      .style("display", "block")
      .style("padding-right", "17px")
      .classed("show", true)
      .attr("aria-hidden", "false");
}

