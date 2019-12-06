import { Selection as d3_Selection, BaseType as d3_BaseType } from 'd3-selection';
import { BaseActivationGraphWidget } from './base_activation_graph';
export declare class DiffGraphWidget extends BaseActivationGraphWidget {
    static url(trial1: string, trial2: string, selectedGraph: string, useCache: boolean): string;
    static createForm(name: string, parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>): void;
    constructor(name: string, cls: string, t1: string, t2: string);
    load(selectedGraph?: string, useCache?: boolean): void;
}
