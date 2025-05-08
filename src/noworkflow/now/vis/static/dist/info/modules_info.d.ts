import { Selection as d3_Selection, BaseType as d3_BaseType } from 'd3-selection';
import { Widget } from '@phosphor/widgets';
import { ModuleData, FilterObject } from './structures';
export declare class ModulesInfoWidget extends Widget {
    d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
    static url(trialId: string): string;
    static createFilterDiv(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>): d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>;
    static createFilter(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, default_local?: string): FilterObject;
    static createList(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, data: ModuleData[], trial_path: string, default_local?: string): FilterObject;
    static createNode(trialDisplay: string, data: ModuleData[], trial_path: string): HTMLElement;
    constructor(trialDisplay: string, data: ModuleData[], trial_path: string);
}
