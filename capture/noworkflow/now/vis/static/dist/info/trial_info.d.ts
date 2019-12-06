import { Selection as d3_Selection, BaseType as d3_BaseType } from 'd3-selection';
import { Widget } from '@phosphor/widgets';
import { VisibleHistoryNode } from '@noworkflow/history';
import { FilterObject } from './structures';
export declare class TrialInfoWidget extends Widget {
    d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
    trial: VisibleHistoryNode;
    static createNode(trial: VisibleHistoryNode): HTMLElement;
    constructor(trial: VisibleHistoryNode);
    static createFold(parent: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, title: string): d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>;
    static createFilterFold(fold: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, filter: FilterObject): void;
    loadModules(): void;
    loadEnvironment(): void;
    loadFileAccess(): void;
}
