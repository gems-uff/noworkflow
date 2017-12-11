import {
  BaseType as d3_BaseType,
  Selection as d3_Selection,
} from 'd3-selection';

import {HistoryGraph} from './graph';
import {VisibleHistoryNode} from './structures';


export
interface HistoryConfig {
  customSelectNode: (g: HistoryGraph, d: VisibleHistoryNode) => boolean;
  customCtrlClick: (g: HistoryGraph, d: VisibleHistoryNode) => boolean;
  customSize: (g: HistoryGraph) => number[];
  customForm: (g: HistoryGraph, form: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>) => void;

  hintMessage: string;

  width: number;
  height: number;

  radius: number;
  moveX: number;
  moveY: number;
  moveY2: number;
  spacing: number;
  margin: number;

  fontSize: number;
  useTooltip: boolean;
}

export
interface HistoryState {
  selectedNode: VisibleHistoryNode | null;
  mouseDownNode: VisibleHistoryNode | null;
  justScale: boolean;
}
