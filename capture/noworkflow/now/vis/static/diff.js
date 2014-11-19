var width, height,
	t1, t2,
	trial_graph, trial_a, trial_b,
	selected_graph = "combined",

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
    trial_a.update_window();
    trial_b.update_window();
    
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
            $('#graphA').html('');
            $('#graphB').html('');

            var trial_svg = d3.select('#graph')
                .append('svg')
                .attr("width", 500)
                .attr("height", 500);
            trial_graph = new TrialGraph(0, trial_svg, {
                custom_size: function() {
                    return [$('#graph').width(), $('#graph').height()];
                }
            });
            trial_graph.set_use_tooltip(d3.select("#showtooltips").property("checked"));
            trial_graph.load(data.diff, t1, t2);
           
            var trialA_svg = d3.select('#graphA')
                .append('svg')
                .attr("width", $('#graphA').width())
                .attr("height", $('#graphA').height());
            trial_a = new TrialGraph(1, trialA_svg, {
                hint_message: "Trial "+t1,
                hint_y: 20,
                hint_class: "hbefore",
                custom_size: function() {
                    return [$('#graphA').width(), $('#graphA').height()];
                }
            });
            trial_a.set_use_tooltip(d3.select("#showtooltips").property("checked"));
            trial_a.load(data.trial1, t1, t1);

             var trialB_svg = d3.select('#graphB')
                .append('svg')
                .attr("width", $('#graphB').width())
                .attr("height", $('#graphB').height());
            trial_b = new TrialGraph(2, trialB_svg, {
                hint_message: "Trial "+t2,
                hint_y: 20,
                hint_class: "hafter",
                custom_size: function() {
                    return [$('#graphB').width(), $('#graphB').height()];
                }
            });
            trial_b.set_use_tooltip(d3.select("#showtooltips").property("checked"));
            trial_b.load(data.trial2, t2, t2);

        },
        error: function (result, status) {
        }
    });
}

//Splitter
$('#show').height("100%");

$('#show').split({
    orientation: 'vertical', limit: 20,
    position: "60%",
    onDrag: function(){
       trial_graph.update_window();
       trial_b.update_window();
    }

});
$('#graphs').height("100%");
$('#graph').height("100%");
$('#graph').width("100%");


$('#graphs').split({
    orientation: 'horizontal', limit: 20,
    position: "70%",
    onDrag: function(){
       trial_graph.update_window();
       trial_a.update_window();
       trial_b.update_window();
    }

});

$('#graphs #bottom').split({
    orientation: 'vertical', limit: 20,
    position: "50%",
    onDrag: function(){
        trial_a.update_window();
        trial_b.update_window();
       // trial_b.update_window();

       //trial_graph.update_window();
    }

});

load_graph(t1, t2, selected_graph);
// Graph type
$( "[name='graphtype']" ).change(function() {
    selected_graph = $(this).attr('value');
    load_graph(t1, t2, selected_graph);
});

$( "#combgraph" ).click();
$( "[name='showtooltips']" ).change(function() {
    trial_graph.set_use_tooltip(d3.select("#showtooltips").property("checked"));
    trial_a.set_use_tooltip(d3.select("#showtooltips").property("checked"));
    trial_b.set_use_tooltip(d3.select("#showtooltips").property("checked"));
});


$('#side-internal').on('click', '.fold', function(e){
	var first = $(this).children()[0];
	$(this).next().slideToggle(200);
    $(first).toggleClass("fa-plus");
    $(first).toggleClass("fa-minus");
});

