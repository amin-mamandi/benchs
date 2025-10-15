#!/bin/bash
set -euo pipefail

# clear existing hugepages (ignore if path missing)
echo 0 | sudo tee /sys/devices/system/node/node0/hugepages/hugepages-32768kB/nr_hugepages 2>/dev/null || true
echo 0 | sudo tee /sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages 2>/dev/null || true

# try 32 MB hugepages
echo 64 | sudo tee /sys/devices/system/node/node0/hugepages/hugepages-32768kB/nr_hugepages >/dev/null 2>&1 || true

# fallback: if 32MB not supported, try 2MB
if [ -f /sys/devices/system/node/node0/hugepages/hugepages-32768kB/nr_hugepages ]; then
  if [ "$(cat /sys/devices/system/node/node0/hugepages/hugepages-32768kB/nr_hugepages)" -eq 0 ]; then
    echo 256 | sudo tee /sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages >/dev/null
  fi
fi

# mount hugetlbfs if not mounted
[ -d /mnt/huge ] || sudo mkdir -p /mnt/huge
if ! mountpoint -q /mnt/huge; then
  if [ -f /sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages ] && \
     [ "$(cat /sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages)" -gt 0 ]; then
    sudo mount -t hugetlbfs -o pagesize=2M none /mnt/huge
  else
    sudo mount -t hugetlbfs -o pagesize=32M none /mnt/huge
  fi
fi

# set CPU governor and freq
if [ -d /sys/devices/system/cpu ]; then
  if [ -r /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq ]; then
    MAX_FREQ=$(cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq)
  else
    MAX_FREQ=""
  fi

  for cpu in /sys/devices/system/cpu/cpu[0-9]*; do
    gov="$cpu/cpufreq/scaling_governor"
    minf="$cpu/cpufreq/scaling_min_freq"
    maxf="$cpu/cpufreq/scaling_max_freq"

    [ -w "$gov" ] && echo performance | sudo tee "$gov" >/dev/null
    if [ -n "$MAX_FREQ" ]; then
      [ -w "$minf" ] && echo "$MAX_FREQ" | sudo tee "$minf" >/dev/null
      [ -w "$maxf" ] && echo "$MAX_FREQ" | sudo tee "$maxf" >/dev/null
    fi
  done
fi

# disable Intel turbo (if exists)
[ -w /sys/devices/system/cpu/intel_pstate/no_turbo ] && \
  echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo >/dev/null

# disable SMT (if supported)
# [ -w /sys/devices/system/cpu/smt/control ] && \
#   echo off | sudo tee /sys/devices/system/cpu/smt/control >/dev/null
