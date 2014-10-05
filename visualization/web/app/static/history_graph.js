
function HistoryGraph(svg, nodes, edges, options) {
    var self = this;

    self.custom_select_node = options.select_node || function() {};

    self.height = HistoryGraph.consts.height

    self.nodes = nodes || [];
    self.edges = edges || [];

    self.state = {
        selected_node: null,
        mousedown_node: null,
        just_scale: false
    };

    var defs = svg.append('svg:defs');
    defs.append('svg:marker')
        .attr('id', 'end-arrow')
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 6)
        .attr('markerWidth', 3)
        .attr('markerHeight', 3)
        .attr('orient', 'auto')
        .append('svg:path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', '#000');

    svg.append('svg:defs').append('svg:marker')
        .attr('id', 'start-arrow')
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 4)
        .attr('markerWidth', 3)
        .attr('markerHeight', 3)
        .attr('orient', 'auto')
        .append('svg:path')
        .attr('d', 'M10,-5L0,0L10,5')
        .attr('fill', '#000');

    self.svg = svg;
    self.svg_g = svg.append("g")
        .classed(HistoryGraph.consts.graph_class, true);
    var svg_g = self.svg_g;

    self.path = svg_g.append('svg:g').selectAll('path'),
    self.circle = svg_g.append('svg:g').selectAll('g');

    // Mouse events
    svg.on("mouseup", function(d){
        self.svg_mouseup.call(self, d);
    });

    // Drag and Zoom
    self.drag = d3.behavior.drag();
    var drag_svg = d3.behavior.zoom()
      .on("zoom", function(){
        self.zoomed.call(self);
      })
      .on("zoomstart", function(){
        d3.select('body').style("cursor", "move");
      })
      .on("zoomend", function(){
        d3.select('body').style("cursor", "auto");
      });
    svg.call(drag_svg).on("dblclick.zoom", null);

}


HistoryGraph.prototype.set_height = function(height){
    this.height = height;
    this.updateWindow(this.svg)
};


HistoryGraph.consts =  {
    selected_class: "selected",
    graph_class: "graph",
    move_x: 20,
    move_y: 25,
    move_y2: 10,
    radius: 20,
    height: 100,
};

HistoryGraph.prototype.unselect_node = function() {
    var self = this,
        state = self.state;
    self.circle.filter(function(cd){
        return cd.id === state.selected_node.id;
    }).select('circle')
    .classed(HistoryGraph.consts.selected_class, false);

    state.selected_node = null;
};

HistoryGraph.prototype.node_mousedown = function(d3node, d){
    var self = this,
        state = self.state;
    d3.event.stopPropagation();
    state.mousedown_node = d;
};

HistoryGraph.prototype.select_node = function(node) {
    this.state.selected_node = node;
    this.custom_select_node(node)
    d3.select($('#history text.id:contains("'+node.title+'")')
        .siblings()[0]).classed('selected', true)
};

HistoryGraph.prototype.node_mouseup = function(d3node, d){
    var self = this,
        state = self.state,
        consts = self.consts;

    var mousedown_node = state.mousedown_node;
    
    if (!mousedown_node) return;

    if (state.just_scale) {
        // dragged, not clicked
        state.just_scale = false;
    } else{
        if (state.selected_node) {
            self.unselect_node();
        }

        d3node.classed(HistoryGraph.consts.selected_class, true);
        state.selected_node = d;
        self.custom_select_node(d);
        
    }
      
    
    state.mousedown_node = null;
    return;
}; 


// mouseup on main svg
HistoryGraph.prototype.svg_mouseup = function(){
    var state = this.state;
    if (state.just_scale) {
      // dragged not clicked
      state.just_scale = false;
    } 
};


HistoryGraph.prototype.update_path = function(path){
    var self = this,
        consts = HistoryGraph.consts,
        state = this.state;

    return path.attr("d", function(d){
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

        result = 'M' + sourceX + ',' + sourceY;
        result += 'C' + (sourceX - consts.move_x/2) + ',' + (sourceY);
        result += ',' + (sourceX - consts.move_x/2) + ',' + (sourceY + 3*step/4);
        result += ',' + (sourceX - consts.move_x) + ',' + (sourceY + step);

        result += 'L' + (sourceX - consts.move_x) + ',' + (sourceY + step);
        result += ',' + (targetX + consts.move_x) + ',' + (sourceY + step);
        
        result += 'C' + (targetX + consts.move_x/2) + ',' + (sourceY + 3*step/4);
        result += ',' + (targetX + consts.move_x/2) + ',' + (sourceY);
        result += ',' + targetX + ',' + targetY;

        return result;
    }).style('marker-start', function(d) { 
        return d.left ? 'url(#start-arrow)' : ''; 
    }).style('marker-end', function(d) { 
        return d.right ? 'url(#end-arrow)' : ''; 
    }).style('stroke', function(d) { 
        return d3.rgb(colors(d.level)).darker().toString(); 
    });
}


HistoryGraph.prototype.update_circle = function(circle) {
    var self = this,
        consts = HistoryGraph.consts,
        state = this.state;
    
    return circle.attr("transform", function(d) {
        return "translate(" + d.x + "," + d.y + ")";
    }).classed('reflexive', function(d) {
        return d.reflexive; 
    });
}



// call to propagate changes to graph
HistoryGraph.prototype.restart = function(){
    
    var self = this,
        consts = HistoryGraph.consts,
        state = this.state;
    
    // path (link) group
    self.path = self.path.data(self.edges)

    // update existing links
    self.update_path(self.path);

    // add new paths
    path = self.path.enter().append("svg:path")
        .attr('class', 'link')
    
    self.update_path(path);
      
    // remove old links
    self.path.exit().remove();
    
    // circle (node) group
    self.circle = self.circle.data(self.nodes, function(d) { return d.id; });
    

    self.update_circle(self.circle.selectAll('circle'));
        
    // add new nodes
    var g = self.circle.enter().append("svg:g");

    self.update_circle(g.append('svg:circle')
            .classed(consts.cicle_class, true)
            .attr('class', 'node')
            .attr('r', consts.radius)
        ).on('mousedown', function(d) {
            self.node_mousedown.call(self, d3.select(this), d);      
        }).on('mouseup', function(d) {
            self.node_mouseup.call(self, d3.select(this), d);     
        }).call(self.drag);
   
    g.append('svg:text')
        .attr('x', 0)
        .attr('y', 4)
        .attr('class', 'id')
        .attr("transform", function(d) {
            return "translate(" + d.x + "," + d.y + ")";
        })
        .text(function(d) { return d.title; })

    // remove old nodes
    self.circle.exit().remove();
};

HistoryGraph.prototype.zoomed = function(){
    this.state.just_scale = true;
    d3.select("." + HistoryGraph.consts.graph_class)
      .attr("transform", "translate(" + d3.event.translate + ") scale(" + d3.event.scale + ")"); 
};

HistoryGraph.prototype.updateWindow = function(){
    var docEl = document.documentElement,
        bodyEl = document.getElementsByTagName('body')[0];
    var x = window.innerWidth || docEl.clientWidth || bodyEl.clientWidth;
    this.svg.attr("width", x-$('#top .filter').width()).attr("height", this.height);
};


 