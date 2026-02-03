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

    // Add toolbar
    this.createToolbar();
  }

  static createNode(cls: string): HTMLElement {
    let node = document.createElement("div");
    let d3node = d3_select(node);

    // Set up container to take full space
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

    // Zoom In button
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
        this.zoomIn();
      })
      .append("i")
      .classed("fa fa-search-plus", true);

    // Zoom Out button
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
        this.zoomOut();
      })
      .append("i")
      .classed("fa fa-search-minus", true);

    // Download SVG button
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

    // Download DOT button
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

    // Show loading state
    contentDiv.innerHTML = `
      <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; padding: 40px;">
        <div style="border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite;"></div>
        <p style="margin-top: 20px; color: #666;">Loading prospective provenance for trial ${this.trialId}...</p>
        <style>
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        </style>
      </div>
    `;

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
        console.log("Successfully fetched prospective provenance DOT");
        this.dotContent = dotContent;
        this.renderGraph(dotContent, contentDiv);
      })
      .catch((error) => {
        console.error("Error fetching prospective provenance:", error);
        // Show error message in graph area
        contentDiv.innerHTML = `
          <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; padding: 40px; text-align: center;">
            <i class="fa fa-exclamation-triangle" style="font-size: 48px; color: #e74c3c; margin-bottom: 20px;"></i>
            <h3 style="color: #e74c3c; margin: 0 0 10px 0;">Failed to Load Prospective Provenance</h3>
            <p style="color: #666; margin: 0 0 10px 0; max-width: 500px;">
              Could not fetch prospective provenance for trial <code>${this.trialId}</code>
            </p>
            <p style="color: #999; margin: 0; font-size: 0.9em; max-width: 500px;">
              ${error.message}
            </p>
            <button onclick="location.reload()" style="margin-top: 20px; padding: 10px 20px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer;">
              Reload Page
            </button>
          </div>
        `;
      });
  }

  renderGraph(dotContent: string, container: Element) {
    console.log("Rendering prospective graph...");
    console.log("DOT content length:", dotContent.length);
    instance()
      .then((viz) => {
        console.log("Viz.js instance loaded");
        container.innerHTML = "";
        let svgElement = viz.renderSVGElement(dotContent);
        console.log("SVG element created:", svgElement);
        console.log(
          "SVG element dimensions:",
          svgElement.clientWidth,
          svgElement.clientHeight,
        );
        console.log("SVG viewBox:", svgElement.getAttribute("viewBox"));
        console.log(
          "Container dimensions:",
          (container as HTMLElement).clientWidth,
          (container as HTMLElement).clientHeight,
        );

        // Store original viewBox before any transformations
        const viewBoxAttr = svgElement.getAttribute("viewBox");
        if (viewBoxAttr) {
          const values = viewBoxAttr.split(" ").map(parseFloat);
          this.originalViewBox = {
            x: values[0],
            y: values[1],
            width: values[2],
            height: values[3]
          };

          // Apply initial zoom by adjusting viewBox
          const zoomFactor = 0.6;
          const newWidth = this.originalViewBox.width * zoomFactor;
          const newHeight = this.originalViewBox.height * zoomFactor;

          const newX = this.originalViewBox.x + (this.originalViewBox.width - newWidth) / 2;
          const newY = this.originalViewBox.y + (this.originalViewBox.height - newHeight) / 2;

          svgElement.setAttribute("viewBox", `${newX} ${newY} ${newWidth} ${newHeight}`);
          console.log("Applied initial zoom, new viewBox:", svgElement.getAttribute("viewBox"));
        }

        // Style SVG to fill container completely
        svgElement.style.width = "100%";
        svgElement.style.height = "100%";
        svgElement.style.display = "block";
        svgElement.style.position = "absolute";
        svgElement.style.top = "0";
        svgElement.style.left = "0";

        container.appendChild(svgElement);
        console.log("SVG appended to container");

        // Add simple pan functionality
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

  zoomIn() {
    this.applyZoom(1.2);
  }

  zoomOut() {
    this.applyZoom(0.8);
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

  protected onResize(msg: Widget.ResizeMessage): void {
    // Resize is handled automatically via flexbox layout
    // SVG uses 100% width/height with position: absolute
    // No manual intervention needed
  }
}
