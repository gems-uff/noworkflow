import { IRenderMime } from '@jupyterlab/rendermime-interfaces';
import { Message } from '@lumino/messaging';
import { Widget } from '@lumino/widgets';
import { makeid } from '@noworkflow/utils';
import CodeMirror from 'codemirror';

/**
 * A widget for rendering data, for usage with rendermime.
 */
export class RenderedCode extends Widget implements IRenderMime.IRenderer {
  /**
   * Create a new widget for rendering
   */
  constructor(options: IRenderMime.IRendererOptions) {
    super();
    this._mimeType = options.mimeType;
    this.addClass('jp-RenderedNowCode');
    this.div = document.createElement('div');
    this.node.appendChild(this.div);
  }

  /**
   * Render into this widget's node.
   */
  renderModel(model: IRenderMime.IMimeModel): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      const data = model.data[this._mimeType] as any;
      const code_id = makeid();
      const textarea = document.createElement('textarea');
      this.div.appendChild(textarea);
      textarea.id = code_id;
      textarea.value = data.code;
      this.code_mirror = CodeMirror.fromTextArea(textarea, {
        lineNumbers: true,
        firstLineNumber: data.firstLineNumber,
        mode: 'python',
        readOnly: true
      });
      this.code_mirror.setValue(data.code);
      const marks = data.marks;
      marks.forEach((mark: Parameters<CodeMirror.Doc['markText']>) => {
        this.code_mirror?.markText(...mark);
      });

      if (data.showSelection) {
        const selection = document.createElement('input');
        selection.id = code_id + '-selection';
        selection.type = 'text';
        this.div.appendChild(selection);
        this.code_mirror.on('cursorActivity', (cm: any) => {
          const tcursor = cm.getCursor(true);
          const fcursor = cm.getCursor(false);
          selection.value =
            '[' +
            tcursor.line +
            ', ' +
            tcursor.ch +
            '], ' +
            '[' +
            fcursor.line +
            ', ' +
            fcursor.ch +
            ']';
        });
      }

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
    if (this.isVisible && this.code_mirror) {
      setTimeout(() => {
        this.code_mirror?.refresh();
      }, 1);
    }
  }

  div: HTMLDivElement;
  code_mirror: CodeMirror.EditorFromTextArea | undefined;
  private _mimeType: string;
}

/**
 * A mime renderer factory for data.
 */
export const codeFactory: IRenderMime.IRendererFactory = {
  safe: false,
  mimeTypes: ['application/noworkflow.code+json'],
  createRenderer: options => new RenderedCode(options)
};
