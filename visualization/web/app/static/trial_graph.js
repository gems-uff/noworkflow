function trial_graph(svg, nodes, edges, min_duration, max_duration) {

    var width = 300;
    var height = 300;

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
        .attr("id", function(d, i) {
            return "pathId-"+i;
        })
        .attr("class", "link")
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


    var label_path = svg_g.selectAll(".label_text")
        .data(force.links())
      .enter().append("text")
        .attr("class", "label_text")
        .attr("dx", 20)
        .attr("dy", -3)
      .append("textPath")
        .attr("xlink:href", function(d, i){
            return "#pathId-"+i;
        })
        .text(function(d){
            return (d.type == 'initial') ? '' : d.count;
        });



    var node = svg_g.selectAll(".node")
        .data(force.nodes())
      .enter().append("g")
        .attr("class", "node")
        .call(force.drag);

    node.append("circle")
        .attr("r", 5)
        .style('fill', function(d) {
            proportion = Math.round(510 * (d.mean - min_duration) / (max_duration - min_duration));
            return d3.rgb(Math.min(255, proportion), Math.min(255, 510 - proportion), 0);
        });

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

        node.attr("transform", function(d) { 
            return "translate(" + d.x + "," + d.y + ")"; 
        });
    }



}

