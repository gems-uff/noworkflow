import {DockPanel, Widget, DockLayout} from '@phosphor/widgets';
import {each} from '@phosphor/algorithm';


export
interface VisWidget extends Widget {
  nowVis?: string;
}


export
interface FindResult {
  area: DockLayout.AreaConfig | null;
  index: number;
}


export
function findInLayout(area: DockLayout.AreaConfig | null, widget: Widget): FindResult | null {
  if (area == null || area.type == 'tab-area') {
    return null;
  }
  var splitconfig: DockLayout.ISplitAreaConfig = area;
  var result: FindResult | null = null;
  splitconfig.children.every((child, index) => {
    if (child.type == 'tab-area') {
      var tabconfig: DockLayout.ITabAreaConfig = child;
      for (var tabwidget of tabconfig.widgets) {
        if (tabwidget == widget) {
          result = {
            area: area,
            index: index
          }
          return false;
        }
      }
    } else {
      var temp = findInLayout(child, widget);
      if (temp) {
        result = temp;
        return false;
      }
    }
    return true;
  });
  return result;
}


export
class NowVisPanel extends DockPanel {

  addMainWidget(widget: Widget, options: DockLayout.IAddOptions = {}): void {
    if (options.ref) {
      if ((options.ref as VisWidget).nowVis != "main") {
        console.log("Warning: options.ref is not 'main'");
      }
    } else {
      each(this.widgets(), (w: VisWidget) => {
        if (w.nowVis == "main") {
          options.ref = w;
        }
      });
    }
    (widget as VisWidget).nowVis = "main";
    this.addWidget(widget, options);
  }

  addGraphWidget(widget: Widget, options: DockLayout.IAddOptions = {}): void {
    var operation: string = "none";
    if (options.ref) {
      if ((options.ref as VisWidget).nowVis != "graph") {
        console.log("Warning: options.ref is not 'graph'");
      }
    } else {
      each(this.widgets(), (w: VisWidget) => {
        if (w.nowVis == "main" && !options.ref) {
          options.ref = w;
          options.mode = "split-bottom";
          operation = "main";
        } else if ((w.nowVis == "info") && (operation != "graph")) {
          options.ref = w;
          options.mode = "split-left";
          operation = "info";
        } else if (w.nowVis == "graph") {
          options.ref = w;
          options.mode = "tab-after";
          operation = "graph";
        }
      });
    }
    (widget as VisWidget).nowVis = "graph";
    this.addWidget(widget, options);

    if (operation == "main") {
      var layout = this.saveLayout();
      var sublayout = findInLayout(layout.main, widget);
      if (sublayout) {
        var sizes: number[] = (sublayout.area as DockLayout.ISplitAreaConfig).sizes;
        sizes[0] = 0.20;
        sizes[1] = 0.80;
        this.restoreLayout(layout);
      }
    }

    if (operation == "info") {
      var layout = this.saveLayout();
      var sublayout = findInLayout(layout.main, widget);
      if (sublayout) {
        var sizes: number[] = (sublayout.area as DockLayout.ISplitAreaConfig).sizes;
        sizes[0] = 0.80;
        sizes[1] = 0.20;
        this.restoreLayout(layout);
      }
    }
  }

  addInfoWidget(widget: Widget, options: DockLayout.IAddOptions = {}): void {
    var operation: string = "none";
    if (options.ref) {
      if ((options.ref as VisWidget).nowVis != "info") {
        console.log("Warning: options.ref is not 'info'");
      }
    } else {
      each(this.widgets(), (w: VisWidget) => {
        if (w.nowVis == "main" && !options.ref) {
          options.ref = w;
          options.mode = "split-bottom";
          operation = "main";
        } else if ((w.nowVis == "graph") && (operation != "info")) {
          options.ref = w;
          options.mode = "split-right";
          operation = "graph";
        } else if (w.nowVis == "info") {
          options.ref = w;
          options.mode = "tab-after";
          operation = "info";
        }
      });
    }
    (widget as VisWidget).nowVis = "info";
    this.addWidget(widget, options);

    if (operation == "main") {
      var layout = this.saveLayout();
      var sublayout = findInLayout(layout.main, widget);
      if (sublayout) {
        var sizes: number[] = (sublayout.area as DockLayout.ISplitAreaConfig).sizes;
        sizes[0] = 0.20;
        sizes[1] = 0.80;
        this.restoreLayout(layout);
      }
    }

    if (operation == "graph") {
      var layout = this.saveLayout();
      var sublayout = findInLayout(layout.main, widget);
      if (sublayout) {
        var sizes: number[] = (sublayout.area as DockLayout.ISplitAreaConfig).sizes;
        sizes[0] = 0.80;
        sizes[1] = 0.20;
        this.restoreLayout(layout);
      }
    }
  }

}
