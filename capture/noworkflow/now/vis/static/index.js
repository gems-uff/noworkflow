/*global window, docEl, bodyEl, d3*/
/*global now_history_graph, now_trial_graph, HistoryGraph, TrialGraph,*/

var width, height;
var history_graph, trial_graph, nodes,
  selected_graph = "namespace_match",
  current_nid = 0;

var $loading = $('#loadingDiv').hide();
$(document)
  .ajaxStart(function () {
    $loading.show();
  })
  .ajaxStop(function () {
    $loading.hide();
  });

function get_url() {
  var arr = window.location.href.split('/');
  arr = arr[arr.length - 1].split('-');
  if (arr.length === 2) {
    current_nid = parseInt(arr[0], 10);
    selected_graph = arr[1].split('#')[0];
    return current_nid + "-" + selected_graph;
  }
  return arr[0];

}
get_url();

function update_graph_title() {
  $('#graph-title').text(
    $("#graphtype option[value='" + selected_graph + "']").text()
  );
  $("#graphtype").val(selected_graph);
}
update_graph_title();

function select_trial(tid) {
  var i;
  if (tid === 0) {
    history_graph.select_node(nodes[0]);
  } else {
    for (i = 0; i < nodes.length; i++) {
      if (nodes[i].title === tid) {
        history_graph.select_node(nodes[i]);
      }
    }
  }
}

var docEl = document.documentElement,
  bodyEl = document.getElementsByTagName('body')[0],
  colors = d3.scale.category10();


// Resizing

function calculate_window_size() {
  width = window.innerWidth || docEl.clientWidth || bodyEl.clientWidth;
  height =  window.innerHeight || docEl.clientHeight || bodyEl.clientHeight;
}
calculate_window_size();

window.onresize = function () {
  calculate_window_size();
  history_graph.update_window();
  trial_graph.update_window();
};


// Graphs
function load_graph(nid, url) {
  var cache = (($('#use_cache').is(":checked")) ? '1' : '0');
  $.ajax({
    type: "GET",
    contentType: "application/json; charset=utf-8",
    url: '/trials/' + nid + '/' + url + '/' + cache + '.json',
    dataType: 'json',
    async: true,
    data: {},
    success: function (data) {
      trial_graph = now_trial_graph('#graph', 0, nid, nid, data, 500, 500, "#trial-toolbar-tooltips", "#trial-toolbar-trial-fullname", {
        custom_size: function () {
          return [$('#graph').width(), $('#graph').height()];
        }
      });
      var temp = nid + "-" + url;
      if (get_url() !== temp) {
        window.history.pushState(temp, "Trial " + current_nid, "/" + temp);
      }
      current_nid = nid;
      selected_graph = url;
      update_graph_title();

    },
    error: function () { return null; }
  });
}

function load_dependencies(nid) {
  $.ajax({
    type: "GET",
    contentType: "application/json; charset=utf-8",
    url: '/trials/' + nid + '/dependencies',
    dataType: 'json',
    async: true,
    data: {},
    success: function (data) {
      var i;
      if (data.all.length > 0) {
        $('#side-internal').append('<div id="modules">' +
            '<div class="fold">' +
              '<i class="fa fa-minus"></i><span> Modules </span>' +
              '<a href="trials/' + nid + '/all_modules" title="Show all" class="show_all"><i class="fa fa-binoculars"></i></a>' +
            '</div>' +
            '<div class="foldable">' +
              '<ul class="mod-list">' +
              '</ul>' +
            '</div>' +
          '</div>');
        //data.local = data.all;
        for (i = 0; i < data.local.length; i++) {
          $('#side-internal #modules ul').append('<li>' +
              '<div class="name">' + data.local[i].name + '</div>' +
              '<div class="version">' + (data.local[i].version === null ? "" : data.local[i].version) + '</div>' +
              '<div class="clear"></div>' +
              '<div class="hash" title="' + data.local[i].path + '">' + data.local[i].code_hash + '</div>' +
            '</li>');
        }

      }

    },
    error: function () { return null; }
  });
}

function load_environment(nid) {
  $.ajax({
    type: "GET",
    contentType: "application/json; charset=utf-8",
    url: '/trials/' + nid + '/environment',
    dataType: 'json',
    async: true,
    data: {},
    success: function (data) {
      var li = function (key) {
        if (data.env[key]) {
          return '<li>' +
              '<span class="key"> ' + key + ' </span>' +
              '<span class="equal"> = </span>' +
              '<span class="value"> ' + data.env[key] + ' </span>' +
            '</li>';
        }
        return '';
      };

      $('#side-internal').append('<div id="environment">' +
          '<div class="fold">' +
            '<i class="fa fa-minus"></i><span> Environment </span>' +
            '<a href="trials/' + nid + '/all_environment" title="Show all" class="show_all"><i class="fa fa-binoculars"></i></a>' +
          '</div>' +
          '<div class="foldable">' +
            '<ul class="env-list">' +
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
            '</ul>' +
          '</div>' +
        '</div>');
    },
    error: function () { return null; }
  });
}

function load_file_accesses(nid) {
  $.ajax({
    type: "GET",
    contentType: "application/json; charset=utf-8",
    url: '/trials/' + nid + '/file_accesses',
    dataType: 'json',
    async: true,
    data: {},
    success: function (data) {
      var i;
      if (data.file_accesses.length > 0) {
        $('#side-internal').append('<div id="file_accesses">' +
            '<div class="fold">' +
              '<i class="fa fa-minus"></i><span> File Accesses </span>' +
              '<a href="trials/' + nid + '/all_file_accesses" title="Show all" class="show_all"><i class="fa fa-binoculars"></i></a>' +
            '</div>' +
            '<div class="foldable">' +
              '<ul class="fac-list">' +
              '</ul>' +
            '</div>' +
          '</div>');
        //data.local = data.all;
        for (i = 0; i < data.file_accesses.length; i++) {
          $('#side-internal #file_accesses ul').append('<li>' +
              '<div class="name" title="Name">' + data.file_accesses[i].name + '</div>' +
              '<div class="mode" title="Mode">' + data.file_accesses[i].mode + '</div>' +
              '<div class="buffering" title="Buffering">' + data.file_accesses[i].buffering + '</div>' +
              '<div class="clear"></div>' +
              '<div class="timestamp" title="Time">' + data.file_accesses[i].timestamp + '</div>' +
              '<div class="content_hash_before hash" title="Content hash before">' + data.file_accesses[i].content_hash_before + '</div>' +
              '<div class="content_hash_after hash" title="Content hash after">' + data.file_accesses[i].content_hash_after + '</div>' +
              '<div class="stack" title="Stack">' + data.file_accesses[i].stack + '</div>' +
            '</li>');
        }

      }

    },
    error: function () { return null; }
  });
}

function reload() {
  $.ajax({
    type: "GET",
    contentType: "application/json; charset=utf-8",
    url: '/trials',
    dataType: 'json',
    data: {
      'script': $("select[name='script']").val(),
      'execution': $("select[name='execution']").val()
    },
    async: true,
    success: function (data) {
      $("#historygraph").html('');
      var w =  width - $('.filter').width();
      var hg = now_history_graph('#historygraph', 0, data, w, height, "#show-history-tooltips", {
        select_node: function (n) {
          $('#side-internal').html('<div id="main">' +
              '<h1>Trial ' + n.title + '</h1>' +
              '<h3 class="hash">' + n.info.code_hash + '</h3>' +
              '<span class="attr"><span class="desc">Script: </span><span class="script">' + n.info.script + '</span></span>' +
              '<span class="attr"><span class="desc">Start: </span><span class="start">' + n.info.start + '</span></span>' +
              '<span class="attr"><span class="desc">Finish: </span><span class="finish">' + n.info.finish + '</span></span>' +
              '<span class="attr"><span class="desc">Duration: </span><span class="duration">' + n.info.duration_text + '</span></span>' +
              (n.info.arguments ? ('<span class="attr"><span class="desc">Arguments: </span><span class="arguments">' + n.info.arguments + '</span></span>') : "") +
              (n.info.duration ? ('<span class="attr"><span class="desc">Duration: </span><span class="duration">' + n.info.duration + '</span></span>') : "") +
            '</div>');
          current_nid = n.title;
          load_dependencies(current_nid);
          load_environment(current_nid);
          load_file_accesses(current_nid);
          load_graph(current_nid, selected_graph);
        },
        ctrl_click: function (new_node, old_node) {
          window.open('diff/' + old_node.title + '/' + new_node.title + '/0-2-' + selected_graph);
        },
        custom_size: function () {
          var docEl = document.documentElement,
            bodyEl = document.getElementsByTagName('body')[0];
          var x = window.innerWidth || docEl.clientWidth || bodyEl.clientWidth;
          return [x, $('#top').height()];
        }
      });

      history_graph = hg.graph;
      nodes = hg.nodes;
      select_trial(current_nid);
    },
    error: function () { return null; }
  });
  return false;
}
reload();

$('#reload').on('click', reload);

$('#show-filter-toolbar').on('click', function () {
  var i = $('#show-filter-toolbar i');
  i.toggleClass('fa-circle-o fa-circle');
  //i.hasClass('fa-circle-o')
  $('.filter').toggle({
    complete: function () {
      history_graph.update_window();
    },
    direction: "left",
    duration: 400,
    effect: 'drop'
  });

});

$('#show-graph-toolbar').click(function () {
  var i = $('#show-graph-toolbar i');
  i.toggleClass('fa-circle-o fa-circle');
  //i.hasClass('fa-circle-o')
  $('#graphselector').slideToggle(400, function () {
    trial_graph.update_window();
  });

});

// Splitters

var horizontal = $('#splitter').split({
  orientation: 'horizontal',
  limit: 20,
  position: HistoryGraph.consts.height + 3,
  onDrag: function () {
    history_graph.update_window();
    trial_graph.update_window();
  }
});
$('#show').width("100%");

$('#show').split({
  orientation: 'vertical',
  limit: 20,
  position: "60%",
  onDrag: function () {
    trial_graph.update_window();
  }

});
$('#graph').height("100%");
$('#graph').width("100%");

// Graph type
$("#reload_graph").on('click', function () {
  load_graph(current_nid, $('#graphtype').val());
  return false;
});

$("[name='trial-toolbar-tooltips']").change(function () {
  trial_graph.set_use_tooltip(d3.select("#trial-toolbar-tooltips").property("checked"));
});

$("[name='trial-toolbar-trial-fullname']").change(function () {
  trial_graph.set_hide_fullname(d3.select("#trial-toolbar-trial-fullname").property("checked"));
});

$("[name='show-history-tooltips']").change(function () {
  history_graph.set_use_tooltip(d3.select("#show-history-tooltips").property("checked"));
});

$('#side-internal').on('click', '.fold', function () {
  $(this.nextSibling).slideToggle(200);
  $(this.firstChild).toggleClass("fa-plus");
  $(this.firstChild).toggleClass("fa-minus");
});

$('#restore-history-zoom').on('click', function () {
  history_graph.reset_zoom();
  return false;
});

window.onpopstate = function (e) {
  if (e.state) {
    history_graph._unselect_node();
    get_url();
    select_trial(current_nid);
  }
};

