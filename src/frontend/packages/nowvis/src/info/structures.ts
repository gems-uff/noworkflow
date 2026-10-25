import {
  Selection as d3_Selection,
  BaseType as d3_BaseType
} from 'd3-selection';

export interface IModuleData {
  name: string;
  version: string;
  path: string;
  code_hash: string;
  code_block_id?: string;
  id?: number;
  transformed?: boolean;
  trial_id?: number;
}

export interface IModuleListData {
  all: IModuleData[];
  trial_path: string;
}

export interface IEnvironmentItemData {
  name: string;
  value: string;
}

export interface IEnvironmentData {
  all: IEnvironmentItemData[];
}

export interface IFileAccessData {
  name: string;
  mode: string;
  buffering: string;
  timestamp: string;
  content_hash_before: string;
  content_hash_after: string;
  stack: string;
  activation_id?: number;
  trial_id?: number;
}

export interface IFileAccessListData {
  file_accesses: IFileAccessData[];
  trial_path: string;
}

export interface ITrialInfoData {
  id?: string;
  display?: string;
  code_hash?: string;
  script?: string;
  start?: string;
  finish?: string;
  duration_text?: string;
  arguments?: string;
}

export interface IDiffInfoData {
  trial1: ITrialInfoData;
  trial2: ITrialInfoData;
  trial: ITrialInfoData;
}

export interface IDiffModuleData {
  modules_added: IModuleData[];
  modules_removed: IModuleData[];
  modules_replaced: IModuleData[][];
  t1_path: string;
  t2_path: string;
}

export interface IDiffEnvironmentData {
  env_added: IEnvironmentItemData[];
  env_removed: IEnvironmentItemData[];
  env_replaced: IEnvironmentItemData[][];
}

export interface IDiffAccessData {
  fa_added: IFileAccessData[];
  fa_removed: IFileAccessData[];
  fa_replaced: IFileAccessData[][];
  t1_path: string;
  t2_path: string;
}

export interface IFilterObject {
  filterdiv: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>;
  valid: any;
  on_change: (filterfn: () => void) => void;
}
