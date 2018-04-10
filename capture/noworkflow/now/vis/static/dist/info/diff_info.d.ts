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
    private info(main, cls, label, value1, value2);
    private mod_li(element, cls, mod);
    private env_field(element, env);
    private env_li(element, cls, env);
    private env_cli(element, rem, add);
    private fa_field(element, cls, title, value);
    private fa_li(element, cls, fa);
    private fa_cfield(element, cls, title, v1, v2);
}
