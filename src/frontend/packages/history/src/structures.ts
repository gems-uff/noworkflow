/**
 * IHistoryNodeData represents either a trial or a summarized version node
 * Some attributes exist only when it is a trial
 */
export interface IHistoryNodeData {
  /* Shared attribute */
  id: number;
  display: string;
  parent_id: number;
  level: number;
  status: string;

  /* Only when IHistoryNodeData acts as a summarized node */
  trials?: IHistoryNodeData[];
}

export interface IHistoryTrialNodeData extends IHistoryNodeData {
  /* Trial attributes */
  script: string;
  command: string;
  path: string;
  status: string;
  modules_inherited_from_trial_id: number;
  main_id: number;

  /* Extra */
  code_hash: string;
  duration_text: string;
  tooltip: string;
  str_start: string;
  str_finish: string;
}

export interface IHistoryEdgeData {
  level: number;
  right: number;
  source: number;
  target: number;
}

export interface IHistoryGraphData {
  edges: IHistoryEdgeData[];
  nodes: IHistoryNodeData[];
  scripts: string[];
  width: number;
  height: number;
}

export interface IVisibleHistoryNode {
  id: number;
  x: number;
  y: number;
  title: string;
  display: string;
  info: IHistoryNodeData;
  radius: number;
  gradient: boolean;
  status: string;

  trials?: IHistoryNodeData[];
  tooltip?: string;
}

export interface IVisibleHistoryEdge {
  id: string;
  level: number;
  right: number;
  source: IVisibleHistoryNode;
  target: IVisibleHistoryNode;
}
