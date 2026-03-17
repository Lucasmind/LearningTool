#!/bin/bash

# Entrypoint script for llama.cpp containers
# Handles split GGUF files and environment configuration

set -e

echo "================================"
echo "LLMRunner Container Starting"
echo "================================"

# Function to check if model files exist
check_model_files() {
    local model_path="$1"

    if [ -f "$model_path" ]; then
        echo "✓ Found model: $(basename "$model_path")"
        echo "  Size: $(du -h "$model_path" | cut -f1)"
        return 0
    else
        echo "✗ Model not found: $model_path"
        return 1
    fi
}

# Handle split GGUF files
MODEL_ARGS=""
if [ -n "$MODEL_PATH_1" ] && [ -n "$MODEL_PATH_2" ]; then
    echo "Detected split GGUF model configuration"

    if check_model_files "$MODEL_PATH_1" && check_model_files "$MODEL_PATH_2"; then
        MODEL_ARGS="-m $MODEL_PATH_1 -m $MODEL_PATH_2"
        echo "✓ Both model parts verified"
    else
        echo "ERROR: Split model files not found!"
        exit 1
    fi
elif [ -n "$MODEL_PATH" ]; then
    echo "Detected single model configuration"

    if check_model_files "$MODEL_PATH"; then
        MODEL_ARGS="-m $MODEL_PATH"
    else
        echo "ERROR: Model file not found!"
        exit 1
    fi
else
    echo "WARNING: No model path specified, using default"
    MODEL_ARGS="-m /models/model.gguf"
fi

echo ""

# Display GPU backend information
if [ -n "$VULKAN_DEVICE" ]; then
    echo "Backend: Vulkan (Device: $VULKAN_DEVICE)"
    export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/radeon_icd.x86_64.json:/usr/share/vulkan/icd.d/amd_icd64.json
elif [ -n "$ROCM_DEVICE" ]; then
    echo "Backend: ROCm (Device: $ROCM_DEVICE)"
    echo "HSA_OVERRIDE_GFX_VERSION: ${HSA_OVERRIDE_GFX_VERSION:-not set}"
    echo "ROCBLAS_USE_HIPBLASLT: ${ROCBLAS_USE_HIPBLASLT:-not set}"

    # Verify ROCm availability
    if command -v rocminfo &> /dev/null; then
        echo "ROCm devices:"
        rocminfo 2>/dev/null | grep -E "Name:" | head -3 || echo "  Failed to query ROCm devices"
    fi
else
    echo "Backend: CPU (No GPU device specified)"
fi

echo ""

# Display memory configuration
echo "Memory Configuration:"
echo "  Total system memory: $(free -h | grep '^Mem:' | awk '{print $2}')"
echo "  Available memory: $(free -h | grep '^Mem:' | awk '{print $7}')"

if [ -n "$MEMORY_LIMIT" ]; then
    echo "  Container limit: $MEMORY_LIMIT"
fi

echo ""

# Display inference configuration
echo "Inference Configuration:"
echo "  Context size: ${CONTEXT_SIZE:-4096}"
echo "  Batch size: ${BATCH_SIZE:-512}"
echo "  Threads: ${THREADS:-8}"
echo "  GPU layers: ${N_GPU_LAYERS:--1}"
echo "  Parallel requests: ${PARALLEL_REQUESTS:-1}"

echo ""
echo "================================"
echo ""

# If no command specified, run the default server
if [ $# -eq 0 ]; then
    echo "Starting llama.cpp server with default configuration..."
    exec ./build/bin/llama-server \
        $MODEL_ARGS \
        --host 0.0.0.0 \
        --port 8080 \
        -c ${CONTEXT_SIZE:-4096} \
        --n-gpu-layers ${N_GPU_LAYERS:--1} \
        --threads ${THREADS:-8} \
        --batch-size ${BATCH_SIZE:-512} \
        --parallel ${PARALLEL_REQUESTS:-1} \
        --log-disable \
        --metrics
else
    # Execute provided command
    exec "$@"
fi