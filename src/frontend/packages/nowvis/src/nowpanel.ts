import { DockPanel, Widget, DockLayout } from '@lumino/widgets';

export interface IVisWidget extends Widget {
  nowVis?: string;
}

export interface IFindResult {
  area: DockLayout.AreaConfig | null;
  index: number;
}

export function findInLayout(
  area: DockLayout.AreaConfig | null,
  widget: Widget
): IFindResult | null {
  if (area == null || area.type === 'tab-area') {
    return null;
  }
  const splitconfig: DockLayout.ISplitAreaConfig = area;
  let result: IFindResult | null = null;
  splitconfig.children.every((child, index) => {
    if (child.type === 'tab-area') {
      const tabconfig: DockLayout.ITabAreaConfig = child;
      for (const tabwidget of tabconfig.widgets) {
        if (tabwidget === widget) {
          result = {
            area: area,
            index: index
          };
          return false;
        }
      }
    } else {
      const temp = findInLayout(child, widget);
      if (temp) {
        result = temp;
        return false;
      }
    }
    return true;
  });
  return result;
}

export class NowVisPanel extends DockPanel {
  addMainWidget(widget: Widget, options: DockLayout.IAddOptions = {}): void {
    if (options.ref) {
      if ((options.ref as IVisWidget).nowVis !== 'main') {
        console.log("Warning: options.ref is not 'main'");
      }
    } else {
      for (const w of this.widgets()) {
        const wnow = w as IVisWidget;
        if (wnow.nowVis === 'main') {
          options.ref = w;
        }
      }
    }
    (widget as IVisWidget).nowVis = 'main';
    this.addWidget(widget, options);
  }

  addGraphWidget(widget: Widget, options: DockLayout.IAddOptions = {}): void {
    let operation: string = 'none';
    if (options.ref) {
      if ((options.ref as IVisWidget).nowVis !== 'graph') {
        console.log("Warning: options.ref is not 'graph'");
      }
    } else {
      for (const w of this.widgets()) {
        const wnow = w as IVisWidget;
        if (wnow.nowVis === 'main' && !options.ref) {
          options.ref = w;
          options.mode = 'split-bottom';
          operation = 'main';
        } else if (wnow.nowVis === 'info' && operation !== 'graph') {
          options.ref = w;
          options.mode = 'split-left';
          operation = 'info';
        } else if (wnow.nowVis === 'graph') {
          options.ref = w;
          options.mode = 'tab-after';
          operation = 'graph';
        }
      }
    }
    (widget as IVisWidget).nowVis = 'graph';
    this.addWidget(widget, options);

    if (operation === 'main') {
      const layout = this.saveLayout();
      const sublayout = findInLayout(layout.main, widget);
      if (sublayout) {
        const sizes: number[] = (sublayout.area as DockLayout.ISplitAreaConfig)
          .sizes;
        sizes[0] = 0.2;
        sizes[1] = 0.8;
        this.restoreLayout(layout);
      }
    }

    if (operation === 'info') {
      const layout = this.saveLayout();
      const sublayout = findInLayout(layout.main, widget);
      if (sublayout) {
        const sizes: number[] = (sublayout.area as DockLayout.ISplitAreaConfig)
          .sizes;
        sizes[0] = 0.8;
        sizes[1] = 0.2;
        this.restoreLayout(layout);
      }
    }
  }

  addInfoWidget(widget: Widget, options: DockLayout.IAddOptions = {}): void {
    let operation: string = 'none';
    if (options.ref) {
      if ((options.ref as IVisWidget).nowVis !== 'info') {
        console.log("Warning: options.ref is not 'info'");
      }
    } else {
      for (const w of this.widgets()) {
        const wnow = w as IVisWidget;
        if (wnow.nowVis === 'main' && !options.ref) {
          options.ref = w;
          options.mode = 'split-bottom';
          operation = 'main';
        } else if (wnow.nowVis === 'graph' && operation !== 'info') {
          options.ref = w;
          options.mode = 'split-right';
          operation = 'graph';
        } else if (wnow.nowVis === 'info') {
          options.ref = w;
          options.mode = 'tab-after';
          operation = 'info';
        }
      }
    }
    (widget as IVisWidget).nowVis = 'info';
    this.addWidget(widget, options);

    if (operation === 'main') {
      const layout = this.saveLayout();
      const sublayout = findInLayout(layout.main, widget);
      if (sublayout) {
        const sizes: number[] = (sublayout.area as DockLayout.ISplitAreaConfig)
          .sizes;
        sizes[0] = 0.2;
        sizes[1] = 0.8;
        this.restoreLayout(layout);
      }
    }

    if (operation === 'graph') {
      const layout = this.saveLayout();
      const sublayout = findInLayout(layout.main, widget);
      if (sublayout) {
        const sizes: number[] = (sublayout.area as DockLayout.ISplitAreaConfig)
          .sizes;
        sizes[0] = 0.8;
        sizes[1] = 0.2;
        this.restoreLayout(layout);
      }
    }
  }
}
