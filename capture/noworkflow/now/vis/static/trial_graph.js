/*global d3 */
function TrialGraph(id, svg, options) {
  var self = this;
  // Configure Graph

  self.state_mousedown_node = false;
  self.translate = false;
  self.use_tooltip = false;
  self.hide_fullname = false;
  self.two_color_scale = false;
  self.graph_id = id;

  self.custom_size = options.custom_size || function () {
    return [TrialGraph.consts.width, TrialGraph.consts.height];
  };
  self.custom_mouseover = options.custom_mouseover || function () { return null; };
  self.custom_mouseout = options.custom_mouseout || function () { return null; };
  self.hint_message = options.hint_message || "Double-click to toggle nodes";
  self.hint_y = options.hint_y || 45;
  self.hint_class = options.hint_class || "";

  self.nodes = [];
  self.edges = [];

  self.link_map = {};
  self.label_map = {};

  var size = self.custom_size();
  self.width = size[0];
  self.height = size[1];

  self.svg = svg;
  self.diagonal = d3.svg.diagonal()
      .projection(function(d){ return [d.x, d.y]; });



  // Define functions
  self._label_distance = function (d) {
    var dx = (d.source.x - d.target.x);
    var dy = (d.source.y - d.target.y);
    console.log("aqui", d, d.source.x, d.target.x, Math.sqrt(dx*dx + dy*dy) / 2);
    return Math.sqrt(dx*dx + dy*dy) / 2;
  };

  self._path_function = function (d, i, reverse) {

    if (reverse) {
      return self.diagonal(d);
    }

    var x1 = d.source.x,
      y1 = d.source.y,
      x2 = d.target.x,
      y2 = d.target.y,
      dx = x2 - x1,
      dy = y2 - y1,
      theta = Math.atan2(dy, dx),
      phi = Math.atan2(dx, dy),
      r = TrialGraph.consts.radius + TrialGraph.consts.stroke_width,
      sin_theta = r * Math.sin(theta),
      cos_theta = r * Math.cos(theta),
      sin_phi = r * Math.sin(phi),
      cos_phi = r * Math.cos(phi),
      m1 = (y2 > y1) ? 1 : -1,
      m2 = (x2 > x1) ? -1 : 1,
      dr = Math.sqrt(dx * dx + dy * dy),
      drx = dr,
      dry = dr,
      rotation = 0,
      large_arc = 0,
      sweep = 1;

    if (dx === 0 && dy === 0 && d.type !== 'initial' && !reverse) {
      rotation = -45;
      large_arc = 1;
      drx = 15;
      dry = 20;
      x2 = x2 + 1;
      y2 = y2 + 1;
    } else if (d.type === 'initial') {
      x2 -= r / 2.0;
      y2 -= r / 2.0;
      x1 = x2 - 20;
      y1 = y2 - 20;
      large_arc = 1;
      sweep = 0;
    } else {
   /*
    //  x1 += m1 * sin_theta;
    //  y1 += m1 * cos_theta;
      if (dx !== 0) {
        x2 += m2 * cos_phi;
      }
      if (dy !== 0) {
        y2 += m2 * sin_phi;
      }

      return d3.svg.line()
      diag = d3.svg.diagonal()
        //.projection(function(d){ return [d.x, d.y]; })
        .source({"x": x1, "y": y1})
        .target({"x": x2, "y": y2});*/
      return "M" + x1 + "," + y1 + "L" + x2 + "," + y2;

    }

    return "M" + x1 + "," + y1 +
      "A" + drx + "," + dry +
      " " + rotation + "," + large_arc + "," + sweep +
      " " + x2 + "," + y2;
  }

  self._graph_id = function () {
    return ("trial-graph-"
      + self.graph_id);
  };

  self._node_name = function (d) {
    if (self.hide_fullname) {
      var s = d.name.split(/[\/\\]/);
      return s[s.length - 1];
    }
    return d.name;
  };

  self._update_node_text = function () {
    d3.selectAll("#" + self._graph_id() + " g.node text").text(
      self._node_name);
  };

  self._prepare_nodes_and_edges = function (nodes, edges) {
    nodes.forEach(function(node){
      node.children = [];
    });
    self.root = 0;
    nodes.forEach(function(node){
      node.x0 = 0;
      node.y0 = 0;
      node.px = 0;
      node.py = 0;
      node.visible = true;
      node.links = {};
      if (node.caller_id == null) {
        self.root = node.index;
      } else {
        nodes[node.caller_id].children.push(node);
      }
    });
    nodes.forEach(function(node){
      node.children.reverse();
    });
    self.nodes = nodes;
    edges.forEach(function (e) {
      if (typeof e.source == "number") e.source = self.nodes[e.source];
      if (typeof e.target == "number") e.target = self.nodes[e.target];
    });
    self.edges = edges;
  };

  self._calculate_color = function (node) {
    if (self.two_color_scale) {
      proportion = Math.round(510 * (node.duration - self.min_duration[node.trial_id]) / self.total_duration[node.trial_id]);
      return d3.rgb(Math.min(255, proportion), Math.min(255, 510 - proportion), 0);
    } else {
      proportion = Math.round(255 * (1.0 - (node.duration / self.total_duration[node.trial_id])));
      return d3.rgb(255, proportion, proportion, 0);
    }
  };

  self._node_id = function (node) {
    if (!node.ref) {
      node.ref = ("node-"
        + self.graph_id
        + "-" + node.index);
    }
    return node.ref;
  };

  self._link_id = function (link) {
    if (!link.ref) {
      link.ref = ("link-"
        + self._node_id(link.source)
        + "-"
        + link.type
        + "-"
        + self._node_id(link.target));
    }
    return link.ref;
  };

  self._node_click = function (d) {
    // Toggle children on click.
    if (d.children) {
      d._children = d.children;
      d.children = null;
    } else {
      d.children = d._children;
      d._children = null;
    }
    self.restart(d);
  };

  self._show_tooltip = function (d) {
    self.div.classed("hidden", false);
    self.div.transition()
      .duration(200)
      .style("opacity", 0.9);
    self.div.html(d.info)
      .style("left", (d3.event.pageX - 3) + "px")
      .style("top", (d3.event.pageY - 28) + "px");
  };

  self._close_tooltip = function () {
    self.div.transition()
      .duration(500)
      .style("opacity", 0);
    self.div.classed("hidden", true);
  };

  self._zoomed = function () {
    self._close_tooltip();
    if (!self.state_mousedown_node) {
      d3.select("#" + self._graph_id())
        .attr("transform",
            "translate(" + d3.event.translate + ") scale(" + d3.event.scale + ")");
    }
  };

  self.load = function (data, t1, t2) {
    self.init(data.nodes, data.edges, data.min_duration, data.max_duration, t1, t2);
    self.update_window();
  };

  self.init = function (nodes, edges, min_duration, max_duration, t1, t2) {
    self.t1 = t1;
    self.t2 = t2;
    self.min_duration = min_duration;
    self.max_duration = max_duration;
    self.total_duration = {};
    self.total_duration[t1] = max_duration[t1] - min_duration[t1];
    self.total_duration[t2] = max_duration[t2] - min_duration[t2];

    self._prepare_nodes_and_edges(nodes, edges);

    size = self.custom_size();
    size[0] -= TrialGraph.consts.margin_left + TrialGraph.consts.margin_right;
    size[1] -= TrialGraph.consts.margin_top + TrialGraph.consts.margin_bottom

    self.tree = d3.layout.tree()
      .size(size);

    self.restart();
  };

  self.restart = function (source) {
    if (source === undefined) {
      source = self.nodes[self.root];
    }
    // Compute the new tree layout
    var nodes = self.tree.nodes(self.nodes[self.root]);
    console.log(nodes, nodes.children);
    // Normalize for fixed-depth
    nodes.forEach(function (d) { d.y = d.depth * 100; });

    // Declare the nodes
    var node = self.svg_g.selectAll("g.node")
      .data(nodes, self._node_id);

    // Entrer the nodes
    var node_enter = node.enter().append("g")
      .attr("class", "node")
      .attr("transform", function (d) {
        d.visible = true;
        return "translate(" + source.x0 + "," + source.y0 + ")";
      })
      .classed("nbefore", function (d) {
        return (d.node && d.node.trial_id == self.t1 && self.t1 !== self.t2);
      })
      .classed("nafter", function (d) {
        return (d.node && d.node.trial_id == self.t2 && self.t1 !== self.t2);
      })
      .call(self.drag)
      .on("dblclick", self._node_click)
      .on("mousedown", function () {
        self.translate = self.drag_svg.translate();
        self.state_mousedown_node = true;
        self._close_tooltip();
      })
      .on("mouseup", function () {
        if (self.translate) {
          self.drag_svg.translate(self.translate);
          self.translate = false;
        }
        self.state_mousedown_node = false;
      })
      .on("mouseover", function (d) {
        var show_tooltip = !self.state_mousedown_node && self.use_tooltip,
            name;
        if (d.node) {
          name = 'node';
        } else {
          name = (d3.mouse(this)[0] < 0) ? 'node1' : 'node2';
        }
        if (show_tooltip) {
          self._close_tooltip();
          self._show_tooltip(d[name]);
        }
        self.custom_mouseover(d, name, show_tooltip);
      })
      .on('mouseout', function (d) {
        self.custom_mouseout(d);
      });

    node_enter.append("circle")
      .attr("r", TrialGraph.consts.radius)
      .attr("data-clicked", "0")
      .attr("stroke", function (d) {
        return d.children || d._children ? "blue" : "#000000"; 
      })
      .style("fill", function (d) {
        if (d.node) {
          return self._calculate_color(d.node);
        }
        var grad = self.svg.append("svg:defs")
          .append("linearGradient")
          .attr("id", "grad-" + self.graph_id + "-" + d.index)
          .attr("x1", "100%")
          .attr("x2", "0%")
          .attr("y1", "0%")
          .attr("y2", "0%");
        grad.append("stop")
          .attr("offset", "50%")
          .style("stop-color", self._calculate_color(d.node2));
        grad.append("stop")
          .attr("offset", "50%")
          .style("stop-color", self._calculate_color(d.node1));

        return "url(#grad-" + self.graph_id + "-" + d.index + ")";
      });

    node_enter.append("text")
      .attr("y", function (d) {
          return d.children || d._children ? -18 : 18;
      })
      .attr("dy", ".35em")
      .attr("text-anchor", "middle")
      .text(self._node_name)
      .style("fill-opacity", 1e-6);

    // Transition nodest to their new position
    var node_update = node
     // .transition()
     // .duration(TrialGraph.consts.duration)
      .attr("transform", function (d) {
        return "translate(" + d.x + "," + d.y + ")";
      });

    node_update.select("circle")
      .attr("r", TrialGraph.consts.radius)
      .attr("stroke", function (d) {
        return d._children ? "blue" : "#000000";
      });

    node_update.select("text")
      .style("fill-opacity", 1);

    // Transition exiting nodes to the parent's new position.
    var node_exit = node.exit()
      //.transition()
      //.duration(TrialGraph.consts.duration)
      .attr("transform", function (d) {
        d.visible = false;
        return "translate(" + source.x + "," + source.y + ")";
      })
      .remove();

    node_exit.select("circle")
      .attr("r", 1e-6);
    node_exit.select("text")
      .style("fill-opacity", 1e-6);


    var links = self.edges.filter(function(x) {
      return x.source.visible && x.target.visible;
    });//self.tree.links(nodes);
    // Update links
    // Declare links
    var link = self.link_g.selectAll("path.link")
      .data(links, self._link_id)

    // Enter the links
    link.enter().insert("path", "g")
      .attr("class", "link")
      .attr("id", self._link_id)
      .attr("marker-end", "")
      .classed('call-arrow', function (d) {
        return d.type === 'call';
      }).classed('return-arrow', function (d) {
        return d.type === 'return';
      }).classed('sequence-arrow', function (d) {
        return d.type === 'sequence';
      }).classed('initial-arrow', function (d) {
        return d.type === 'initial';
      });
    // Transition links to their new position.
    link
      //.transition()
      //.duration(TrialGraph.consts.duration)
      .attr("marker-end", function (d) {
        if (!d.trial) {
          return "url(#end)";
        }
        if (d.trial === 1) {
          return "url(#endbefore)";
        }
        if (d.trial === 2) {
          return "url(#endafter)";
        }
        return "";
      })
      .attr("d", function(d) {
        var link_id = self._link_id(d);
        self.link_map[link_id] = this;
        d.source.links[link_id] = true;
        d.target.links[link_id] = true;
        return self._path_function(d);
      });

    // Transition exiting nodes to the parent's new position
    link.exit()
      .attr("d", function(d) {
        var link_id = self._link_id(d);
        delete d.source.links[link_id];
        delete d.target.links[link_id];
        return self._path_function(d);
      })
      .remove();

    // Create link labels
    var link_labels = self.svg_g.selectAll(".label_text")
      .data(links, self._link_id);

    // Enter the labels
    link_labels.enter().append("text")
      .attr("class", "label_text")
      .attr("dx", self._label_distance)
      .attr("dy", -3)
      .attr("id", function (d, i) {
        self.label_map[self._link_id(d)] = this;
        return "pathlabel-" + self.graph_id + "-" + i;
      })
      .append("textPath")
      .attr("xlink:href", function (d, i) {
        return "#" + self._link_id(d);
      })
      .text(function (d) {
        return (d.type === 'initial') ? '' : d.count;
      });

    // Exit labels
    link_labels.exit().remove();

    // Stash the old positions for transition.
    nodes.forEach(function (d) {
        d.x0 = d.x;
        d.y0 = d.y;
    });

    // Add links to nodes for navigation

    links.forEach(function (link, i) {
      var source = link.source,
      target = link.target;

      source.arrival_links = source.arrival_links || [];
      source.sequence_links = source.sequence_links || [];
      source.call_links = source.call_links || [];
      source.return_links = source.return_links || [];
      target.arrival_links = target.arrival_links || [];
      target.sequence_links = target.sequence_links || [];
      target.call_links = target.call_links || [];
      target.return_links = target.return_links || [];


      if (link.type === 'sequence') { source.sequence_links.push([i, target]); }
      if (link.type === 'call') { source.call_links.push([i, target]); }
      if (link.type === 'return') { source.return_links.push([i, target]); }
      target.arrival_links.push([i, source, link.type]);
    })
  };

  self.set_use_tooltip = function (use) {
    self.use_tooltip = use;
    return;
  };

  self.set_hide_fullname = function (hide) {
    self.hide_fullname = hide;
    self._update_node_text();
  };

  self.update_window = function () {
    size = self.custom_size();
    self.svg
      .attr("width", size[0])
      .attr("height", size[1]);
  };

  // Create Tooltip, hint, markers, selections

  self.div = d3.select("body").append("div")
    .attr("class", "now-tooltip now-trial-tooltip")
    .style("opacity", 0)
    .on("mouseout", function () {
      self._close_tooltip();
    });

  svg.append("text")
    .text(self.hint_message)
    .attr("dx", 5)
    .attr("dy",  self.hint_y)
    .classed(self.hint_class, true);

  self._create_marker(svg, 'end', 'enormal');
  self._create_marker(svg, 'endbefore', 'ebefore');
  self._create_marker(svg, 'endafter', 'eafter');

  var svg_g = svg.append("g")
    .attr("id", self._graph_id())
    .classed(TrialGraph.consts.graph_class, true)
    .attr("transform", "translate(" + TrialGraph.consts.margin_left + ","
      + TrialGraph.consts.margin_top + ")");

  self.svg_g = svg_g;

  self.link_g = svg_g.append("svg:g")
  self.label_selection = svg_g.selectAll(".label_text");

  self.drag = d3.behavior.drag()
    .on("drag", function dragmove(d, i) {
        d.px += d3.event.dx;
        d.py += d3.event.dy;
        d.x += d3.event.dx;
        d.y += d3.event.dy;
        d3.select(this).attr("transform", function (d) {
          return "translate(" + d.x + "," + d.y + ")";
        });

        d3.selectAll(Object.keys(d.links).map(function(link_id){
          return self.link_map[link_id];
        })).attr("d", self._path_function);
        d3.selectAll(Object.keys(d.links).map(function(link_id){
          return self.label_map[link_id];
        })).attr("dx", self._label_distance);
    })
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


  return self;
}

TrialGraph.consts =  {
  graph_class: "trialgraph",
  height: 400,
  width: 400,
  radius: 10.0,
  stroke_width: 2,
  marker_width: 6,
  marker_height: 6,
  duration: 750,
  margin_top: 40,
  margin_right: 20,
  margin_bottom: 20,
  margin_left: 20,
};

TrialGraph.prototype._create_marker = function (svg, name, cls) {
  svg.append("svg:defs").selectAll("marker")
    .data([name])
    .enter().append("svg:marker")
      .attr("id", String)
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 20)
      .attr("refY", 0)
      .attr("markerWidth", TrialGraph.consts.marker_width)
      .attr("markerHeight", TrialGraph.consts.marker_height)
      .attr("orient", "auto")
    .append("svg:path")
      .classed(cls, true)
      .attr("d", "M0,-5L10,0L0,5");
};


function now_trial_graph(div_selector, graph_id, trial_id_1, trial_id_2, data, width, height, tooltip_selector, hide_fullname_selector, options) {
  $(div_selector).html('');

  var trial_svg = d3.select(div_selector)
    .append('svg')
    .attr("width", width)
    .attr("height", height);
  var trial_graph = new TrialGraph(graph_id, trial_svg, options);
  trial_graph.set_use_tooltip(d3.select(tooltip_selector).property("checked"));
  trial_graph.set_hide_fullname(d3.select(hide_fullname_selector).property("checked"));
  trial_graph.load(data, trial_id_1, trial_id_2);
  return trial_graph;
}