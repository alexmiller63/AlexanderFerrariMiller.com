#!/usr/bin/env bash
# Keep the PDF outside Git, and restore it after each Jekyll rebuild.
set -euo pipefail
cache_dir="${1:?Pass a persistent cache directory outside the Git checkout}"
output_dir="${2:?Pass the published asset directory}"
proof_sha='df9ae609c8e25a8631d573069b7e5d0e366ac5ba2733cf8187b18fe99ea924ce'
proof_source='https://raw.githubusercontent.com/alexmiller63/illuminated-bible-project/4afb0a181a7787e9767e44d5ce8c89e9ad7acf8a/genesis_1_1-10_illuminated_proof_v5.pdf'
proof_file="$cache_dir/genesis-1-proof.pdf"
umask 022
mkdir -p "$cache_dir"
if [ ! -f "$proof_file" ]; then
  temporary_file=$(mktemp "$cache_dir/proof.XXXXXX")
  trap 'rm -f "$temporary_file"' EXIT
  curl --fail --location --retry 3 --connect-timeout 15 --max-time 120 "$proof_source" --output "$temporary_file"
  printf '%s  %s\n' "$proof_sha" "$temporary_file" | sha256sum --check --status
  mv "$temporary_file" "$proof_file"
  trap - EXIT
fi
printf '%s  %s\n' "$proof_sha" "$proof_file" | sha256sum --check --status
mkdir -p "$output_dir"
install -m 644 "$proof_file" "$output_dir/genesis-1-proof.pdf.tmp"
mv "$output_dir/genesis-1-proof.pdf.tmp" "$output_dir/genesis-1-proof.pdf"
printf 'Published verified Genesis 1 PDF proof.\n'
