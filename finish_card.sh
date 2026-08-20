#!/bin/sh
set -e
git add -A
git commit -m "$1"
git push
git log --oneline -3
