import { IRenderMime } from "@jupyterlab/rendermime-interfaces";
import { Message } from "@lumino/messaging";
import { Widget } from "@lumino/widgets";
import { HistoryGraph, HistoryGraphData } from "@noworkflow/history";
import { makeid } from "@noworkflow/utils";


/**
 * A widget for rendering data, for usage with rendermime.
 */
export class RenderedHistory extends Widget implements IRenderMime.IRenderer {
  /**
   * Create a new widget for rendering
   */
  constructor(options: IRenderMime.IRendererOptions) {
    super();
    this._mimeType = options.mimeType;
    this.addClass('jp-RenderedNowHistory');
    this.div = document.createElement('div');
    
    this.node.appendChild(this.div);
  }

  /**
   * Render into this widget's node.
   */
  renderModel(model: IRenderMime.IMimeModel): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      let data = model.data[this._mimeType] as any | HistoryGraphData;
      this.graph = new HistoryGraph('history-' + makeid(), this.div, {
        width: data.width,
        height: data.height,
        hintMessage: ""
      });
      this.graph.load(data)
      this.update();
      resolve();
    });
  }

  /**
   * A message handler invoked on an `'after-show'` message.
   */
  protected onAfterShow(msg: Message): void {
    this.update();
  }

  /**
   * A message handler invoked on a `'resize'` message.
   */
  protected onResize(msg: Widget.ResizeMessage): void {
    this.update();
  }

  /**
   * A message handler invoked on an `'update-request'` message.
   */
  protected onUpdateRequest(msg: Message): void {
    // Update size after update
    if (this.isVisible && this.graph) {
      let width =  this.node.getBoundingClientRect().width - 24;
      this.graph.config.width = width;
      this.div.style.width = width + "px";
      this.graph.updateWindow();
    }
  }

  graph: HistoryGraph | undefined;
  div: HTMLDivElement;
  private _mimeType: string;
}

  
/**
 * A mime renderer factory for data.
 */
export const historyFactory: IRenderMime.IRendererFactory = {
  safe: false,
  mimeTypes: ['application/noworkflow.history+json'],
  createRenderer: options => new RenderedHistory(options)
};
