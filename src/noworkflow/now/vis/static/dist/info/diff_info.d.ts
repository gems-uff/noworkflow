import { Selection as d3_Selection, BaseType as d3_BaseType } from 'd3-selection';
import { Widget } from '@phosphor/widgets';
import { DiffInfoData, FilterObject } from './structures';
export declare class DiffInfoWidget extends Widget {
    d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
    display1: string;
    display2: string;
    static url(trial1: string, trial2: string): string;
    static modules_url(trial1: string, trial2: string): string;
    static environment_url(trial1: string, trial2: string): string;
    static accesses_url(trial1: string, trial2: string): string;
    static createNode(): HTMLElement;
    constructor(display1: string, display2: string, trial1: string, trial2: string);
    load(trial1: string, trial2: string): void;
    createMain(data: DiffInfoData): void;
    filter_trial(filter: FilterObject, filterfn: (strial: number) => void): void;
    loadModules(trial1: string, trial2: string): void;
    loadEnvironment(trial1: string, trial2: string): void;
    loadFileAccess(trial1: string, trial2: string): void;
    private info;
    private mod_li;
    private env_field;
    private env_li;
    private env_cli;
    private fa_field;
    private fa_li;
    private fa_cfield;
}
