var colors = d3.scale.category10();

var docEl = document.documentElement,
    bodyEl = document.getElementsByTagName('body')[0];

var width = window.innerWidth || docEl.clientWidth || bodyEl.clientWidth,
    height =  window.innerHeight|| docEl.clientHeight|| bodyEl.clientHeight;

var trial_svg;

function select_node(n){
    $.ajax({
        type: "GET",
        contentType: "application/json; charset=utf-8",
        url: 'trials/' + n.title,
        dataType: 'json',
        async: true,
        data: {}, 
        success: function (data) {
            var nodes = [];
            var edges = [];
            var id = 0;
            for (var i = 0; i < data.nodes.length; i++) {
                node = {
                    name: data.nodes[i].name,
                    index: data.nodes[i].index,
                    mean: data.nodes[i].mean
                };
                nodes.push(node)
            }
            for (var i = 0; i < data.edges.length; i++) {
                var edge = data.edges[i];
                edge.source = nodes[edge.source];
                edge.target = nodes[edge.target];
                
                edges.push(edge);        
            }
            $('#graph').html('');

            $('#side-internal').html(
                '<div id="main">'+
                    '<h1>Trial ' + n.title + '</h1>'+
                    '<h3>' + n.info.code_hash + '</h1>'+
                    '<span class="attr"><span class="desc">Script: </span><span class="script">' + n.info.script + '</span></span>' +
                    '<span class="attr"><span class="desc">Start: </span><span class="start">' + n.info.start + '</span></span>' +
                    '<span class="attr"><span class="desc">Finish: </span><span class="finish">' + n.info.finish + '</span></span>' +
                    (n.info.arguments ? ('<span class="attr"><span class="desc">Arguments: </span><span class="arguments">' + n.info.arguments + '</span></span>') : "") +
                '</div>'
            );
            trial_svg = d3.select('#graph')
                .append('svg')
                .attr("width", 300)
                .attr("height", 300);
            trial_graph(trial_svg, nodes, edges,
                        data.min_duration, data.max_duration);
            
            resize_trial();
           
        },
        error: function (result, status) {
        }
    })
}

var history_graph;

$.ajax({
    type: "GET",
    contentType: "application/json; charset=utf-8",
    url: 'trials',
    dataType: 'json',
    async: true,
    success: function (data) {
        var nodes = [];
        var edges = [];
        var id = 0;
        for (var i = data.nodes.length - 1; i >= 0; i--) {
            nodes.push({id: id, x:(width-30)-(60*id), y: 30, title: data.nodes[i].id, info: data.nodes[i]});        
            id += 1;
        }
        for (var i = 0; i < data.edges.length; i++) {
            var edge = data.edges[i];
            edge.source = nodes[edge.source];
            edge.target = nodes[edge.target];
            
            edges.push(edge);        
        }
        $('#history').html('');
        var svg = d3.select('#history')
            .append('svg')
            .attr("width", width)
            .attr("height", HistoryGraph.consts.height);

        history_graph = new HistoryGraph(svg, nodes, edges, {
            select_node: select_node,
            unselect_node: function(n) {
                console.log("un"); 
            }

        });

        history_graph.restart();
        history_graph.select_node(nodes[0]);
    },
    error: function (result) {

    }
});


function resize_trial() {
    // console.log(trial_svg[0].getBoundingClientRect());
    var docEl = document.documentElement,
        bodyEl = document.getElementsByTagName('body')[0];
    var x = window.innerWidth || docEl.clientWidth || bodyEl.clientWidth;
    var y = window.innerHeight || docEl.clientHeight || bodyEl.clientHeight;
    trial_svg.attr("height", y).attr("width", x);
}

window.onresize = function() {
    history_graph.updateWindow();
    resize_trial();
};

var horizontal = $('#splitter').split({
    orientation: 'horizontal', limit: 20,
    position: HistoryGraph.consts.height + 3,
    onDrag: function(){
        history_graph.set_height($('#history').height());
        resize_trial();
    }
});

$('#show').split({
    orientation: 'vertical', limit: 20,
    position: "60%",
    onDrag: function(){
        resize_trial();
    }

});