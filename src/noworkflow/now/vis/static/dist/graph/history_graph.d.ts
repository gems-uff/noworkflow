import { Selection as d3_Selection, BaseType as d3_BaseType } from 'd3-selection';
import { Widget } from '@phosphor/widgets';
import { HistoryGraph, HistoryGraphData } from '@noworkflow/history';
import { ConfigWidget } from '../config_widget';
export declare class HistoryWidget extends Widget {
    name: string;
    expId: string;
    cls: string;
    graph: HistoryGraph;
    d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
    config: ConfigWidget;
    static url(script?: string, execution?: string, summarize?: boolean): string;
    static createNode(): HTMLElement;
    constructor(config: ConfigWidget, name: string, cls: string, expId: string);
    setGraph(data: HistoryGraphData, config?: any): void;
    load(script?: string, execution?: string, summarize?: boolean): void;
    protected onResize(msg: Widget.ResizeMessage): void;
}
