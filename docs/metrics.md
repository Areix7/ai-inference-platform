# Metrics

Scraped into Prometheus, visualized in Grafana.

## vLLM (inference engine)

vLLM exposes `/metrics` on :8000. All names prefixed `vllm:`.

    vllm:time_to_first_token_seconds     TTFT, histogram
    vllm:time_per_output_token_seconds   TPOT, histogram
    vllm:e2e_request_latency_seconds     end to end, histogram
    vllm:num_requests_running            active batch size, gauge
    vllm:num_requests_waiting            queue length, gauge
    vllm:kv_cache_usage_perc             KV cache 0..1, gauge
    vllm:prompt_tokens_total             input tokens, counter
    vllm:generation_tokens_total         output tokens, counter
    vllm:request_success_total           by finish reason, counter

TTFT is what users feel first: time from request send to first token.
p99 above 1s is bad for chat. With Qwen3-8B on A10 at concurrency 10,
TTFT p99 measured 88 ms.

KV cache usage close to 1.0 means the engine is memory bound. Under
sustained load, watch vllm:num_requests_waiting. If it grows, the
scheduler is queueing, not the GPU.

## DCGM Exporter (GPU hardware)

DCGM Exporter runs on :9400. Metrics prefixed `DCGM_FI_DEV_`.

    DCGM_FI_DEV_GPU_UTIL        SM utilisation %
    DCGM_FI_DEV_MEM_COPY_UTIL   memory bandwidth %
    DCGM_FI_DEV_FB_USED         framebuffer used, MiB
    DCGM_FI_DEV_FB_FREE         framebuffer free, MiB
    DCGM_FI_DEV_GPU_TEMP        temperature C
    DCGM_FI_DEV_POWER_USAGE     power W
    DCGM_FI_DEV_SM_CLOCK        SM clock MHz
    DCGM_FI_DEV_MEM_CLOCK       memory clock MHz
    DCGM_FI_DEV_XID_ERRORS      XID count since boot

A10 thermal ceiling is around 95 C. Sustained 85 C triggers the
GPUTempHigh alert.

## Platform inspection

Custom script writes textfile metrics for node_exporter. Prefix
`ai_platform_`.

    ai_platform_vllm_up              1 if vllm.service is active
    ai_platform_vllm_restarts_total  systemd NRestarts
    ai_platform_vllm_api_ok          1 if /v1/models returns 200
    ai_platform_gpu_ok               1 if nvidia-smi works
    ai_platform_gpu_temp_celsius     GPU temp
    ai_platform_gpu_mem_used_percent VRAM used %
    ai_platform_toolkit_ok           1 if nvidia-ctk on PATH
    ai_platform_docker_up            1 if docker.service active
    ai_platform_model_dir_ok         weights dir exists
    ai_platform_model_size_mb        weights dir size
    ai_platform_disk_free_percent    free % on /
    ai_platform_prometheus_up        1 if prometheus.service active
    ai_platform_grafana_up           1 if grafana.service active
    ai_platform_inspect_last_run     unix ts
    ai_platform_inspect_exit_code    0 ok, 1 warn, 2 critical

The exit code is also written to journald:

    journalctl -t ai-platform-inspect -n 10

## Client side benchmark

tools/benchmark.py reports what the caller sees, not what the server
reports. Comparing them catches network and SDK overhead that server
side metrics miss.

    ttft p50 p90 p99     time to first token, seconds
    total p50 p90 p99    end to end, seconds
    rps                  requests per second
    tok_per_s            generated tokens per second
    errors               count by failure class

Reference run, Qwen3-8B, concurrency 10, max_tokens 128:

    ttft p50 0.0799 s   p90 0.0877 s   p99 0.0884 s
    total p50 4.7663 s  p99 4.7712 s
    rps 2.1             tok_per_s 268.43
