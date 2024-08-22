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

cd ../nowvis
npm link @noworkflow/utils
npm link @noworkflow/trial
npm link @noworkflow/history
npm install
npm run build

cd ../labextension
npm link @noworkflow/utils
npm link @noworkflow/trial
npm link @noworkflow/history
jlpm
jlpm build
jupyter labextension link .
jlpm build
jupyter lab build
