import { Selection as d3_Selection, BaseType as d3_BaseType } from 'd3-selection';
import { Widget } from '@phosphor/widgets';
import { TrialGraph, TrialGraphData } from '@noworkflow/trial';
export declare class BaseActivationGraphWidget extends Widget {
    name: string;
    cls: string;
    t1: string;
    t2: string;
    graph: TrialGraph;
    d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
    static graphTypeForm(name: string, selectorDiv: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>): void;
    static useCacheForm(name: string, selectorDiv: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>): void;
    static createNode(name: string, fn?: (name: string, parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>) => void): HTMLElement;
    setGraph(data: TrialGraphData, config?: any): void;
    configureGraph(selectedGraph: string | undefined, useCache: boolean | undefined, genDataflow: boolean | undefined, data: TrialGraphData): void;
    protected onResize(msg: Widget.ResizeMessage): void;
}
