#!/bin/sh

#set -e; 
for i in {0..5}; do echo hello $((i+1)) && sleep 0.5; done; 
ls -l /root; 
#exit -1
for i in {0..500}; do echo hello $((i+1)) && sleep 0.5; done

