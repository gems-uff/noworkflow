import {
  BaseType as d3_BaseType,
  Selection as d3_Selection
} from 'd3-selection';

import { HistoryGraph } from './graph';
import { IVisibleHistoryNode } from './structures';

export interface IHistoryConfig {
  customSelectNode: (g: HistoryGraph, d: IVisibleHistoryNode) => boolean;
  customCtrlClick: (g: HistoryGraph, d: IVisibleHistoryNode) => boolean;
  customSize: (g: HistoryGraph) => number[];
  customForm: (
    g: HistoryGraph,
    form: d3_Selection<d3_BaseType, unknown, HTMLElement | null, any>
  ) => void;
  customWindowTabCommand: (
    trialIdSimplified: string,
    trialId: string,
    command: string
  ) => boolean;

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

export interface IHistoryState {
  selectedNode: IVisibleHistoryNode | null;
  mouseDownNode: IVisibleHistoryNode | null;
  justScale: boolean;
}
