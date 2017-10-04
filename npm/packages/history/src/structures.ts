export
interface HistoryNodeData {
  id: number;
  display: string;
  parent_id: number;
  level: number;
  script: string;
  status: string;
  tooltip: string;
  str_start?: string;
  str_finish?: string;
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
interface HistoryEdgeData {
  level: number;
  right: number;
  source: number;
  target: number;
}

export
interface HistoryGraphData {
  edges: HistoryEdgeData[];
  nodes: HistoryNodeData[];
  scripts: string[];
}

export
interface VisibleHistoryNode {
  id: number;
  x: number;
  y: number;
  title: string;
  display: string;
  info: HistoryNodeData;
  tooltip: string;
  radius: number;
  gradient: boolean;
  trials?: HistoryNodeData[];
}

export
interface VisibleHistoryEdge {
  id: string;
  level: number;
  right: number;
  source: VisibleHistoryNode;
  target: VisibleHistoryNode;
}