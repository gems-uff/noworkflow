import {
  BaseType as d3_BaseType,
  Selection as d3_Selection,
} from 'd3-selection';

import {TrialGraph} from './graph';
import {VisibleTrialNode} from './structures';


export
interface TrialConfig {
  customSize: (g:TrialGraph) => number[];
  customMouseOver: (g:TrialGraph, d: VisibleTrialNode) => boolean;
  customMouseOut: (g:TrialGraph, d: VisibleTrialNode) => boolean;
  customForm: (g: TrialGraph, form: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>) => void;
  customLoadTooltip: (g: TrialGraph, div: HTMLDivElement, text: string, trialid: string, aid: string) => void;

  duration: number;

  top: number;
  right: number;
  bottom: number;
  left: number;

  width: number;
  height: number;

  useTooltip: boolean;
  fontSize: number;
  labelFontSize: number;

  nodeSizeX: number;
  nodeSizeY: number;

  queryTooltip: boolean;
}
