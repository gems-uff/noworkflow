import { Selection as d3_Selection, BaseType as d3_BaseType } from 'd3-selection';
import { Widget } from '@phosphor/widgets';
import { EnvironmentItemData, FilterObject } from './structures';
export declare class EnvironmentInfoWidget extends Widget {
    d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
    static url(trialId: string): string;
    static createItem(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, key: string, value: string): void;
    static createFilterDiv(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>): d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>;
    static createFilter(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, default_local?: string): FilterObject;
    static createList(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, data: EnvironmentItemData[], default_local?: string): FilterObject;
    static createNode(trialDisplay: string, data: EnvironmentItemData[], default_local?: string): HTMLElement;
    constructor(trialDisplay: string, data: EnvironmentItemData[], default_local?: string);
}
