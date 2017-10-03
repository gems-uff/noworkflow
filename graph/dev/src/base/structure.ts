export
interface TrialEdgeData {
  count: number | { [trial: string]: number; }[];
  source: number;
  target: number;
  trial?: number;
  type: number;
}

export
interface TrialNodeInfoData {
  count: number;
  diff?: number;
  duration: number;
  finished: boolean;
  info: string;
  level: number;
  line: number;
  mean: number;
  original?: number;
  trial_id: number;
}

export
interface TrialNodeData {
  graph?: number;
  caller_id: number;
  parent_index: number;
  index: number;
  name: string;
  node?: TrialNodeInfoData;
  node1?: TrialNodeInfoData;
  node2?: TrialNodeInfoData;
  repr: string;

  children?: TrialNodeData[];
  x0?: number;
  y0?: number;
  children_index?: number;
}

export
interface TrialGraphData {
  nodes: TrialNodeData[];
  edges: TrialEdgeData[];
  max_duration: { [trial: string]: number; };
  min_duration: { [trial: string]: number; };
}

export
interface MultiGraphData {
  diff: TrialGraphData;
  trial1: TrialGraphData;
  trial2: TrialGraphData;
}

export
interface HistoryEdgeData {
  level: number;
  right: number;
  source: number;
  target: number;
}

export
interface HistoryNodeData {
  id: number;
  display: string;
  parent_id: number;
  level: number;
  script: string;
  status: string;
  tooltip: string;
  code_hash?: string;
  command?: string;
  duration_text?: string;
  finish?: string;
  main_id?: number;
  modules_inherited_from_trial_id?: number;
  path?: string;
  start?: string;
  arguments?: string;
  trials?: HistoryNodeData[];
}

export
interface HistoryGraphData {
  edges: HistoryEdgeData[];
  nodes: HistoryNodeData[];
  scripts: string[];
}


export
interface DependencyData {
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
interface DependencyListData {
  local: DependencyData[];
  all: DependencyData[];
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
