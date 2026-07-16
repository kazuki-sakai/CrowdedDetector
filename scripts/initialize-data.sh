#!/usr/bin/env sh
set -eu

data_dir="${1:-backend/data}"
mkdir -p "$data_dir/each" "$data_dir/backup"
if [ ! -f "$data_dir/ID_name.csv" ]; then
  printf 'id,room_name,updated_at\n' > "$data_dir/ID_name.csv"
fi
if [ ! -f "$data_dir/crowded.csv" ]; then
  printf 'id,person_count,observed_at\n' > "$data_dir/crowded.csv"
fi
echo "CSV data directory initialized at $data_dir"

