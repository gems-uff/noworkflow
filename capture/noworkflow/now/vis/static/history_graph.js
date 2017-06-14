/*global d3*/

function HistoryGraph(id, svg, options) {
  var self = this;

  self.custom_select_node = options.select_node || function () { return null; };
  self.custom_ctrl_click = options.ctrl_click || function () { return null; };
  self.custom_size = options.custom_size || function () {
    return [HistoryGraph.consts.width, HistoryGraph.consts.height];
  };
  self.hint_message = options.hint_message;
  if (options.hint_message === undefined) {
    self.hint_message = "Ctrl+Shift click or ⌘+Shift click to diff trials";
  }
  self.graph_id = id;

  self.nodes = [];
  self.edges = [];
  self.max = 0;

  self.state = {
    selected_node: null,
    mousedown_node: null,
    just_scale: false
  };
  self.use_tooltip = false;

  self.div = d3.select("body").append("div")
    .classed("now-tooltip now-history-tooltip", true)
    .style("max-width", "250px")
    .style("opacity", 0)
    .on("mouseout", function () {
      self._close_tooltip();
    });

  self.svg = svg;

  self._create_hint()

  self.height = self.custom_size()[1];

  self._create_marker('end-arrow', 'endarrow', '#000')
  self._create_marker('start-arrow', 'startarrow', '#000')

  self.svg_g = svg.append("g")
    .attr("id", self._graph_id())
    .classed(HistoryGraph.consts.graph_class, true);

  var svg_g = self.svg_g;

  self.path = svg_g.append('svg:g').selectAll('path');
  self.circle = svg_g.append('svg:g').selectAll('g');

  // Mouse events
  svg.on("mouseup", function (d) {
    self._svg_mouseup(d);
  });

  // Drag and Zoom
  self.drag = d3.behavior.drag();
  self.drag_svg = d3.behavior.zoom()
    .on("zoom", function () {
      self._zoomed();
    })
    .on("zoomstart", function () {
      d3.select('body').style("cursor", "move");
    })
    .on("zoomend", function () {
      d3.select('body').style("cursor", "auto");
    });
  svg.call(self.drag_svg).on("dblclick.zoom", null);

}

HistoryGraph.consts =  {
  selected_class: "selected",
  graph_class: "historygraph",
  circle_class: "node",
  marker_width: 3,
  marker_height: 3,
  move_x: 20,
  move_y: 25,
  move_y2: 10,
  radius: 20,
  spacing: 17,
  margin: 30,
  height: 100,
  width: 200
};


HistoryGraph.prototype._create_marker = function (name, cls, fill) {
  var self = this;
  self.svg.append("svg:defs").selectAll("marker")
    .data([name])
    .enter().append("svg:marker")
      .attr("id", String)
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 6)
      .attr("refY", 0) //
      .attr("markerWidth", HistoryGraph.consts.marker_width)
      .attr("markerHeight", HistoryGraph.consts.marker_height)
      .attr("orient", "auto")
    .append("svg:path")
      .classed(cls, true)
      .attr("fill", fill)
      .attr("d", "M0,-5L10,0L0,5");
};

HistoryGraph.prototype._create_hint = function () {
  this.hint_element = this.svg.append("text")
    .text(this.hint_message)
    .attr('font-family', 'sans-serif')
    .attr('font-size', '12px')
    .attr('pointer-events', 'none')
    .attr("dx", 5)
    .attr("dy", 45);
}

HistoryGraph.prototype._graph_id = function () {
  var self = this;
  return "history-graph-" + self.graph_id;
};


HistoryGraph.prototype._unselect_node = function () {
  var self = this,
    state = self.state;
  var unselected = self.circle.filter(function (cd) {
    return cd.id === state.selected_node.id;
  }).select('circle')
    .classed(HistoryGraph.consts.selected_class, false);
  self._update_circle(unselected);
  state.selected_node = null;
};

/*jslint unparam: true*/
HistoryGraph.prototype._node_mousedown = function (d3node, d) {
  var self = this,
    state = self.state;
  d3.event.stopPropagation();
  state.mousedown_node = d;
  self._close_tooltip();
};
/*jslint unparam: false*/

HistoryGraph.prototype._node_mouseup = function (d3node, d) {
  var self = this,
    state = self.state;

  var mousedown_node = state.mousedown_node;

  if (!mousedown_node) {
    return;
  }

  if (state.just_scale) {
    // dragged, not clicked
    state.just_scale = false;
  } else {
    if (d3.event.ctrlKey || d3.event.shiftKey || d3.event.altKey) {
      self.custom_ctrl_click(d, state.selected_node);
      return;
    }
    if (state.selected_node) {
      self._unselect_node();
    }

    d3node
      .attr('fill', 'rgb(200, 238, 241)')
      .classed(HistoryGraph.consts.selected_class, true);
    state.selected_node = d;
    self.custom_select_node(d);
  }

  state.mousedown_node = null;
  return;
};

HistoryGraph.prototype._svg_mouseup = function () {
  var state = this.state;
  if (state.just_scale) {
    // dragged not clicked
    state.just_scale = false;
  }
};

HistoryGraph.prototype._update_path = function (path) {
  var consts = HistoryGraph.consts,
    colors = d3.scale.category10();

  return path.attr("d", function (d) {
    var deltaX = d.target.x - d.source.x,
      deltaY = d.target.y - d.source.y,
      dist = Math.sqrt(deltaX * deltaX + deltaY * deltaY),
      normX = deltaX / dist,
      normY = deltaY / dist,
      sourcePadding = consts.radius + (d.left ? 3 : -5),
      targetPadding = consts.radius + (d.right ? 3 : -5),
      sourceX = d.source.x + (sourcePadding * normX),
      sourceY = d.source.y + (sourcePadding * normY),
      targetX = d.target.x - (targetPadding * normX),
      targetY = d.target.y - (targetPadding * normY);
    var step = 0;
    if (d.level > 0) {
      step += consts.move_y;
      step += (d.level - 1) * consts.move_y2;
    }

    var result = 'M' + sourceX + ',' + sourceY;
    result += 'C' + (sourceX - consts.move_x / 2) + ',' + sourceY;
    result += ',' + (sourceX - consts.move_x / 2) + ',' + (sourceY + 3 * step / 4);
    result += ',' + (sourceX - consts.move_x) + ',' + (sourceY + step);

    result += 'L' + (sourceX - consts.move_x) + ',' + (sourceY + step);
    result += ',' + (targetX + consts.move_x) + ',' + (sourceY + step);

    result += 'C' + (targetX + consts.move_x / 2) + ',' + (sourceY + 3 * step / 4);
    result += ',' + (targetX + consts.move_x / 2) + ',' + sourceY;
    result += ',' + targetX + ',' + targetY;

    return result;
  }).attr('marker-start', function (d) {
    return d.left ? 'url(#start-arrow)' : '';
  }).attr('marker-end', function (d) {
    return d.right ? 'url(#end-arrow)' : '';
  }).attr('stroke', function (d) {
    return d3.rgb(colors(d.level)).darker().toString();
  });
};

HistoryGraph.prototype._update_circle = function (circle) {
  return (
    circle
      .attr("transform", function (d) {
        return "translate(" + d.x + "," + d.y + ")";
      })
      .attr("stroke", "#000")
      .attr("stroke-width", "2.5px")
      .attr("fill", function (d) {
        if (d3.select(this).classed(HistoryGraph.consts.selected_class)) {
          return 'rgb(200, 238, 241)';
        }
        if (d.info.status === 'unfinished') {
          return "rgb(238, 200, 241)";
        }
        if (d.info.status === 'finished') {
          return "#F6FBFF";
        }
        if (d.info.status === 'backup') {
          return "rgb(241, 238, 200)";
        }
        return '#666';
      })
  );
};

HistoryGraph.prototype._zoomed = function () {
  var self = this;
  self.state.just_scale = true;
  self._close_tooltip();
  d3.select("#" + self._graph_id())
    .attr("transform", "translate(" + d3.event.translate + ") scale(" + d3.event.scale + ")");
};

HistoryGraph.prototype._show_tooltip = function (d) {
  var self = this;
  self.div.classed("hidden", false);
  self.div.transition()
    .duration(200)
    .style("opacity", 0.9);
  self.div.html(d.tooltip)
    .style("left", (d3.event.pageX - 3) + "px")
    .style("top", (d3.event.pageY - 28) + "px");
};

HistoryGraph.prototype._close_tooltip = function () {
  var self = this;
  self.div.transition()
    .duration(500)
    .style("opacity", 0);
  self.div.classed("hidden", true);
};

HistoryGraph.prototype.load = function (data, width) {
  var self = this,
    nodes = [],
    edges = [],
    spacing = HistoryGraph.consts.spacing,
    margin = HistoryGraph.consts.margin;
  var spacing2 = 2 * spacing,
    spacing4 = 4 * spacing,
    end = width - margin,
    max = 0,
    id = 0,
    last = data.nodes.length - 1;
  var i, node, x, y, edge;

  for (i = last; i >= 0; i--) {
    node = data.nodes[i];
    x = end - spacing4 * id;
    y = margin + node.level * spacing2;

    nodes.push({
      id: id,
      x: x,
      y: y,
      title: node.id,
      info: node,
      tooltip: node.tooltip
    });
    max = Math.max(max, y);
    id += 1;
  }
  max += spacing2;
  self.max = max;

  for (i = 0; i < data.edges.length; i++) {
    edge = data.edges[i];
    edge.source = nodes[last - edge.source];
    edge.target = nodes[last - edge.target];

    edges.push(edge);
  }

  self.nodes = nodes;
  self.edges = edges;
  self.update_window();
  self.reset_zoom();
  self.restart();

  return nodes;
};

HistoryGraph.prototype.reset_zoom = function () {
  var self = this,
    scale = self.height / self.max;
  if (scale < 1.0) {
    self.drag_svg.scale(scale);
    self.drag_svg.translate([self.width * (1 - scale), 0]);
    self.drag_svg.event(self.svg);
  } else {
    self.drag_svg.scale(1);
    self.drag_svg.translate([0, 0]);
    self.drag_svg.event(self.svg);
  }
  self.state.just_scale = false;
};

HistoryGraph.prototype.select_node = function (node) {
  this.state.selected_node = node;
  this.custom_select_node(node);
  d3.select($('#history text.trial-id:contains("' + node.title + '")')
    .siblings()[0])
    .attr('fill', 'rgb(200, 238, 241)')
    .classed(HistoryGraph.consts.selected_class, true);
};

HistoryGraph.prototype.restart = function () {

  var self = this,
    consts = HistoryGraph.consts;

  // path (link) group
  self.path = self.path.data(self.edges);

  // update existing links
  self._update_path(self.path);

  // add new paths
  var path = self.path.enter().append("svg:path")
    .classed('link', true)
    .attr('cursor', 'crosshair')
    .attr('fill', 'none')
    .attr('stroke', '#000')
    .attr('stroke-width', '4px');

  self._update_path(path);

  // remove old links
  self.path.exit().remove();

  // circle (node) group
  self.circle = self.circle.data(self.nodes, function (d) { return d.id; });


  self._update_circle(self.circle.selectAll('circle'));

  // add new nodes
  var g = self.circle.enter().append("svg:g")
    .classed(consts.circle_class, true);

  self._update_circle(
    g.append('svg:circle')
      .attr('stroke-width', '2px')
      .attr('cursor', 'pointer')
      .attr('stroke', '#333')
      .attr('r', consts.radius)
  ).on('mousedown', function (d) {
    self._node_mousedown(d3.select(this), d);
  }).on('mouseup', function (d) {
    self._node_mouseup(d3.select(this), d);
  }).on('mouseover', function (d) {
    if (!self.state.mousedown_node && self.use_tooltip) {
      self._close_tooltip();
      self._show_tooltip(d);
    }
    d3.select(this)
      .attr('fill', 'rgb(200, 238, 241)')
  }).on('mouseout', function (d) {
    self._update_circle(d3.select(this));
  })
    .call(self.drag);

  g.append('svg:text')
    .classed('trial-id', true)
    .attr('font-family', 'sans-serif')
    .attr('font-size', '12px')
    .attr('pointer-events', 'none')
    .attr('x', 0)
    .attr('y', 4)
    .attr('text-anchor', 'middle')
    .attr('font-weight', 'bold')
    .attr("transform", function (d) {
      return "translate(" + d.x + "," + d.y + ")";
    }).text(function (d) { return d.title; });

  // remove old nodes
  self.circle.exit().remove();
};

HistoryGraph.prototype.set_use_tooltip = function (use) {
  var self = this;
  self.use_tooltip = use;
};

HistoryGraph.prototype.update_window = function () {
  var self = this,
    size = self.custom_size();
  self.width = size[0];
  self.height = size[1];
  this.svg
    .attr("width", size[0])
    .attr("height", size[1]);
};

HistoryGraph.prototype.download = function(name) {
  try {
      var isFileSaverSupported = !!new Blob();
  } catch (e) {
      alert("blob not supported");
  }
  name = (name === undefined)? "history.svg" : name;
  var bbox = this.svg_g[0][0].getBBox();
  var width = this.svg.attr("width"), height = this.svg.attr("height");
  this.translate = this.drag_svg.translate();

  this.svg_g.attr("transform", "translate(" + (- bbox.x + 5) +", " +(-bbox.y + 5) +")");
  this.hint_element.remove();
  var html = this.svg
      .attr("title", "Trial")
      .attr("version", 1.1)
      .attr("width", bbox.width + 10)
      .attr("height", bbox.height + 10)
      .attr("xmlns", "http://www.w3.org/2000/svg")
      .node().parentNode.innerHTML;
  html = '<svg xmlns:xlink="http://www.w3.org/1999/xlink" ' + html.slice(4);
  this.svg
    .attr("width", width)
    .attr("height", height);
  this.svg_g.attr("transform", "translate(" + this.translate[0] +", " +this.translate[1] +")");
  this.drag_svg.event(this.svg);
  var blob = new Blob([html], {type: "image/svg+xml"});
  saveAs(blob, name);
  this._tick()
}

HistoryGraph.prototype.set_node_font_size = function(size) {
  this.svg.selectAll("text.trial-id")
    .attr('y', size / 3)
    .attr("font-size", size);
}


function now_history_graph(div_selector, graph_id, data, width, height, tooltip_selector, options) {
  $(div_selector).html('');
  var svg = d3.select(div_selector)
    .append('svg')
    .attr("width", width)
    .attr("height", height);

  var history_graph = new HistoryGraph(graph_id, svg, options);
  history_graph.set_use_tooltip(d3.select(tooltip_selector).property("checked"));
  var nodes = history_graph.load(data, width);
  return {
    'graph': history_graph,
    'nodes': nodes
  };
}