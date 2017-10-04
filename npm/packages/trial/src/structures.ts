import {
  HierarchyPointNode as d3_HierarchyPointNode,
} from 'd3-hierarchy';

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
  original: number;
  trial_id: number;
}

export
interface TrialNodeData {
  graph?: number;
  caller_id: number;
  parent_index: number;
  index: number;
  name: string;
  node: TrialNodeInfoData;
  node1: TrialNodeInfoData;
  node2: TrialNodeInfoData;
  repr: string;

  children: TrialNodeData[];
  x0?: number;
  y0?: number;
  children_index: number;
}

export
interface TrialEdgeData {
  count: number | { [trial: string]: number; }[];
  source: number;
  target: number;
  trial?: number;
  type: number;
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
interface VisibleTrialNode extends d3_HierarchyPointNode<TrialNodeData> {
  _children: d3_HierarchyPointNode<TrialNodeData>[];
  children: d3_HierarchyPointNode<TrialNodeData>[];
  dy?: number;
  x0?: number;
  y0?: number;
}

export
interface VisibleTrialEdge {
  count: number;
  source: VisibleTrialNode;
  target: VisibleTrialNode;
  trial: number;
  type: string;
  id: string;
}
