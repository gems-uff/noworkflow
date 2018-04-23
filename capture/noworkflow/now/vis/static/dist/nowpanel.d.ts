import { DockPanel, Widget, DockLayout } from '@phosphor/widgets';
export interface VisWidget extends Widget {
    nowVis?: string;
}
export interface FindResult {
    area: DockLayout.AreaConfig | null;
    index: number;
}
export declare function findInLayout(area: DockLayout.AreaConfig | null, widget: Widget): FindResult | null;
export declare class NowVisPanel extends DockPanel {
    addMainWidget(widget: Widget, options?: DockLayout.IAddOptions): void;
    addGraphWidget(widget: Widget, options?: DockLayout.IAddOptions): void;
    addInfoWidget(widget: Widget, options?: DockLayout.IAddOptions): void;
}
