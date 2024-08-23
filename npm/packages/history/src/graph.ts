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

import * as fs from 'file-saver';

import { HistoryConfig, HistoryState } from './config';
import { VisibleHistoryNode, VisibleHistoryEdge } from './structures';
import { HistoryGraphData, HistoryNodeData, HistoryTrialNodeData } from './structures';
import { D3ZoomEvent } from 'd3';

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
  

  nodes: VisibleHistoryNode[] = [];
  versionNodes: VisibleHistoryNode[] = [];
  edges: VisibleHistoryEdge[] = [];
  maxX: number = 0;
  maxY: number = 0;
  maxId: number = 0;
  
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
        const e = event as unknown as WheelEvent;
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
