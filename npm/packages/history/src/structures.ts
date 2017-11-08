/**
  * HistoryNodeData represents either a trial or a summarized version node
  * Some attributes exist only when it is a trial
  */
export
interface HistoryNodeData {
  /* Shared attribute */
  id: number;
  display: string;
  parent_id: number;
  level: number;

  /* Only when HistoryNodeData acts as a summarized node */
  trials?: HistoryNodeData[];
}

export
interface HistoryTrialNodeData extends HistoryNodeData {
  /* Trial attributes */
  script: string;
  command: string;
  path: string;
  status: string;
  modules_inherited_from_trial_id: number;
  main_id: number;

  /* Extra */
  code_hash:string;
  duration_text: string;
  tooltip: string;
  str_start: string;
  str_finish: string;
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
  width: number;
  height: number;
}

export
interface VisibleHistoryNode {
  id: number;
  x: number;
  y: number;
  title: string;
  display: string;
  info: HistoryNodeData;
  radius: number;
  gradient: boolean;
  status: string;

  trials?: HistoryNodeData[];
  tooltip?: string;
}

export
interface VisibleHistoryEdge {
  id: string;
  level: number;
  right: number;
  source: VisibleHistoryNode;
  target: VisibleHistoryNode;
}