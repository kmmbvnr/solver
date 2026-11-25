#!/bin/sh
# Build the KHE step against the pinned GOAL distribution and system Expat.
set -eu
source_dir=$1/stt_heur/stt_heur/khe
output=$2
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
# The upstream null-node guard in this pointer-returning function has a bare return.
sed '/if (node==NULL)/{n;s/return;/return NULL;/;}' "$source_dir/khe_node.c" > "$work/khe_node.c"
set -- "$work/khe_node.c"
for source in "$source_dir"/*.c; do
    if [ "${source##*/}" != khe_node.c ]; then set -- "$@" "$source"; fi
done
cc -std=gnu99 -O2 -I"$source_dir" "$(dirname "$0")/khe_step.c" "$@" -lexpat -lm -o "$output"
