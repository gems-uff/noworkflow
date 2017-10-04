import {
  TrialNodeData, TrialEdgeData
} from './structures';

export
class CallerMap {

  data: { [key: string]: number[]; };
  nodes: TrialNodeData[];
  edges: TrialEdgeData[];

  constructor(nodes: TrialNodeData[], edges: TrialEdgeData[]) {
    this.data = {};
    this.nodes = nodes;
    this.edges = edges;
  }

  insert(key: string, value: number): void {
    if (this.data[key] == undefined) {
      this.data[key] = [];
    }
    this.data[key].push(value);
  }

  get(key: string): number[] {
    return this.data[key];
  }

  populate(): TrialNodeData | null{
    let rootnode: TrialNodeData | null = null;
    for (var node of this.nodes) {
      if (node.parent_index != null) {
        this.insert(node.parent_index.toString(), node.index);
      } else {
        rootnode = node;
      }
    }
    return rootnode;
  }

  buildTree(root: TrialNodeData): TrialNodeData {
    if ((root == undefined) || (root.children != undefined)) return root;

    root.children = [];
    let children_ids = this.get(root.index.toString());

    if (children_ids == undefined) return root;

    for (var node_id of children_ids) {
      root.children.push(this.buildTree(this.nodes[node_id]));
    }

    root.children.sort((a, b) => {
      if (a.graph == undefined) {
        return b.index - a.index;
      }
      if (a.graph == b.graph) {
        if (a.graph == 0) {
          return b.node1.original - a.node1.original;
        }
        return b.node.original - a.node.original;
      } else {
        if (a.graph == 0) {
          return b.node.original - (b.graph == 1? a.node1 : a.node2).original;
        } else if (b.graph == 0) {
          return (a.graph == 1? b.node1 : b.node2).original - a.node.original;
        }
      }
      return -1
    });

    root.children.forEach((n, i) => {
      n.children_index = i;
    });
    return root;
  }
}
