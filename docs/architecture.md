# Architecture

Single AlmaLinux 10 node, one NVIDIA A10. Three layers.

```mermaid
flowchart TB
    subgraph Platform["Platform layer"]
        Prom[Prometheus :9090]
        Graf[Grafana :3000]
        Inspect[inspection script cron/5min]
        Rules[alert rules]
        Inspect --> Prom
        Rules --> Prom
        Prom --> Graf
    end

    subgraph Engine["Inference engine layer"]
        VLLM[vLLM container :8000<br/>OpenAI API + /metrics<br/>systemd managed]
    end

    subgraph Hardware["Hardware layer"]
        A10[NVIDIA A10]
        Driver[driver + CUDA]
        DCGM[DCGM Exporter :9400]
    end

    VLLM -.-> Prom
    DCGM -.-> Prom
    VLLM --- A10
    DCGM --- Driver
    A10 --- Driver
```

## Roles

site.yml runs them in order.

- preflight: read-only checks
- nvidia: driver + nvidia-smi verify
- docker: docker-ce + toolkit
- vllm: container + systemd unit
- monitoring: dcgm, prometheus, grafana
- inspect: health check cron

## Data flow

    vLLM /metrics          :8000  ->  Prometheus  ->  Grafana
    DCGM Exporter          :9400  ->  Prometheus  ->  Grafana
    inspect textfile       (disk) ->  node_exporter ->  Prometheus

The inspection script writes Prometheus textfile metrics to
/var/lib/node_exporter/textfile_collector/. node_exporter exposes them
over HTTP. Prometheus scrapes node_exporter like any other target.

## Why no Kubernetes

Just one node. One operator. K8s would add a control plane, an
ingress, a storage class, and a CRD for no benefit. systemd plus
Docker does the same job in 200 lines of Ansible.

## Model weights: mounted, not baked

The vLLM image is public and stable. The model changes. Keeping weights
on the host under data/hf-cache/models/ means:

- switching models is a one-line change, no image rebuild
- the same image serves different models on different hosts
- model download can fail or retry without touching the container
