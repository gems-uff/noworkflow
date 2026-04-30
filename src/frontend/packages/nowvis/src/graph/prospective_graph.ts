import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from "d3-selection";

import { Widget } from "@lumino/widgets";
import { instance } from "@viz-js/viz";
import * as fs from "file-saver";

declare var require: any;
const svgPanZoom = require("svg-pan-zoom");

export class ProspectiveGraphWidget extends Widget {
  name: string;
  cls: string;
  trialId: string;
  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  dotContent: string | null;
  currentZoom: number;
  originalViewBox: { x: number; y: number; width: number; height: number } | null;

  static url(trialId: string): string {
    return `trials/${trialId}/prospective.dot`;
  }

  constructor(name: string, cls: string, trialId: string) {
    super({ node: ProspectiveGraphWidget.createNode(cls) });
    this.d3node = d3_select(this.node);
    this.addClass("content");
    this.addClass("prospective-widget");
    this.title.label = name;
    this.title.closable = true;
    this.title.caption = `${name} Prospective Graph`;
    this.name = name;
    this.cls = cls;
    this.trialId = trialId;
    this.dotContent = null;
    this.currentZoom = 1.0;
    this.originalViewBox = null;

    this.createToolbar();
  }

  static createNode(cls: string): HTMLElement {
    let node = document.createElement("div");
    let d3node = d3_select(node);

    node.style.display = "flex";
    node.style.flexDirection = "column";
    node.style.width = "100%";
    node.style.height = "100%";
    node.style.overflow = "hidden";

    d3node.append("div")
      .classed("prospective-toolbar", true)
      .style("flex-shrink", "0")
      .style("height", "30px")
      .style("min-height", "30px")
      .style("max-height", "30px")
      .style("padding", "2px 5px")
      .style("background", "#f5f5f5")
      .style("border-bottom", "1px solid #ddd")
      .style("display", "flex")
      .style("align-items", "center")
      .style("gap", "8px");

    d3node.append("div")
      .classed("prospective-content", true)
      .style("flex", "1")
      .style("min-height", "0")
      .style("overflow", "hidden")
      .style("position", "relative");

    return node;
  }

  createToolbar() {
    let toolbar = this.d3node.select(".prospective-toolbar");

    toolbar
      .append("a")
      .classed("toollink", true)
      .attr("href", "#")
      .attr("title", "Zoom In")
      .style("padding", "4px 8px")
      .style("text-decoration", "none")
      .style("color", "#333")
      .style("font-size", "14px")
      .on("click", (event: Event) => {
        event.preventDefault();
    	this.applyZoom(1.2);
      })
      .append("i")
      .classed("fa fa-search-plus", true);

    toolbar
      .append("a")
      .classed("toollink", true)
      .attr("href", "#")
      .attr("title", "Zoom Out")
      .style("padding", "4px 8px")
      .style("text-decoration", "none")
      .style("color", "#333")
      .style("font-size", "14px")
      .on("click", (event: Event) => {
        event.preventDefault();
        this.applyZoom(0.8);
      })
      .append("i")
      .classed("fa fa-search-minus", true);

    toolbar
      .append("a")
      .classed("toollink", true)
      .attr("href", "#")
      .attr("title", "Download graph SVG")
      .style("padding", "4px 8px")
      .style("text-decoration", "none")
      .style("color", "#333")
      .style("font-size", "14px")
      .on("click", () => {
        this.downloadSVG();
      })
      .append("i")
      .classed("fa fa-download", true);

    toolbar
      .append("a")
      .classed("toollink", true)
      .attr("href", "#")
      .attr("title", "Download graph DOT")
      .style("padding", "4px 8px")
      .style("text-decoration", "none")
      .style("color", "#333")
      .style("font-size", "14px")
      .on("click", () => {
        this.downloadDOT();
      })
      .append("i")
      .classed("fa fa-file-text", true);
  }

  load() {
    let contentDiv = this.node.getElementsByClassName("prospective-content")[0];
    contentDiv.innerHTML = "<p>Loading prospective provenance for trial:" + this.trialId + "</p>";

    // Fetch DOT content from backend
    const url = ProspectiveGraphWidget.url(this.trialId);

    fetch(url)
      .then((response) => {
        if (!response.ok) {
          return response.text().then((errorText) => {
            throw new Error(`HTTP ${response.status}: ${errorText}`);
          });
        }
        return response.text();
      })
      .then((dotContent) => {
        this.dotContent = dotContent;
        this.renderGraph(dotContent, contentDiv);
      })
      .catch((error) => {
        console.error("Error fetching prospective provenance:", error);
        container.innerHTML = "<p>Error fetching prospective provenance:" + error + "</p>";
      });
  }

  renderGraph(dotContent: string, container: Element) {
    instance()
      .then((viz) => {
        container.innerHTML = "";
        let svgElement = viz.renderSVGElement(dotContent);

        const viewBoxAttr = svgElement.getAttribute("viewBox");
        if (viewBoxAttr) {
          const values = viewBoxAttr.split(" ").map(parseFloat);
          this.originalViewBox = {
            x: values[0],
            y: values[1],
            width: values[2],
            height: values[3]
          };

          const zoomFactor = 1.1;
          const newWidth = this.originalViewBox.width * zoomFactor;
          const newHeight = this.originalViewBox.height * zoomFactor;

          const newX = this.originalViewBox.x + (this.originalViewBox.width - newWidth) / 2;
          const newY = this.originalViewBox.y + (this.originalViewBox.height - newHeight) / 2;

          svgElement.setAttribute("viewBox", `${newX} ${newY} ${newWidth} ${newHeight}`);
        }

        svgElement.style.width = "100%";
        svgElement.style.height = "100%";
        svgElement.style.display = "block";
        svgElement.style.position = "absolute";
        svgElement.style.top = "0";
        svgElement.style.left = "0";

        container.appendChild(svgElement);

        this.addPanFunctionality(svgElement);
      })
      .catch((error) => {
        console.error("Error rendering prospective graph:", error);
        container.innerHTML = "<p>Error rendering graph: " + error + "</p>";
      });
  }

  addPanFunctionality(svgElement: SVGSVGElement) {
    let isPanning = false;
    let startPoint = { x: 0, y: 0 };
    let startViewBox = { x: 0, y: 0 };

    svgElement.style.cursor = "grab";

    svgElement.addEventListener("mousedown", (e: MouseEvent) => {
      isPanning = true;
      startPoint = { x: e.clientX, y: e.clientY };

      const viewBoxAttr = svgElement.getAttribute("viewBox");
      if (viewBoxAttr) {
        const values = viewBoxAttr.split(" ").map(parseFloat);
        startViewBox = { x: values[0], y: values[1] };
      }

      svgElement.style.cursor = "grabbing";
      e.preventDefault();
    });

    svgElement.addEventListener("mousemove", (e: MouseEvent) => {
      if (!isPanning) return;

      const viewBoxAttr = svgElement.getAttribute("viewBox");
      if (!viewBoxAttr) return;

      const values = viewBoxAttr.split(" ").map(parseFloat);
      const width = values[2];
      const height = values[3];

      const dx = (e.clientX - startPoint.x) * (width / svgElement.clientWidth);
      const dy = (e.clientY - startPoint.y) * (height / svgElement.clientHeight);

      const newX = startViewBox.x - dx;
      const newY = startViewBox.y - dy;

      svgElement.setAttribute("viewBox", `${newX} ${newY} ${width} ${height}`);
    });

    svgElement.addEventListener("mouseup", () => {
      isPanning = false;
      svgElement.style.cursor = "grab";
    });

    svgElement.addEventListener("mouseleave", () => {
      isPanning = false;
      svgElement.style.cursor = "grab";
    });
  }

  downloadSVG() {
    if (this.dotContent) {
      instance().then((viz) => {
        let svgElement = viz.renderSVGElement(this.dotContent!);
        fs.saveAs(
          new Blob([svgElement.outerHTML], { type: "image/svg+xml" }),
          "prospective_" + this.trialId + ".svg",
        );
      });
    }
  }

  downloadDOT() {
    if (this.dotContent) {
      fs.saveAs(
        new Blob([this.dotContent], { type: "text/plain;charset=utf-8" }),
        "prospective_" + this.trialId + ".dot",
      );
    }
  }

  applyZoom(factor: number) {
    const svgElement = this.node.querySelector("svg");
    if (!svgElement || !this.originalViewBox) return;

    const viewBoxAttr = svgElement.getAttribute("viewBox");
    if (!viewBoxAttr) return;

    const values = viewBoxAttr.split(" ").map(parseFloat);
    const currentX = values[0];
    const currentY = values[1];
    const currentWidth = values[2];
    const currentHeight = values[3];

    this.currentZoom *= factor;

    const newWidth = currentWidth / factor;
    const newHeight = currentHeight / factor;

    const centerX = currentX + currentWidth / 2;
    const centerY = currentY + currentHeight / 2;

    const newX = centerX - newWidth / 2;
    const newY = centerY - newHeight / 2;

    svgElement.setAttribute("viewBox", `${newX} ${newY} ${newWidth} ${newHeight}`);
  }
}
