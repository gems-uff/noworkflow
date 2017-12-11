export
interface ModuleData {
  name: string;
  version: string;
  path: string;
  code_hash: string;
  code_block_id?: string;
  id?: number;
  transformed?: boolean;
  trial_id?: number;
}

export
interface ModuleListData {
  local: ModuleData[];
  all: ModuleData[];
}

export
interface EnvironmentData {
  env: { [key: string]: string };
}

export
interface EnvironmentItemData {
  name: string;
  value: string;
}


export
interface FileAccessData {
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

export
interface FileAccessListData {
  file_accesses: FileAccessData[];
}

export
interface TrialInfoData {
  id?: string;
  display?: string;
  code_hash?: string;
  script?: string;
  start?: string;
  finish?: string;
  duration_text?: string;
  arguments?: string;
}

export
interface DiffInfoData {
  trial1: TrialInfoData;
  trial2: TrialInfoData;
  trial: TrialInfoData;
}

export
interface DiffModuleData {
  modules_added: ModuleData[];
  modules_removed: ModuleData[];
  modules_replaced: ModuleData[][];
}

export
interface DiffEnvironmentData {
  env_added: EnvironmentItemData[];
  env_removed: EnvironmentItemData[];
  env_replaced: EnvironmentItemData[][];
}

export
interface DiffAccessData {
  fa_added: FileAccessData[];
  fa_removed: FileAccessData[];
  fa_replaced: FileAccessData[][];
}