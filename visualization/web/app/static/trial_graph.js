function trial_graph(svg, nodes, edges, options) {

    var width = options.width || 300;
    var height = options.height || 300;
    console.log(nodes);
    console.log(edges);

    var force = d3.layout.force()
        .nodes(nodes)
        .links(edges)
        .size([width, height])
        .linkDistance(60)
        .charge(-300)
        .on("tick", tick)
        .start();
    
    svg_g = svg.append("g")
        .classed('trialgraph', true);

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

    var path = svg_g.append("svg:g").selectAll("path")
        .data(force.links())
      .enter().append("svg:path")
        .attr("class", "link")
        .attr("marker-end", "url(#end)");

    var node = svg_g.selectAll(".node")
        .data(force.nodes())
      .enter().append("g")
        .attr("class", "node")
        .call(force.drag);

    node.append("circle")
        .attr("r", 5);

    node.append("text")
        .attr("x", 12)
        .attr("dy", ".35em")
        .text(function(d) { return d.name; });

    var state_mousedown_node = false;

    drag = d3.behavior.drag();
    var drag_svg = d3.behavior.zoom()
        .on("zoom", function(){
            if (!state_mousedown_node) {
                d3.select(".trialgraph")
                    .attr("transform", "translate(" + d3.event.translate + ") scale(" + d3.event.scale + ")"); 
            }
          })
          .on("zoomstart", function(){
            d3.select('body').style("cursor", "move");
          })
          .on("zoomend", function(){
            d3.select('body').style("cursor", "auto");
          });
    svg.call(drag_svg).on("dblclick.zoom", null);

    var translate = false;

    node.on('mousedown', function(d) {
        translate = drag_svg.translate();
        state_mousedown_node = true;
    }).on('mouseup', function(d) {
        if (translate){
            drag_svg.translate(translate);   
            translate = false
        }
        state_mousedown_node = false;
    }).call(force.drag);

    function tick() {
        path.attr("d", function(d) {
            var dx = d.target.x - d.source.x,
                dy = d.target.y - d.source.y,
                dr = Math.sqrt(dx * dx + dy * dy);
            return "M" + 
                d.source.x + "," + 
                d.source.y + "A" + 
                dr + "," + dr + " 0 0,1 " + 
                d.target.x + "," + 
                d.target.y;
        });

        node.attr("transform", function(d) { 
            return "translate(" + d.x + "," + d.y + ")"; 
        });
    }



}

