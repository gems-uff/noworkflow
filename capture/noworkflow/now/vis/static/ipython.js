/*global jQuery, d3 */
/*global now_history_graph, now_trial_graph */

function empty() {
  return function () { return null; };
}

function custom_size(width, height) {
  return function () { return [width, height]; };
}

function history_graph_html(uid, width, height) {
  return "<div id='history-" + uid + "' class='now-history-graph ipython-graph' style='width: " + width + "px; height: " + height + "px;'></div>";
}

function trial_graph_html(uid, width, height, modifier) {
  modifier = modifier || "";
  return "<div id='graph" + modifier + "-" + uid + "' class='now-trial-graph ipython-graph' style='width: " + width + "px; height: " + height + "px;'></div>";
}

function toolbar_html(uid, name, history) {
  var result = "<div class='toolbar'>";
  if (history) {
    result += "<a class='toollink' id='restore-history-zoom-" + uid + "' href='#' title='Restore zoom'>" +
        "<i class='fa fa-eye'></i>" +
      "</a>";
  } else {
    result += "<input id='trial-toolbar-trial-fullname-" + uid + "' type='checkbox' name='trial-toolbar-trial-fullname' value='show'>" +
        "<label for='trial-toolbar-trial-fullname-" + uid + "' title='Show tooltips on mouse hover'>" +
          "<i class='fa fa-font'></i>" +
        "</label>";
  }

  result += "<input id='" + name + "-" + uid + "' type='checkbox' name='" + name + "' value='show'>" +
      "<label for='" + name + "-" + uid + "' title='Show tooltips on mouse hover'>" +
        "<i class='fa fa-comment'></i>" +
      "</label>" +
    "</div>";
  return result;
}

function add_tooltips(graph, name, uid) {
  $("[name='" + name + "']").change(function () {
    graph.set_use_tooltip(d3.select("#" + name + "-" + uid).property("checked"));
  });
}

function add_hide_fullname(graph, name, uid) {
  $("[name='" + name + "']").change(function () {
    graph.set_hide_fullname(d3.select("#" + name + "-" + uid).property("checked"));
  });
}

function create_history_graph(history) {
  if (history.length) {
    var uid = history.data('uid'),
      width = history.data('width'),
      height = history.data('height'),
      data = jQuery.parseJSON(jQuery.trim(history.text()));

    history.parent().append("<div class='now-history now'>" +
        "<div>" +
          toolbar_html(uid, 'show-history-tooltips', true) +
          history_graph_html(uid, width, height) +
        "</div>" +
      "</div>");

    var hg = now_history_graph("#history-" + uid, uid, data, width, height, "#show-history-tooltips-" + uid, {
      custom_size: custom_size(width, height),
      hint_message: "",
    });
    add_tooltips(hg.graph, "show-history-tooltips", uid);

    $("#restore-history-zoom-" + uid).on("click", function () {
      hg.graph.reset_zoom();
    });
    history.remove();
  }
}



function create_trial_graph(trial) {
  if (trial.length) {
    var uid = trial.data('uid'),
      id = trial.data('id'),
      width = trial.data('width'),
      height = trial.data('height'),
      data = jQuery.parseJSON(jQuery.trim(trial.text()));

    trial.parent().append(
      "<div class='now-trial now'>" +
        "<div>" +
          toolbar_html(uid, "trial-toolbar-tooltips", false) +
          trial_graph_html(uid, width, height) +
        "</div>" +
        "</div>"
    );
    var trial_graph = now_trial_graph("#graph-" + uid, uid, id, id, data, width, height, "#trial-toolbar-tooltips-" + uid, "#trial-toolbar-trial-fullname-" + uid, {
      custom_size: custom_size(width, height),
      hint_message: "Trial " + id + ". Ctrl-click to toggle nodes"
    });
    add_tooltips(trial_graph, "trial-toolbar-tooltips", uid);
    add_hide_fullname(trial_graph, "trial-toolbar-trial-fullname", uid);
    trial.remove();
  }
}

function create_diff_graph(diff) {
  if (diff.length) {
    var trial_graph, trial_a, trial_b,
      trial_custom_mouseover = empty(),
      trial_custom_mouseout = empty(),
      combined_html = trial_graph_html,
      side_by_side_html = function (uid, width, height) {
        return "<div class='bottom'>" +
            trial_graph_html(uid, width / 2, height, "A") +
            trial_graph_html(uid, width / 2, height, "B") +
          "</div>";
      },
      both_html = function (uid, width, height) {
        return trial_graph_html(uid, width, height) +
          "<div class='bottom'>" +
            trial_graph_html(uid, width / 2, height, "A") +
            trial_graph_html(uid, width / 2, height, "B") +
          "</div>";
      },
      combined_js = function (uid, id1, id2, data, width, height) {
        trial_graph = now_trial_graph("#graph-" + uid, uid, id1, id2, data[0], width, height, "#trial-toolbar-tooltips-" + uid, "#trial-toolbar-trial-fullname-" + uid, {
          custom_size: custom_size(width, height),
          custom_mouseout: trial_custom_mouseout,
          hint_message: "Diff " + id1 + "/" + id2 + ". Ctrl-click to toggle nodes"
        });
        add_tooltips(trial_graph, "trial-toolbar-tooltips", uid);
        add_hide_fullname(trial_graph, "trial-toolbar-trial-fullname", uid);
      },
      side_by_side_js = function (uid, id1, id2, data, width, height) {
        trial_a = now_trial_graph("#graphA-" + uid, "1" + uid, id1, id1, data[1], width, height, "#trial-toolbar-tooltips-" + uid, "#trial-toolbar-trial-fullname-" + uid, {
          custom_size: custom_size(width, height),
          hint_message: "Trial " + id1,
          hint_class: "hbefore",
          custom_mouseover: trial_custom_mouseover,
          custom_mouseout: trial_custom_mouseout
        });
        trial_b = now_trial_graph("#graphB-" + uid, "2" + uid, id2, id2, data[2], width, height, "#trial-toolbar-tooltips-" + uid, "#trial-toolbar-trial-fullname-" + uid, {
          custom_size: custom_size(width, height),
          hint_message: "Trial " + id2,
          hint_class: "hafter",
          custom_mouseover: trial_custom_mouseover,
          custom_mouseout: trial_custom_mouseout
        });
        add_tooltips(trial_a, "trial-toolbar-tooltips", uid);
        add_tooltips(trial_b, "trial-toolbar-tooltips", uid);
        add_hide_fullname(trial_a, "trial-toolbar-trial-fullname", uid);
        add_hide_fullname(trial_b, "trial-toolbar-trial-fullname", uid);
      },
      both_js = function (uid, id1, id2, data, width, height) {
        trial_custom_mouseover = function (d) {
          d3.select("#node-" + trial_graph.graph_id + "-" + d.node.diff + " circle")
            .classed("node-hover", true);
        };

        trial_custom_mouseout = function () {
          d3.selectAll(".node-hover")
            .classed("node-hover", false);
        };
        combined_js(uid, id1, id2, data, width, height);
        side_by_side_js(uid, id1, id2, data, width, height);
      };

    var diff_html = [combined_html, side_by_side_html, both_html],
      diff_js = [combined_js, side_by_side_js, both_js];

    var uid = diff.data('uid'),
      id1 = diff.data('id1'),
      id2 = diff.data('id2'),
      width = diff.data('width'),
      height = diff.data('height'),
      display_mode = diff.data('mode'),
      data = jQuery.parseJSON(jQuery.trim(diff.text()));
    console.log(diff.text());

    diff.parent().append(
      "<div class='now-trial now'>" +
        "<div>" +
          toolbar_html(uid, "trial-toolbar-tooltips", false) +
          diff_html[display_mode](uid, width, height) +
        "</div>" +
        "</div>"
    );
    diff_js[display_mode](uid, id1, id2, data, width, height);
    diff.remove();
  }
}


$(document).unbind('DOMNodeInserted.noworkflow');
$(document).bind('DOMNodeInserted.noworkflow', function (event) {
  if ($(event.target).hasClass('output_area')) {
    create_history_graph($(event.target).find('.nowip-history'));
    create_trial_graph($(event.target).find('.nowip-trial'));
    create_diff_graph($(event.target).find('.nowip-diff'));
  }
});