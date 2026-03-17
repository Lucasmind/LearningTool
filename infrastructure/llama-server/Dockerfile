FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC
ENV LLAMA_VULKAN=1

# Install dependencies including Vulkan and CUDA support
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    libcurl4-openssl-dev \
    ca-certificates \
    python3 \
    python3-pip \
    libgomp1 \
    vulkan-tools \
    libvulkan-dev \
    vulkan-validationlayers \
    spirv-tools \
    glslang-tools \
    glslc \
    libshaderc-dev \
    mesa-vulkan-drivers \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone llama.cpp latest master for broadest model support
RUN git clone --depth 1 https://github.com/ggerganov/llama.cpp.git && \
    cd llama.cpp && \
    mkdir build && \
    cd build && \
    cmake .. \
        -DGGML_VULKAN=ON \
        -DGGML_VULKAN_CHECK_RESULTS=OFF \
        -DLLAMA_BUILD_SERVER=ON \
        -DLLAMA_BUILD_EXAMPLES=ON \
        -DCMAKE_BUILD_TYPE=Release \
        -DLLAMA_NATIVE=OFF \
        -DLLAMA_F16C=ON \
        -DLLAMA_FMA=ON \
        -DLLAMA_AVX=ON \
        -DLLAMA_AVX2=ON \
        -DLLAMA_AVX512=OFF && \
    cmake --build . --config Release -j$(nproc)

RUN mkdir -p /models /config /cache

COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /app/llama.cpp

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

CMD ["./build/bin/llama-server", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "-m", "/models/model.gguf", \
     "-c", "16384", \
     "--n-gpu-layers", "-1", \
     "--parallel", "4", \
     "--threads", "16"]
