#!/bin/bash 

cd $1
now dataflow $2 >$3
dot -T pdf $3 -o $4
