#!/usr/bin/env python3
import os
import re
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import argparse

COLORS = {
    "one_bank": "#1B9E77",  # teal-green (excellent for clarity)
    "all_banks": "#D95F02", # warm orange (contrasts teal)
    "baseline": "#7570B3",  # muted violet (neutral baseline)
}
def parse_victim_log_matmult(filepath):
    """Parse matrix multiplication victim log file to extract execution time."""
    try:
        with open(filepath, 'r') as f:
            content = f.read().strip()
            # Extract time from format: "matmult_opt1  7.998469  chsum: 19043.350654"
            match = re.search(r'matmult_opt\d+\s+([\d.]+)\s+chsum:', content)
            if match:
                return float(match.group(1))
    except FileNotFoundError:
        return None
    return None

def parse_victim_log_sdvbs(filepath):
    """Parse SD-VBS victim log file to extract cycles."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            # Extract cycles from format: "Cycles elapsed          - 123383523"
            # Take the last occurrence in case there are multiple runs
            matches = re.findall(r'Cycles elapsed\s+-\s+(\d+)', content)
            if matches:
                # Return the last (most recent) cycle count
                return float(matches[-1])
    except FileNotFoundError:
        return None
    return None

def parse_attacker_log(filepath):
    """Parse attacker log file to extract bandwidth in MB/s."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            # Extract bandwidth from format: "bandwidth 433.77 MB/s"
            match = re.search(r'bandwidth\s+([\d.]+)\s+MB/s', content)
            if match:
                return float(match.group(1))
    except FileNotFoundError:
        return None
    return None

def collect_results_matmult(base_dir):
    """Collect results from matrix multiplication results directory."""
    results = {}
    
    dims = [1024, 2048]
    algos = [0, 1, 2, 3, 4]
    
    for dim in dims:
        for algo in algos:
            test_dir = os.path.join(base_dir, f"dim{dim}_algo{algo}")
            if not os.path.exists(test_dir):
                continue
            
            # Parse victim logs
            solo_time = parse_victim_log_matmult(os.path.join(test_dir, "victim_solo.log"))
            attack_time = parse_victim_log_matmult(os.path.join(test_dir, "victim_with_3_write_attackers.log"))
            
            # Parse attacker logs
            attacker_bandwidths = []
            for core in [1, 2, 3]:
                bw = parse_attacker_log(os.path.join(test_dir, f"log-attack-core{core}.log"))
                if bw is not None:
                    attacker_bandwidths.append(bw)
            
            # Calculate slowdown and aggregate bandwidth
            slowdown = None
            if solo_time and attack_time and solo_time > 0:
                slowdown = attack_time / solo_time
            
            aggregate_bw = sum(attacker_bandwidths) if attacker_bandwidths else None
            
            key = (dim, algo)
            results[key] = {
                'solo_time': solo_time,
                'attack_time': attack_time,
                'slowdown': slowdown,
                'aggregate_bw': aggregate_bw,
                'attacker_bandwidths': attacker_bandwidths
            }
    
    return results

def collect_results_sdvbs(base_dir):
    """Collect results from SD-VBS results directory."""
    results = {}
    
    # Common SD-VBS workloads
    workloads = ["disparity", "mser", "sift", "stitch", "tracking"]
    
    for workload in workloads:
        test_dir = os.path.join(base_dir, workload)
        if not os.path.exists(test_dir):
            continue
        
        # Parse victim logs
        solo_cycles = parse_victim_log_sdvbs(os.path.join(test_dir, "victim_solo.log"))
        attack_cycles = parse_victim_log_sdvbs(os.path.join(test_dir, "victim_with_3_write_attackers.log"))
        
        # Parse attacker logs
        attacker_bandwidths = []
        for core in [1, 2, 3]:
            bw = parse_attacker_log(os.path.join(test_dir, f"log-attack-core{core}.log"))
            if bw is not None:
                attacker_bandwidths.append(bw)
        
        # Calculate slowdown and aggregate bandwidth
        slowdown = None
        if solo_cycles and attack_cycles and solo_cycles > 0:
            slowdown = attack_cycles / solo_cycles
        
        aggregate_bw = sum(attacker_bandwidths) if attacker_bandwidths else None
        
        results[workload] = {
            'solo_cycles': solo_cycles,
            'attack_cycles': attack_cycles,
            'slowdown': slowdown,
            'aggregate_bw': aggregate_bw,
            'attacker_bandwidths': attacker_bandwidths
        }
    
    return results

def plot_results_matmult(one_bank_results, all_banks_results, output_file='memory_interference_matmult.png'):
    """Create plots comparing one-bank and all-banks results for matrix multiplication."""
    
    dims = [1024, 2048]
    algos = [0, 1, 2, 3, 4]
    
    # Create figure with 2 rows and 2 columns
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Matrix Multiplication', 
                 fontsize=16, fontweight='bold')
    
    # Plot for each dimension
    for dim_idx, dim in enumerate(dims):
        ax_slowdown = axes[dim_idx, 0]
        ax_bandwidth = axes[dim_idx, 1]
        
        # Collect data for this dimension
        one_bank_slowdowns = []
        all_banks_slowdowns = []
        one_bank_bws = []
        all_banks_bws = []
        algo_labels = []
        
        for algo in algos:
            key = (dim, algo)
            algo_labels.append(f'Algo {algo}')
            
            # One bank data
            if key in one_bank_results and one_bank_results[key]['slowdown']:
                one_bank_slowdowns.append(one_bank_results[key]['slowdown'])
                one_bank_bws.append(one_bank_results[key]['aggregate_bw'] or 0)
            else:
                one_bank_slowdowns.append(0)
                one_bank_bws.append(0)
            
            # All banks data
            if key in all_banks_results and all_banks_results[key]['slowdown']:
                all_banks_slowdowns.append(all_banks_results[key]['slowdown'])
                all_banks_bws.append(all_banks_results[key]['aggregate_bw'] or 0)
            else:
                all_banks_slowdowns.append(0)
                all_banks_bws.append(0)
        
        # Plot slowdown
        x = np.arange(len(algos))
        width = 0.35
        
        bars1 = ax_slowdown.bar(x - width/2, one_bank_slowdowns, width, 
                                label='One Bank', color=COLORS["one_bank"], alpha=0.8)
        bars2 = ax_slowdown.bar(x + width/2, all_banks_slowdowns, width, 
                                label='All Banks', color=COLORS["all_banks"], alpha=0.8)
        
        ax_slowdown.set_xlabel('Algorithm', fontsize=11, fontweight='bold')
        ax_slowdown.set_ylabel('Slowdown (with 3 attackers)', fontsize=11, fontweight='bold')
        ax_slowdown.set_title(f'Matrix Dimension {dim}×{dim} - Slowdown', fontsize=12, fontweight='bold')
        ax_slowdown.set_xticks(x)
        ax_slowdown.set_xticklabels(algo_labels)
        ax_slowdown.legend()
        ax_slowdown.grid(axis='y', alpha=0.3, linestyle='--')
        ax_slowdown.axhline(y=1, color='red', linestyle='--', linewidth=1, alpha=0.5)
        ax_slowdown.set_ylim(0, 120)
        
        # Add value labels on bars
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax_slowdown.text(bar.get_x() + bar.get_width()/2., height,
                                   f'{height:.1f}x',
                                   ha='center', va='bottom', fontsize=8)
        
        # Plot aggregate bandwidth
        bars3 = ax_bandwidth.bar(x - width/2, one_bank_bws, width, 
                                 label='One Bank', color=COLORS["one_bank"], alpha=0.8)
        bars4 = ax_bandwidth.bar(x + width/2, all_banks_bws, width, 
                                 label='All Banks', color=COLORS["all_banks"], alpha=0.8)
        
        ax_bandwidth.set_xlabel('Algorithm', fontsize=11, fontweight='bold')
        ax_bandwidth.set_ylabel('Aggregate Attackers B/W (MB/s)', fontsize=11, fontweight='bold')
        ax_bandwidth.set_title(f'Matrix Dimension {dim}×{dim} - Attacker Bandwidth', fontsize=12, fontweight='bold')
        ax_bandwidth.set_xticks(x)
        ax_bandwidth.set_xticklabels(algo_labels)
        ax_bandwidth.legend()
        ax_bandwidth.grid(axis='y', alpha=0.3, linestyle='--')
        ax_bandwidth.set_ylim(0,7000)
        
        # Add value labels on bars
        for bars in [bars3, bars4]:
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax_bandwidth.text(bar.get_x() + bar.get_width()/2., height,
                                    f'{height:.0f}',
                                    ha='center', va='bottom', fontsize=8)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Plot saved as '{output_file}'")

def plot_results_sdvbs(one_bank_results, all_banks_results, output_file='memory_interference_sdvbs.png'):
    """Create plots comparing one-bank and all-banks results for SD-VBS."""
    
    # Get all workloads that exist in either dataset
    all_workloads = sorted(set(list(one_bank_results.keys()) + list(all_banks_results.keys())))
    
    if not all_workloads:
        print("No SD-VBS workloads found!")
        return
    
    # Create figure with 1 row and 2 columns
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('SD-VBS', 
                 fontsize=16, fontweight='bold')
    
    ax_slowdown = axes[0]
    ax_bandwidth = axes[1]
    
    # Collect data
    one_bank_slowdowns = []
    all_banks_slowdowns = []
    one_bank_bws = []
    all_banks_bws = []
    workload_labels = []
    
    for workload in all_workloads:
        workload_labels.append(workload)
        
        # One bank data
        if workload in one_bank_results and one_bank_results[workload]['slowdown']:
            one_bank_slowdowns.append(one_bank_results[workload]['slowdown'])
            one_bank_bws.append(one_bank_results[workload]['aggregate_bw'] or 0)
        else:
            one_bank_slowdowns.append(0)
            one_bank_bws.append(0)
        
        # All banks data
        if workload in all_banks_results and all_banks_results[workload]['slowdown']:
            all_banks_slowdowns.append(all_banks_results[workload]['slowdown'])
            all_banks_bws.append(all_banks_results[workload]['aggregate_bw'] or 0)
        else:
            all_banks_slowdowns.append(0)
            all_banks_bws.append(0)
    
    # Plot slowdown
    x = np.arange(len(all_workloads))
    width = 0.35
    
    bars1 = ax_slowdown.bar(x - width/2, one_bank_slowdowns, width, 
                            label='One Bank', color=COLORS["one_bank"], alpha=0.8)
    bars2 = ax_slowdown.bar(x + width/2, all_banks_slowdowns, width, 
                            label='All Banks', color=COLORS["all_banks"], alpha=0.8)
    
    ax_slowdown.set_xlabel('Workload', fontsize=11, fontweight='bold')
    ax_slowdown.set_ylabel('Slowdown (with 3 attackers)', fontsize=11, fontweight='bold')
    ax_slowdown.set_title('SD-VBS Workloads - Slowdown', fontsize=12, fontweight='bold')
    ax_slowdown.set_xticks(x)
    ax_slowdown.set_xticklabels(workload_labels, rotation=45, ha='right')
    ax_slowdown.legend()
    ax_slowdown.grid(axis='y', alpha=0.3, linestyle='--')
    ax_slowdown.axhline(y=1, color='red', linestyle='--', linewidth=1, alpha=0.5)
    ax_slowdown.set_ylim(0, 120)
    
    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax_slowdown.text(bar.get_x() + bar.get_width()/2., height,
                               f'{height:.1f}x',
                               ha='center', va='bottom', fontsize=8)
    
    # Plot aggregate bandwidth
    bars3 = ax_bandwidth.bar(x - width/2, one_bank_bws, width, 
                             label='One Bank', color=COLORS["one_bank"], alpha=0.8)
    bars4 = ax_bandwidth.bar(x + width/2, all_banks_bws, width, 
                             label='All Banks', color=COLORS["all_banks"], alpha=0.8)
    
    ax_bandwidth.set_xlabel('Workload', fontsize=11, fontweight='bold')
    ax_bandwidth.set_ylabel('Aggregate Attackers B/W (MB/s)', fontsize=11, fontweight='bold')
    ax_bandwidth.set_title('SD-VBS Workloads - Attacker Bandwidth', fontsize=12, fontweight='bold')
    ax_bandwidth.set_xticks(x)
    ax_bandwidth.set_xticklabels(workload_labels, rotation=45, ha='right')
    ax_bandwidth.legend()
    ax_bandwidth.grid(axis='y', alpha=0.3, linestyle='--')
    ax_bandwidth.set_ylim(0, 7000)
    
    # Add value labels on bars
    for bars in [bars3, bars4]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax_bandwidth.text(bar.get_x() + bar.get_width()/2., height,
                                f'{height:.0f}',
                                ha='center', va='bottom', fontsize=8)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Plot saved as '{output_file}'")

def print_summary_matmult(one_bank_results, all_banks_results):
    """Print a summary table of matrix multiplication results."""
    print("\n" + "="*80)
    print("MATRIX MULTIPLICATION RESULTS")
    print("="*80)
    
    dims = [1024, 2048]
    algos = [0, 1, 2, 3, 4]
    
    for dim in dims:
        print(f"\n{'Matrix Dimension: ' + str(dim) + '×' + str(dim):^80}")
        print("-"*80)
        print(f"{'Algo':<8} {'One Bank':<30} {'All Banks':<30}")
        print(f"{'':>8} {'Slowdown':<15} {'Agg. BW (MB/s)':<15} {'Slowdown':<15} {'Agg. BW (MB/s)':<15}")
        print("-"*80)
        
        for algo in algos:
            key = (dim, algo)
            
            one_slowdown = one_bank_results.get(key, {}).get('slowdown') or 0
            one_bw = one_bank_results.get(key, {}).get('aggregate_bw') or 0
            all_slowdown = all_banks_results.get(key, {}).get('slowdown') or 0
            all_bw = all_banks_results.get(key, {}).get('aggregate_bw') or 0
            
            print(f"{algo:<8} {one_slowdown:>10.2f}x     {one_bw:>10.1f}      "
                  f"{all_slowdown:>10.2f}x     {all_bw:>10.1f}")
    
    print("="*80 + "\n")

def print_summary_sdvbs(one_bank_results, all_banks_results):
    """Print a summary table of SD-VBS results."""
    print("\n" + "="*80)
    print("SD-VBS BENCHMARK RESULTS")
    print("="*80)
    
    all_workloads = sorted(set(list(one_bank_results.keys()) + list(all_banks_results.keys())))
    
    print(f"\n{'Workload':<15} {'One Bank':<30} {'All Banks':<30}")
    print(f"{'':>15} {'Slowdown':<15} {'Agg. BW (MB/s)':<15} {'Slowdown':<15} {'Agg. BW (MB/s)':<15}")
    print("-"*80)
    
    for workload in all_workloads:
        one_slowdown = one_bank_results.get(workload, {}).get('slowdown') or 0
        one_bw = one_bank_results.get(workload, {}).get('aggregate_bw') or 0
        all_slowdown = all_banks_results.get(workload, {}).get('slowdown') or 0
        all_bw = all_banks_results.get(workload, {}).get('aggregate_bw') or 0
        
        print(f"{workload:<15} {one_slowdown:>10.2f}x     {one_bw:>10.1f}      "
              f"{all_slowdown:>10.2f}x     {all_bw:>10.1f}")
    
    print("="*80 + "\n")

def main():
    parser = argparse.ArgumentParser(description='Plot memory interference results')
    parser.add_argument('--benchmark', choices=['matmult', 'sdvbs'], required=True,
                       help='Benchmark type: matmult or sdvbs')
    parser.add_argument('--one-bank-dir', default='one-bank-results',
                       help='Directory for one-bank results')
    parser.add_argument('--all-banks-dir', default='all-banks-results',
                       help='Directory for all-banks results')
    parser.add_argument('--output', 
                       help='Output filename (default: memory_interference_<benchmark>.png)')
    
    args = parser.parse_args()
    
    # Set default output filename
    if args.output is None:
        args.output = f'memory_interference_{args.benchmark}.png'
    
    # Check if directories exist
    if not os.path.exists(args.one_bank_dir):
        print(f"Error: Directory '{args.one_bank_dir}' not found!")
        return
    
    if not os.path.exists(args.all_banks_dir):
        print(f"Error: Directory '{args.all_banks_dir}' not found!")
        return
    
    if args.benchmark == 'matmult':
        # Matrix multiplication
        print("Collecting matrix multiplication results from one-bank-results...")
        one_bank_results = collect_results_matmult(args.one_bank_dir)
        
        print("Collecting matrix multiplication results from all-banks-results...")
        all_banks_results = collect_results_matmult(args.all_banks_dir)
        
        print_summary_matmult(one_bank_results, all_banks_results)
        
        print("Generating plots...")
        plot_results_matmult(one_bank_results, all_banks_results, args.output)
        
    elif args.benchmark == 'sdvbs':
        # SD-VBS
        print("Collecting SD-VBS results from one-bank-results...")
        one_bank_results = collect_results_sdvbs(args.one_bank_dir)
        
        print("Collecting SD-VBS results from all-banks-results...")
        all_banks_results = collect_results_sdvbs(args.all_banks_dir)
        
        print_summary_sdvbs(one_bank_results, all_banks_results)
        
        print("Generating plots...")
        plot_results_sdvbs(one_bank_results, all_banks_results, args.output)

if __name__ == "__main__":
    main()
