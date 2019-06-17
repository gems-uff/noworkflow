#!/bin/bash -x
pwd
cd $1
now dataflow $2 -b >$3
dot -T pdf $3 -o $4
pwd