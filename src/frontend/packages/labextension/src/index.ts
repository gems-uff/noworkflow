import { IRenderMime } from '@jupyterlab/rendermime-interfaces';

import '../style/index.css';
import { historyFactory } from './historyrenderer';
import { trialFactory } from './trialrenderer';
import { codeFactory } from './coderenderer';


const TYPES: {
  [key: string]: { name: string; extensions: string[]; factory: IRenderMime.IRendererFactory };
} = {
  'application/noworkflow.history+json': {
    name: 'noWorkflow History',
    extensions: ['.nowhistory'],
    factory: historyFactory
  },
  'application/noworkflow.trial+json': {
    name: 'noWorkflow Trial',
    extensions: ['.nowtrial'],
    factory: trialFactory
  },
  'application/noworkflow.code+json': {
    name: 'noWorkflow Code',
    extensions: ['.nowcode'],
    factory: codeFactory
  }
};


/**
 * Extension definition.
 */
const extensions: IRenderMime.IExtension[] = Object.keys(TYPES).map(k => {
  const { name, factory } = TYPES[k];
  return {
    id: `jupyterlab-noworkflow:${name}`,
    rendererFactory: factory,
    rank: 100,
    dataType: 'json',
    fileTypes: [
      {
        name,
        mimeTypes: [k],
        extensions: TYPES[k].extensions
      }
    ],
    documentWidgetFactoryOptions: {
      name,
      primaryFileType: name,
      fileTypes: [name, 'json'],
      defaultFor: [name]
    }
  } as IRenderMime.IExtension;
});

export default extensions;
