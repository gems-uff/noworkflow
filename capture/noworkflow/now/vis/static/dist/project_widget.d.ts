import { Widget } from '@phosphor/widgets';
import { Selection as d3_Selection, BaseType as d3_BaseType } from 'd3-selection';
interface IExperiment {
    id: string;
    name: string;
}
export declare class ProjectWidget extends Widget {
    d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
    experiments: Array<IExperiment>;
    static createNode(): HTMLElement;
    constructor(experiments: Array<IExperiment>);
    setNode(): void;
}
export {};
