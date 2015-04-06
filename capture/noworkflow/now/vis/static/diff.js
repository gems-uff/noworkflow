/*global window, docEl, bodyEl, d3 */
/*global now_trial_graph */

var width, height,
  trial_graph, trial_a, trial_b,
  selected_graph = "combined",
  t1 = $("#trial1").text(),
  t2 = $("#trial2").text();

// Resizing
function calculate_window_size() {
  width = window.innerWidth || docEl.clientWidth || bodyEl.clientWidth;
  height =  window.innerHeight || docEl.clientHeight || bodyEl.clientHeight;
}
calculate_window_size();

window.onresize = function () {
  calculate_window_size();
  trial_graph.update_window();
  trial_a.update_window();
  trial_b.update_window();
};

function trial_custom_mouseover(d) {
  d3.select('#node-' + trial_graph.graph_id + '-' + d.node.diff + ' circle')
    .classed('node-hover', true);
}

function trial_custom_mouseout() {
  d3.selectAll('.node-hover')
    .classed('node-hover', false);
}


// Graphs
function load_graph(t1, t2, url) {
  $.ajax({
    type: "GET",
    contentType: "application/json; charset=utf-8",
    url: '/diff/' + t1 + '/' + t2 + '/' + url,
    dataType: 'json',
    async: true,
    data: {},
    success: function (data) {
      trial_graph = now_trial_graph('#graph', 0, t1, t2, data.diff, 500, 500, "#showtooltips", {
        custom_size: function () {
          return [$('#graph').width(), $('#graph').height()];
        },
        custom_mouseover: function (d, name) {
          if (name === 'node') {
            var tg = (d[name].trial_id === t1) ? trial_a : trial_b,
              selector = '#node-' + tg.graph_id + '-' + d[name].original + ' circle';
            d3.select(selector)
              .classed('node-hover', true);
          } else {
            var selector1 = '#node-' + trial_a.graph_id + '-' + d.node1.original + ' circle',
              selector2 = '#node-' + trial_b.graph_id + '-' + d.node2.original + ' circle';
            d3.select(selector1)
              .classed('node-hover', true);
            d3.select(selector2)
              .classed('node-hover', true);
          }

        },
        custom_mouseout: trial_custom_mouseout
      });

      trial_a = now_trial_graph('#graphA', 1, t1, t1, data.trial1, $('#graphA').width(), $('#graphA').height(), "#showtooltips", {
        hint_message: "Trial " + t1,
        hint_y: 20,
        hint_class: "hbefore",
        custom_size: function () {
          return [$('#graphA').width(), $('#graphA').height()];
        },
        custom_mouseover: trial_custom_mouseover,
        custom_mouseout: trial_custom_mouseout
      });

      trial_b = now_trial_graph('#graphB', 2, t2, t2, data.trial2, $('#graphB').width(), $('#graphB').height(), "#showtooltips", {
        hint_message: "Trial " + t2,
        hint_y: 20,
        hint_class: "hafter",
        custom_size: function () {
          return [$('#graphB').width(), $('#graphB').height()];
        },
        custom_mouseover: trial_custom_mouseover,
        custom_mouseout: trial_custom_mouseout
      });

    },
    error: function () {
      return null;
    }
  });
}

//Splitter
$('#show').height("100%");

$('#show').split({
  orientation: 'vertical',
  limit: 20,
  position: "60%",
  onDrag: function () {
    trial_graph.update_window();
    trial_b.update_window();
  }

});
$('#graphs').height("100%");
$('#graph').height("100%");
$('#graph').width("100%");


$('#graphs').split({
  orientation: 'horizontal',
  limit: 20,
  position: "70%",
  onDrag: function () {
    trial_graph.update_window();
    trial_a.update_window();
    trial_b.update_window();
  }

});

$('#graphs .bottom').split({
  orientation: 'vertical',
  limit: 20,
  position: "50%",
  onDrag: function () {
    trial_a.update_window();
    trial_b.update_window();
  }

});

load_graph(t1, t2, selected_graph);
// Graph type
$("[name='graphtype']").change(function () {
  selected_graph = $(this).attr('value');
  load_graph(t1, t2, selected_graph);
});

$("#combgraph").click();
$("[name='showtooltips']").change(function () {
  trial_graph.set_use_tooltip(d3.select("#showtooltips").property("checked"));
  trial_a.set_use_tooltip(d3.select("#showtooltips").property("checked"));
  trial_b.set_use_tooltip(d3.select("#showtooltips").property("checked"));
});


$('#side-internal').on('click', '.fold', function () {
  var first = $(this).children()[0];
  $(this).next().slideToggle(200);
  $(first).toggleClass("fa-plus");
  $(first).toggleClass("fa-minus");
});

