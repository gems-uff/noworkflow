import { HierarchyPointNode as d3_HierarchyPointNode } from 'd3-hierarchy';

export interface ITrialNodeData {
  activations: { [trial: string]: number }[];
  children: ITrialNodeData[];
  children_index: number; // Position in parent list
  duration: { [trial: string]: number };
  full_tooltip: boolean;
  name: string;
  tooltip: { [trial: string]: string };
  trial_ids: number[];

  // Do not use it
  index: number; // Represents parent index in preorder list
  caller_id: number; // Represents activation id
  parent_index: number; // Represents parent index in preorder list
  repr?: string; // Represents structure repr in structure summarization

  // Other
  x0?: number;
  y0?: number;
}

export interface ITrialEdgeData {
  count: { [trial: string]: number };
  source: number;
  target: number;
  type: number;
}

export interface ITrialGraphData {
  root: ITrialNodeData;
  edges: ITrialEdgeData[];
  max_duration: { [trial: string]: number };
  min_duration: { [trial: string]: number };
  colors: { [trial: string]: number };
  trial1: number;
  trial2: number;
}

export interface IVisibleTrialNode extends d3_HierarchyPointNode<ITrialNodeData> {
  _children?: d3_HierarchyPointNode<ITrialNodeData>[];
  children?: this[];
  dy?: number;
  x0?: number;
  y0?: number;
}

export interface IVisibleTrialEdge {
  count: { [trial: string]: string };
  source: IVisibleTrialNode;
  target: IVisibleTrialNode;
  type: string;
  id: string;
}

export interface IActivationData {
  id: string;
  hash: string;
  name: string;
  line: number;
  parameters: string[];
  globals: string[];
  return_value: string;
  duration: string;
  start: string;
  finish: string;
}
