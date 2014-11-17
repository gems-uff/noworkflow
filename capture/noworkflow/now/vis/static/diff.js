var width, height,
	t1, t2,
	trial_graph,
	selected_graph = "independent",

t1 = $("#trial1").text();
t2 = $("#trial2").text();

// Resizing
function calculate_window_size() {
    width = window.innerWidth || docEl.clientWidth || bodyEl.clientWidth;
    height =  window.innerHeight|| docEl.clientHeight|| bodyEl.clientHeight;
};
calculate_window_size();

window.onresize = function() {
    calculate_window_size();
    trial_graph.update_window();
};

// Graphs
function load_graph(t1, t2, url) {
    $.ajax({
        type: "GET",
        contentType: "application/json; charset=utf-8",
        url: '/diff/'+t1+'/'+t2+'/'+url,
        dataType: 'json',
        async: true,
        data: {}, 
        success: function (data) {
            $('#graph').html('');

            var trial_svg = d3.select('#graph')
                .append('svg')
                .attr("width", 500)
                .attr("height", 500);
            trial_graph = new TrialGraph(trial_svg, {
                custom_size: function() {
                    return [width, height];
                }
            });
            trial_graph.set_use_tooltip(d3.select("#showtooltips").property("checked"));
            trial_graph.load(data, t1, t2);
           
        },
        error: function (result, status) {
        }
    });
}

//Splitter
$('#show').height("100%")

$('#show').split({
    orientation: 'vertical', limit: 20,
    position: "60%",
    onDrag: function(){
       trial_graph.update_window();
    }

});

load_graph(t1, t2, selected_graph);

// Graph type
$( "[name='graphtype']" ).change(function() {
    selected_graph = $(this).attr('value');
    load_graph(t1, t2, selected_graph);
});

$( "[name='showtooltips']" ).change(function() {
    trial_graph.set_use_tooltip(d3.select("#showtooltips").property("checked"));
});


$('#side-internal').on('click', '.fold', function(e){
	var first = $(this).children()[0];
	$(this).next().slideToggle(200);
    $(first).toggleClass("fa-plus");
    $(first).toggleClass("fa-minus");
});

