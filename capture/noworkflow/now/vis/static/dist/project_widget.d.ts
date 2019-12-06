import { Widget } from '@phosphor/widgets';
import { Selection as d3_Selection, BaseType as d3_BaseType } from 'd3-selection';
export declare class ProjectWidget extends Widget {
    d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
    folders: Array<String>;
    static createNode(): HTMLElement;
    constructor(folders: Array<string>);
    setNode(): void;
}
