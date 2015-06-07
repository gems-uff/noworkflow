/*global window, docEl, bodyEl, d3 */
/*global now_trial_graph */

var width, height,
  trial_graph, trial_a, trial_b,
  selected_graph = "namespace_match",
  neighborhoods = 2,
  time_limit = 0,
  t1 = $("#trial1").text(),
  t2 = $("#trial2").text();

function get_url() {
  var arr = window.location.href.split('/');
  arr = arr[arr.length - 1].split('-');
  if (arr.length === 3) {
    time_limit = parseInt(arr[0], 10);
    neighborhoods = parseInt(arr[1], 10);
    selected_graph = arr[2].split('#')[0];
    return time_limit + "-" + neighborhoods + '-' + selected_graph;
  }
  return arr[0];
}
get_url();

function update_graph_title() {
  $('#graph-title').text(
    $("#graphtype option[value='" + selected_graph + "']").text()
  );
  $("#graphtype").val(selected_graph);
  $("#difflevel").val(neighborhoods);
  $("#graphlimit").val(time_limit);
}
update_graph_title();


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
function load_graph(t1, t2, type, tl, nh) {
  var cache = (($('#use_cache').is(":checked")) ? '1' : '0');
 /* $('#graph').html('');
  $('#graphA').html('');
  $('#graphB').html('');*/
  $.ajax({
    type: "GET",
    contentType: "application/json; charset=utf-8",
    url: '/diff/' + t1 + '/' + t2 + '/' + type + '/' + tl + '-' + nh + '-' + cache + '.json',
    dataType: 'json',
    async: true,
    data: {},
    success: function (data) {
      trial_graph = now_trial_graph('#graph', 0, parseInt(t1, 10), parseInt(t2, 10), data.diff, 500, 500, "#trial-toolbar-tooltips", "#trial-toolbar-trial-fullname", {
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

      trial_a = now_trial_graph('#graphA', 1, parseInt(t1, 10), parseInt(t1, 10), data.trial1, $('#graphA').width(), $('#graphA').height(), "#trial-toolbar-tooltips", "#trial-toolbar-trial-fullname", {
        hint_message: "Trial " + t1,
        hint_y: 20,
        hint_class: "hbefore",
        custom_size: function () {
          return [$('#graphA').width(), $('#graphA').height()];
        },
        custom_mouseover: trial_custom_mouseover,
        custom_mouseout: trial_custom_mouseout
      });

      trial_b = now_trial_graph('#graphB', 2, parseInt(t2, 10), parseInt(t2, 10), data.trial2, $('#graphB').width(), $('#graphB').height(), "#trial-toolbar-tooltips", "#trial-toolbar-trial-fullname", {
        hint_message: "Trial " + t2,
        hint_y: 20,
        hint_class: "hafter",
        custom_size: function () {
          return [$('#graphB').width(), $('#graphB').height()];
        },
        custom_mouseover: trial_custom_mouseover,
        custom_mouseout: trial_custom_mouseout
      });

      var temp = tl + "-" + nh + '-' + type;
      if (get_url() !== temp) {
        window.history.pushState(temp, "Diff " + t1 + "-" + t2, "/diff/" + t1 + '/' + t2 + '/' + temp);
      }
      time_limit = tl;
      neighborhoods = nh;
      selected_graph = type;
      update_graph_title();

    },
    error: function () {
      return null;
    }
  });
}

$('#show-graph-toolbar').click(function () {
  var i = $('#show-graph-toolbar i');
  i.toggleClass('fa-circle-o fa-circle');
  $('#graphselector').slideToggle(400, function () {
    trial_graph.update_window();
    trial_a.update_window();
    trial_b.update_window();
  });

});

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

load_graph(t1, t2, selected_graph, time_limit, neighborhoods);
// Graph type
$("#reload_graph").on('click', function () {
  selected_graph = $(this).attr('value');
  load_graph(t1, t2, $('#graphtype').val(), $('#graphlimit').val(), $('#difflevel').val());
  return false;
});

$("#combgraph").click();
$("[name='trial-toolbar-tooltips']").change(function () {
  trial_graph.set_use_tooltip(d3.select("#trial-toolbar-tooltips").property("checked"));
  trial_a.set_use_tooltip(d3.select("#trial-toolbar-tooltips").property("checked"));
  trial_b.set_use_tooltip(d3.select("#trial-toolbar-tooltips").property("checked"));
});
$("[name='trial-toolbar-trial-fullname']").change(function () {
  trial_graph.set_hide_fullname(d3.select("#trial-toolbar-trial-fullname").property("checked"));
  trial_a.set_hide_fullname(d3.select("#trial-toolbar-trial-fullname").property("checked"));
  trial_b.set_hide_fullname(d3.select("#trial-toolbar-trial-fullname").property("checked"));
});


$('#side-internal').on('click', '.fold', function () {
  var first = $(this).children()[0];
  $(this).next().slideToggle(200);
  $(first).toggleClass("fa-plus");
  $(first).toggleClass("fa-minus");
});


window.onpopstate = function (e) {
  if (e.state) {
    get_url();
    load_graph(t1, t2, selected_graph, time_limit, neighborhoods);
  }
};

var $loading = $('#loadingDiv').hide();
$(document)
  .ajaxStart(function () {
    $loading.show();
  })
  .ajaxStop(function () {
    $loading.hide();
  });