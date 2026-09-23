# ai-inference-platform

Ansible playbooks to deploy a vLLM inference service on a single
AlmaLinux 10 node with NVIDIA A10 GPU.

Tested on Alibaba Cloud ecs.gn7i-c32g1.8xlarge.

## What it deploys

- vLLM in Docker, managed by systemd, auto-restart on crash
- DCGM Exporter for GPU hardware metrics
- Prometheus scraping vLLM, DCGM and a node inspection script
- Grafana with pre-provisioned dashboards and datasource
- Node inspection script running every 5 min via cron
- Client-side TTFT benchmark tool (async, Python)

## Ports

    8000   vLLM API + /metrics
    9400   DCGM Exporter
    9090   Prometheus
    3000   Grafana

## Quick start

    git clone https://github.com/Areix7/ai-inference-platform
    cd ai-inference-platform
    vim inventory/hosts          # set target host
    vim group_vars/all.yml       # pick model
    ansible-playbook site.yml

## Model switch

Edit vllm_model in group_vars/all.yml, then:

    ansible-playbook site.yml --tags vllm

Model weights are expected at data/hf-cache/models/<name>/ and are
mounted into the container read-only. Download once with modelscope:

    modelscope download --model Qwen/Qwen3-8B \
      --local_dir data/hf-cache/models/Qwen3-8B

## Benchmark

    python3 tools/benchmark.py --concurrency 10 --requests 40 \
      --max-tokens 128 --out docs/bench-qwen3-8b.json

Sample result, Qwen3-8B on one A10, concurrency 10:

    requests     40 ok / 0 failed
    wall         19.074 s
    rps          2.1
    tokens       5120  (268.43 tok/s)

    ttft p50     0.0799 s
    ttft p90     0.0877 s
    ttft p99     0.0884 s

    total p50    4.7663 s
    total p99    4.7712 s

## Alerts

Prometheus rules shipped under roles/monitoring/files/ai-platform-rules.yml:

- VLLMDown        vLLM endpoint unreachable for 1 min       critical
- GPUTempHigh     GPU temperature above 85 C for 5 min      warning
- GPUMemoryHigh   GPU memory above 90% for 10 min           warning
- DiskSpaceLow    root filesystem below 15% free for 5 min  warning

## Node inspection

roles/inspect installs /usr/local/bin/ai-platform-inspect.sh and a cron
entry that runs it every 5 min. Metrics go to the Prometheus textfile
collector and are scraped by node_exporter. Log lines go to journald:

    journalctl -t ai-platform-inspect

Thresholds live in /etc/ai-platform/inspect.conf.

## Docs

- docs/architecture.md
- docs/metrics.md
- docs/troubleshooting.md

## License

MIT
