import {
  HierarchyPointNode as d3_HierarchyPointNode,
} from 'd3-hierarchy';

export
interface TrialNodeData {
  activations: { [trial: string]: number; }[];
  children: TrialNodeData[];
  children_index: number; // Position in parent list
  duration: { [trial: string]: number; };
  full_tooltip: boolean;
  name: string;
  tooltip: { [trial: string]: string; };
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

export
interface TrialEdgeData {
  count: { [trial: string]: number; };
  source: number;
  target: number;
  type: number;
}

export
interface TrialGraphData {
  root: TrialNodeData;
  edges: TrialEdgeData[];
  max_duration: { [trial: string]: number; };
  min_duration: { [trial: string]: number; };
  colors: { [trial: string]: number; };
  trial1: number;
  trial2: number;
}

export
interface VisibleTrialNode extends d3_HierarchyPointNode<TrialNodeData> {
  _children?: d3_HierarchyPointNode<TrialNodeData>[];
  children?: d3_HierarchyPointNode<TrialNodeData>[];
  dy?: number;
  x0?: number;
  y0?: number;
}

export
interface VisibleTrialEdge {
  count: { [trial: string]: string; };
  source: VisibleTrialNode;
  target: VisibleTrialNode;
  type: string;
  id: string;
}
