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

    force_links = force.links();
    
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
        .data(force_links)
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
        .data(force_links)
      .enter().append("text")
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



    var node = svg_g.selectAll(".node")
        .data(force.nodes())
      .enter().append("g")
        .attr("id", function(d) { 
            return "node-"+d.index;
        })
        .attr("class", "node")
        .call(force.drag);

    node.append("circle")
        .attr("r", 5)
        .attr("data-clicked", "0")
        
        .style('fill', function(d) {
            proportion = Math.round(510 * (d.mean - min_duration) / (max_duration - min_duration));
            return d3.rgb(Math.min(255, proportion), Math.min(255, 510 - proportion), 0);
        }).on("click", toggle_nodes);

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


    // Add links to nodes
    force_links.forEach(function(link, i) {
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

    // Toggle nodes
    function toggle_nodes(node, i){
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
    }



}

