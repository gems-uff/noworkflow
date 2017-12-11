cd packages/utils
npm install
npm run build
npm link

cd ../trial
npm link @noworkflow/utils
npm install
npm run build
npm link

cd ../history
npm link @noworkflow/utils
npm install
npm run build
npm link

cd ../nbextension
npm link @noworkflow/utils
npm link @noworkflow/trial
npm link @noworkflow/history
npm install
npm run build

cd ../nowvis
npm link @noworkflow/utils
npm link @noworkflow/trial
npm link @noworkflow/history
npm install
npm run build