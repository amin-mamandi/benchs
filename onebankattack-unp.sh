#!/bin/bash

# Base directories
SDVBS_DIR="/home/nvidia/sd-vbs/vision/benchmarks"
MATMULT_DIR="/home/nvidia/matmult"
LLAMA_DIR="/home/nvidia/llama.cpp/build/bin"
MODEL_PATH="/home/nvidia/model/Llama-3.2-3b-instruct-q8_0.gguf"

MAP_FILE="/home/nvidia/IsolBench/bench/map.txt"

# number of attackers
ATTACKER_COUNT=3
# cores to use for attackers
ATTACKER_CORES=(1 2 3)

WORKLOADS=("disparity" "mser" "sift" "stitch" "tracking")
# WORKLOADS=("disparity")

run_attackers() {
    local attk=$1
    local test_dir=$2

    attacker_pids=()
    for idx in $(seq 0 $((ATTACKER_COUNT-1))); do
        core=${ATTACKER_CORES[$idx]:-$(($idx + 1))}
        log="$test_dir/log-${attk}-attack-core${core}.log"
        # start attacker in background; adjust 'pll' args if needed
        pll -f "$MAP_FILE" -c "$core" -l 22 -m 256 -i 1000000000 -a "$attk" -u 64 -e 0 >& "$log" &
        pid=$!
        attacker_pids+=("$pid")
        echo "Started attacker on core $core with PID: $pid (log: $log)"
    done

    n_attackers=${#attacker_pids[@]}
    echo "All $n_attackers attackers started: PIDs ${attacker_pids[*]}"
    sleep 20
}

run_unp_attackers() {
	
    local attk="$1"
    local test_dir="$2"

    # where the binary lives
    local bin="/home/nvidia/drama/re/onebank_attacker"
    if [[ ! -x "$bin" ]]; then
        echo "ERROR: attacker binary not found or not executable: $bin" >&2
        return 1
    fi

    local log="$test_dir/log-${attk}-unp.log"
    local pid

    # start attacker in background and capture PID
    "$bin" -a "$attk" -c 1 -m 1024 -r 10 -k 1024 -s 256 -n 3 -t 13 &> "$log" &
    pid=$!
    
    sleep 180 
}

# run matrix victim
run_matrix_victim() {
    local dim=$1
    local algo=$2
    # adapt taskset/core binding as desired
    taskset -c 0 "$MATMULT_DIR/matrix" -n "$dim" -a "$algo"
}

# run sd-vbs victim helper
run_victim() {
    local workload=$1

    # Use 'cif' for localization and svm, otherwise 'fullhd'
    local res_dir="fullhd"
    case "$workload" in
        localization|svm) res_dir="cif" ;;
    esac

    local input_dir="$SDVBS_DIR/$workload/data/$res_dir"
    local exec="$SDVBS_DIR/$workload/data/$res_dir/$workload"

    echo "running victim: $workload (input dir: $input_dir) ..."
    taskset -c 0 "$exec" "$input_dir"
}

# run llama-bench victim
run_llama_victim() {
    local exec="$LLAMA_DIR/llama-bench"
    echo "running llama-bench (model: $MODEL_PATH) ..."
    # bind to core 0 like other victims
    taskset -c 0 "$exec" -C 0 -pg 512,128 -m "$MODEL_PATH" -t 1 --progress -r 1
}

# kill attackers
kill_attackers() {
    for p in "${attacker_pids[@]:-}"; do
        if kill -2 "$p" 2>/dev/null; then
            echo "Sent SIGINT to PID $p"
        else
            echo "SIGINT failed for PID $p, trying SIGKILL"
            kill -9 "$p" 2>/dev/null || true
        fi
    done

    killall -2 onebank_attacker
    # give them a moment to terminate
    sleep 3
}

# Argument parsing: expect matmult or sdvbs or llama
if [ "${1-}" = "matmult" ]; then

    RESULTS_DIR="matmult-onebank-unp-results"
    mkdir -p "$RESULTS_DIR"

    for dim in 1024 2048; do
        for algo in 0 1 2 3 4; do
            TEST_DIR="$RESULTS_DIR/dim${dim}_algo${algo}"
            mkdir -p "$TEST_DIR"

            for attk in "write" "read"; do
                run_unp_attackers "$attk" "$TEST_DIR"

                # Run victim once while all attackers run
                victim_log="$TEST_DIR/victim_with${n_attackers}_${attk}_attackers.log"
                echo "running matrix victim (dim=$dim algo=$algo) under $n_attackers attackers..."
                run_matrix_victim "$dim" "$algo" 2>&1 | tee -a "$victim_log" || true

                # Kill attackers and run solo victim
                kill_attackers

                echo "solo run for dim $dim algo $algo"
                victim_log="$TEST_DIR/victim_solo.log"
                run_matrix_victim "$dim" "$algo" 2>&1 | tee -a "$victim_log" || true
            done
        done
    done

    echo "All matmult results saved in: $RESULTS_DIR"

elif [ "${1-}" = "sdvbs" ]; then
    
    RESULTS_DIR="sdvbs-onebank-unp-results"
    mkdir -p "$RESULTS_DIR"

    for workload in "${WORKLOADS[@]}"; do
        echo ">>> Running workload: $workload"
        TEST_DIR="$RESULTS_DIR/$workload"
        mkdir -p "$TEST_DIR"

        for attk in "write" "read"; do
            run_unp_attackers "$attk" "$TEST_DIR"

            victim_log="$TEST_DIR/victim_with${n_attackers}_${attk}_attackers.log"
            echo "running victim ($workload) with $n_attackers attackers doing $attk"
            run_victim "$workload" 2>&1 | tee -a "$victim_log" || true

            kill_attackers

            # Solo run (no attackers)
            echo "solo run for $workload"
            victim_log="$TEST_DIR/victim_solo.log"
            run_victim "$workload" 2>&1 | tee -a "$victim_log" || true
        done
    done

    echo "All sd-vbs results saved in: $RESULTS_DIR"

elif [ "${1-}" = "llama" ]; then

    RESULTS_DIR="llama-onebank-unp-results"
    mkdir -p "$RESULTS_DIR"

    # single TEST_DIR for llama runs
    TEST_DIR="$RESULTS_DIR/run"
    mkdir -p "$TEST_DIR"

    for attk in "write" "read"; do
        run_unp_attackers "$attk" "$TEST_DIR"

        victim_log="$TEST_DIR/victim_with${n_attackers}_${attk}_attackers.log"
        echo "running victim (llama-bench) with $n_attackers attackers doing $attk"
        run_llama_victim 2>&1 | tee -a "$victim_log" || true

        kill_attackers

        # Solo run (no attackers)
        echo "solo run for llama-bench"
        victim_log="$TEST_DIR/victim_solo.log"
        run_llama_victim 2>&1 | tee -a "$victim_log" || true
    done

else
    echo "Usage: $0 {matmult|sdvbs|llama}"
    exit 1
fi
