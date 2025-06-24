#!/bin/bash
# read the pbf list and download each file
pbf_list="pbf_list.txt"
if [[ ! -f "$pbf_list" ]]; then
  echo "$(date +'%Y-%m-%d %H:%M:%S') - pbf list not found!" >> download.log
  exit 1
fi
while IFS= read -r file; do
  if [[ -z "$file" || "$file" =~ ^# ]]; then
    continue
  fi
  mkdir -p "$(dirname "$file")"
  echo "$(date +'%Y-%m-%d %H:%M:%S') - Downloading https://download.geofabrik.de/$file" >> download.log
  wget -q "https://download.geofabrik.de/$file" -O "$file"
  if [[ $? -ne 0 ]]; then
    echo "$(date +'%Y-%m-%d %H:%M:%S') - Failed to download $file"  >> download.log
  else
    # output timestamp
    echo "$(date +'%Y-%m-%d %H:%M:%S') - Downloaded $file" >> download.log
  fi
done < "$pbf_list"
echo "$(date +'%Y-%m-%d %H:%M:%S') - All downloads completed." >> download.log
