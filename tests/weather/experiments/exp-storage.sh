#!/bin/sh
echo 'Removing previous runs'
rm -rf .noworkflow

for i in {1..1000}
do
   echo "$i run"
   now run simulation.py data1.dat data2.dat
   du -hs .noworkflow/db.sqlite >> dbsize.txt
   du -hs .noworkflow/content/ >> contentsize.txt
done