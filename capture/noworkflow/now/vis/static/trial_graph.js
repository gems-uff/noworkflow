function TrialGraph(svg, options) {
    var self = this;

    self.state_mousedown_node = false;
    self.translate = false;

    self.custom_size = options.custom_size || function() {
        return [TrialGraph.consts.width, TrialGraph.consts.height];
    };

    self.nodes = [];
    self.edges = [];

    self.div = d3.select("body").append("div")
        .attr("class", "tooltip")
        .style("opacity", 0)
        .on("mouseout", function(){
            self._close_tooltip();
        })
    
    self.width = TrialGraph.consts.width;
    self.height = TrialGraph.consts.height;

    svg.append("text")
        .text("Ctrl-click to toggle nodes")
        .attr("dx", 5)
        .attr("dy", 45);

    svg_g = svg.append("g")
        .classed(TrialGraph.consts.graph_class, true);

    svg.append("svg:defs").selectAll("marker")
        .data(["end"])
      .enter().append("svg:marker")
        .attr("id", String)
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 15)
        .attr("refY", -1.5)
        .attr("markerWidth", 6)
        .attr("markerHeight", 6)
        .attr("orient", "auto")
      .append("svg:path")
        .attr("d", "M0,-5L10,0L0,5");

    self.svg = svg;
    self.svg_g = svg_g;

    self.path = svg_g.append("svg:g").selectAll("path");
    self.label_path = svg_g.selectAll(".label_text");
    self.node = svg_g.selectAll(".node");

    self.drag = d3.behavior.drag();
    self.drag_svg = d3.behavior.zoom()
      .on("zoom", function(){
        self._zoomed.call(self);
      })
      .on("zoomstart", function(){
        d3.select('body').style("cursor", "move");
      })
      .on("zoomend", function(){
        d3.select('body').style("cursor", "auto");
      });
    svg.call(self.drag_svg).on("dblclick.zoom", null);
};

TrialGraph.consts =  {
    graph_class: "trialgraph",
    height: 400,
    width: 400
};

TrialGraph.prototype._zoomed = function(){
    var self = this;
    self._close_tooltip();
    if (!self.state_mousedown_node) {
        d3.select(".trialgraph")
            .attr("transform", "translate(" + d3.event.translate + ") scale(" + d3.event.scale + ")"); 
    } 
};

TrialGraph.prototype._tick = function(self) {
    return function() {
        self.path.attr("d", function(d) {
            var x1 = d.source.x,
                y1 = d.source.y,
                x2 = d.target.x,
                y2 = d.target.y,
                dx = d.target.x - d.source.x,
                dy = d.target.y - d.source.y,
                dr = Math.sqrt(dx * dx + dy * dy),
                drx = dr,
                dry = dr,
                rotation = 0,
                large_arc = 0,
                sweep = 1;
            
            if (dx == 0 && dy == 0 && d.type != 'initial') {
                rotation = -45;
                large_arc = 1;
                drx = 15;
                dry = 20;
                x2 = x2 + 1;
                y2 = y2 + 1;
            } else if (d.type == 'initial') {
                x1 = x2 - 20;
                y1 = y2 - 20;
                large_arc = 1;
                sweep = 0;
            }

            return "M" + x1 + "," + y1 + 
                "A" + drx + "," + dry + 
                " " + rotation + "," + large_arc + "," + sweep + 
                " " + x2 + "," + y2;
        });

        self.node.attr("transform", function(d) { 
            return "translate(" + d.x + "," + d.y + ")"; 
        });
    }
};

TrialGraph.prototype._update_path = function(path) {
    var self = this;
    return path
        .attr("marker-end", "url(#end)")
        .classed('call-arrow', function(d) {
            return d.type == 'call';
        }).classed('return-arrow', function(d) {
            return d.type == 'return';
        }).classed('sequence-arrow', function(d) {
            return d.type == 'sequence';
        }).classed('initial-arrow', function(d) {
            return d.type == 'initial';
        });
};

TrialGraph.prototype._add_path = function(path) {
    var self = this;
    path = path.enter().append("svg:path")
        .attr("id", function(d, i) {
            return "pathId-"+i;
        })
        .attr("class", "link");

    self._update_path(path);
};

TrialGraph.prototype._add_label_path = function(label_path) {
    var self = this;
    label_path = label_path.enter().append("text")
        .attr("class", "label_text")
        .attr("dx", 20)
        .attr("dy", -3)
        .attr("id", function(d, i) {
            return "pathlabel-"+i;
        })
      .append("textPath")
        .attr("xlink:href", function(d, i){
            return "#pathId-"+i;
        })
        .text(function(d){
            return (d.type == 'initial') ? '' : d.count;
        });
};

TrialGraph.prototype._add_node = function(node) {
    var self = this;
    node = node.enter().append("g")
        .attr("id", function(d) { 
            return "node-"+d.index;
        })
        .attr("class", "node")
        .call(self.force.drag);

    node.append("circle")
        .attr("r", 5)
        .attr("data-clicked", "0")
        
        .style('fill', function(d) {
            proportion = Math.round(510 * (d.mean - self.min_duration) / self.total_duration);
            return d3.rgb(Math.min(255, proportion), Math.min(255, 510 - proportion), 0);
        }).on("click", self._toggle_nodes());

    node.append("text")
        .attr("x", 12)
        .attr("dy", ".35em")
        .text(function(d) { return d.name; });


    node.on('mousedown', function(d) {
        self.translate = self.drag_svg.translate();
        self.state_mousedown_node = true;
        self._close_tooltip();
    }).on('mouseup', function(d) {
        if (self.translate){
            self.drag_svg.translate(self.translate);   
            self.translate = false;
        }
        self.state_mousedown_node = false;
    }).on('mouseover',function(d) {
        var use_tooltip = d3.select("#showtooltips").property("checked");
        if (!self.state_mousedown_node && use_tooltip) {
            self._close_tooltip();
            self._show_tooltip(d);
        }
    
    })
    .call(self.force.drag);
};

TrialGraph.prototype._toggle_nodes = function(){
    return function(node, i){
        if (!node.call_links.length || !d3.event.ctrlKey) {
            return;
        }

        var visibility = 'visible',
            data_clicked = 0;
        if (d3.select(this).attr("data-clicked") == "1") {
            d3.select(this).attr("data-clicked", "0");
            data_clicked = 0;
            visibility = 'visible';
        } else {
            d3.select(this).attr("data-clicked", "1");
            visibility = 'hidden';   
            data_clicked = 1;
        }

        var used = {};
        used[node.index] = 1;
        var queue = [];
        node.call_links.forEach(function(n){
            queue.push(n);
            used[n[1].index] = 1;
            n[1].arrival_links.forEach(hide_path);
        })
        node.arrival_links.forEach(function(a) {
            if (a[2] == 'return') hide_path(a);
        });

        while (queue.length) {
            var ln = queue.pop(),
                l = ln[0], n = ln[1],
                node_clicked = d3.select("#node-"+n.index +' circle')
                    .attr("data-clicked");
            
            d3.select("#node-"+n.index).style('visibility', visibility);
            
            if (visibility == 'hidden' || node_clicked == data_clicked) { 
                n.call_links.forEach(add_to_queue);  
                n.arrival_links.forEach(hide_path);
            } else if (visibility != 'hidden' && node_clicked != data_clicked) {
                n.arrival_links.forEach(function(a) {
                    if (a[2] != 'return') hide_path(a);
                });
            }
            

            n.sequence_links.forEach(add_to_queue);
        }

        function hide_path(a) {
            d3.select("#pathId-"+a[0]).style('visibility', visibility);  
            d3.select("#pathlabel-"+a[0]).style('visibility', visibility);
        }

        function add_to_queue(n2) {
            if (n2[1].index != node.index && !used[n2[1].index]) {
                queue.push(n2);
                used[n2[1].index] = 1;
            }
        }
    };
};

TrialGraph.prototype._show_tooltip = function(d) {
    var self = this;
    self.div.classed("hidden", false);
    self.div.transition()
        .duration(200)
        .style("opacity", .9)
    self.div.html(d.info)
        .style("left", (d3.event.pageX - 3) + "px")
        .style("top", (d3.event.pageY - 28) + "px");
};

TrialGraph.prototype._close_tooltip = function() {
    var self = this;
    self.div.transition()
        .duration(500)
        .style("opacity", 0);
    self.div.classed("hidden", true);
};

TrialGraph.prototype.load = function(data) {
    var self = this;
    self.init(data.nodes, data.edges, data.min_duration, data.max_duration);
    self.update_window();
};

TrialGraph.prototype.init = function(nodes, edges, min_duration, max_duration) {
    var self = this;
    self.min_duration = min_duration;
    self.max_duration = max_duration;
    self.total_duration = max_duration - min_duration;
    self.force = d3.layout.force()
        .nodes(nodes)
        .links(edges)
        .size([self.width, self.height])
        .linkDistance(60)
        .charge(-300)
        .on("tick", self._tick(self))
        .start();

    self.force_links = self.force.links();
    self.restart();
};

TrialGraph.prototype.restart = function() {
    var self = this;
    self.path = self.path.data(self.force_links); // path (link) group
    self._update_path(self.path); // update existing links
    self._add_path(self.path); // add new paths    
    self.path.exit().remove(); // remove old links
    
    self.label_path = self.label_path.data(self.force_links); // label path group
    self._add_label_path(self.label_path); // add new label paths
    self.label_path.exit().remove(); // remove old labels

    self.node = self.node.data(self.force.nodes()); // circle (node) group
    self._add_node(self.node); // add new nodes
    self.node.exit().remove(); // remove olf nodes
    
    // Add links to nodes for navigation
    self.force_links.forEach(function(link, i) {
        var source = link.source, target = link.target;
        source.arrival_links || (source.arrival_links = []);
        source.sequence_links || (source.sequence_links = []);
        source.call_links || (source.call_links = []);
        source.return_links || (source.return_links = []);
        target.sequence_links || (target.sequence_links = []);
        target.call_links || (target.call_links = []);
        target.return_links || (target.return_links = []);
        

        if (link.type == 'sequence') source.sequence_links.push([i, target]);
        if (link.type == 'call') source.call_links.push([i, target]);
        if (link.type == 'return') source.return_links.push([i, target]);
        (target.arrival_links || (target.arrival_links = [])).push([i, source, link.type]);
    });
};

TrialGraph.prototype.update_window = function(){
    var self = this,
        size = self.custom_size();
    this.svg
        .attr("width", size[0])
        .attr("height", size[1]);
};
