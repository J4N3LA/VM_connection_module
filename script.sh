#!/bin/sh

#set -e; 
for i in {0..5}; do echo hello $((i+1)) && sleep 0.5; done; 
ls -l /root; 
for i in {0..100}; do echo hello $((i+1)) && sleep 0.5; done

