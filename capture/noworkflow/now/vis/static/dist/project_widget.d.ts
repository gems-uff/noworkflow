import { Widget } from '@phosphor/widgets';
import '../style/bootstrap.min.css';
import { Selection as d3_Selection, BaseType as d3_BaseType } from 'd3-selection';
interface IExperiment {
    id: string;
    name: string;
    description: string;
}
export declare class ProjectWidget extends Widget {
    d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
    expTBody: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
    successFeedback: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
    errorFeedback: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
    experiments: Array<IExperiment>;
    static createNode(): HTMLElement;
    constructor(experiments: Array<IExperiment>);
    addExpRow(exp: IExperiment): void;
    addFormInput(form: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, fieldId: string, fieldLabel: string, fieldType: string): d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
    addFeedBackinfo(baseNode: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, cls: string, txt: string, desc: string): d3_Selection<HTMLDivElement, {}, HTMLElement | null, any>;
    hideNode(node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>): void;
    showNode(node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>): void;
    setNode(): void;
}
export {};
