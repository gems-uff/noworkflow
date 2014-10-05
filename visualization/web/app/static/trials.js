var width, height,
    filter_width = 200;
var history_graph, trial_svg, 
    selected_graph = "independent",
    current_nid = 0;

var docEl = document.documentElement,
    bodyEl = document.getElementsByTagName('body')[0],
    colors = d3.scale.category10();


// Resizing

function calculate_window_size() {
    width = window.innerWidth || docEl.clientWidth || bodyEl.clientWidth;
    height =  window.innerHeight|| docEl.clientHeight|| bodyEl.clientHeight;
};
calculate_window_size();

function resize_trial() {
    trial_svg.attr("height", height).attr("width", width);
}

window.onresize = function() {
    calculate_window_size();
    history_graph.updateWindow();
    resize_trial();
};


// Graphs
function load_graph(nid, url) {
    $.ajax({
        type: "GET",
        contentType: "application/json; charset=utf-8",
        url: 'trials/' + nid + '/' + url,
        dataType: 'json',
        async: true,
        data: {}, 
        success: function (data) {
            $('#graph').html('');

            trial_svg = d3.select('#graph')
                .append('svg')
                .attr("width", 500)
                .attr("height", 500);
            trial_graph(trial_svg, data.nodes, data.edges,
                        data.min_duration, data.max_duration);
            console.log(data.min_duration, data.max_duration);
            
            resize_trial();
           
        },
        error: function (result, status) {
        }
    });
}

function load_dependencies(nid) {
    $.ajax({
        type: "GET",
        contentType: "application/json; charset=utf-8",
        url: 'trials/' + nid + '/dependencies',
        dataType: 'json',
        async: true,
        data: {}, 
        success: function (data) {
            if (data.all.length > 0) {
                $('#side-internal').append(
                    '<div id="modules">' +
                        '<div class="fold">' +
                            '<i class="fa fa-minus"></i><span> Modules </span>' +
                            '<a href="trials/'+nid+'/all_modules" title="Show all" class="show_all"><i class="fa fa-binoculars"></i></a>' +
                        '</div>' +
                        '<div class="foldable">' +
                            '<ul class="mod-list">'+
                            '</ul>'+
                        '</div>' +
                    '</div>'
                );    
                //data.local = data.all;
                for (i = 0; i < data.local.length; i++) {
                    $('#side-internal #modules ul').append(
                        '<li>' + 
                            '<div class="name">' + data.local[i].name + '</div>' + 
                            '<div class="version">' + (data.local[i].version == null ? "" : data.local[i].version) + '</div>' + 
                            '<div class="clear"></div>' +
                            '<div class="hash" title="'+data.local[i].path  +'">' + data.local[i].code_hash + '</div>' + 
                        '</li>'
                    );  
                }
               
            }
            
        },
        error: function (result, status) {
        }
    });
}

function load_environment(nid) {
    $.ajax({
        type: "GET",
        contentType: "application/json; charset=utf-8",
        url: 'trials/' + nid + '/environment',
        dataType: 'json',
        async: true,
        data: {}, 
        success: function (data) {
            function li(key) {
                if (data.env[key]) {
                    return '<li>' +
                        '<span class="key"> '+key+' </span>' +
                        '<span class="equal"> = </span>' +
                        '<span class="value"> '+data.env[key] +' </span>' +
                    '</li>';
                }
                return ''
            }

            $('#side-internal').append(
                '<div id="environment">' +
                    '<div class="fold">' +
                        '<i class="fa fa-minus"></i><span> Environment </span>' +
                        '<a href="trials/'+nid+'/all_environment" title="Show all" class="show_all"><i class="fa fa-binoculars"></i></a>' +
                    '</div>' +
                    '<div class="foldable">' +
                        '<ul class="env-list">'+
                            li('PYTHON_IMPLEMENTATION') +
                            li('PYTHON_VERSION') +
                            li('OS_NAME') +
                            li('OS_RELEASE') +
                            li('OS_VERSION') +
                            li('OS_USER') +
                            li('PWD') +
                            li('PID') +
                            li('HOSTNAME') +
                            li('ARCH') +
                            li('PROCESSOR') +
                        '</ul>'+
                    '</div>' +
                '</div>'
            );    
               
            
            
        },
        error: function (result, status) {
        }
    });
}

function select_node(n){

    $('#side-internal').html(
        '<div id="main">'+
            '<h1>Trial ' + n.title + '</h1>'+
            '<h3 class="hash">' + n.info.code_hash + '</h1>'+
            '<span class="attr"><span class="desc">Script: </span><span class="script">' + n.info.script + '</span></span>' +
            '<span class="attr"><span class="desc">Start: </span><span class="start">' + n.info.start + '</span></span>' +
            '<span class="attr"><span class="desc">Finish: </span><span class="finish">' + n.info.finish + '</span></span>' +
            (n.info.arguments ? ('<span class="attr"><span class="desc">Arguments: </span><span class="arguments">' + n.info.arguments + '</span></span>') : "") +
        '</div>'
    );
    current_nid = n.title;
    load_graph(current_nid, selected_graph);
    load_dependencies(current_nid);
    load_environment(current_nid);
}



function reload() {
    $.ajax({
        type: "GET",
        contentType: "application/json; charset=utf-8",
        url: 'trials',
        dataType: 'json',
        data: {
            'script': $("select[name='script']").val(),
            'execution': $("select[name='execution']").val()   
        },
        async: true,
        success: function (data) {
            var nodes = [];
            var edges = [];
            w = width - filter_width;
            var id = 0;
            for (var i = data.nodes.length - 1; i >= 0; i--) {
                nodes.push({id: id, x:(w-30)-(60*id), y: 30, title: data.nodes[i].id, info: data.nodes[i]});        
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
                select_node: select_node
            });

            history_graph.restart();
            history_graph.select_node(nodes[0]);
        },
        error: function (result) {

        }
    });
}
reload();

$('#reload').click(reload);


// Splitters

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

$('#top').split({
    orientation: 'vertical', limit: 20,
    position: filter_width + "px",
    onDrag: function(){
        history_graph.updateWindow();
        
    }

});


// Graph type
$( "[name='graphtype']" ).change(function() {
    selected_graph = $(this).attr('value');
    load_graph(current_nid, selected_graph);
});

$('#side-internal').on('click', '.fold', function(e){
    $(this.nextSibling).slideToggle(200);
    $(this.firstChild).toggleClass("fa-plus");
    $(this.firstChild).toggleClass("fa-minus");
});