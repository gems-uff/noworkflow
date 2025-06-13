import { Widget } from '@phosphor/widgets';
import { Selection as d3_Selection, BaseType as d3_BaseType } from 'd3-selection';
export declare class ConfigWidget extends Widget {
    d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
    static createNode(): HTMLElement;
    constructor();
    showTrial(): boolean;
    showInfo(): boolean;
    graphType(): string;
    useCache(): boolean;
}
