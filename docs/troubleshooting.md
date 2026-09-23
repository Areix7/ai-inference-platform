# Troubleshooting

Notes from deploying this stack on AlmaLinux 10.2 with an A10.
Most of these are EL10-specific, some are Docker Hub related.

## 1. dkms missing on AlmaLinux 10

    No package dkms available.

dkms is not in the base repos. Enable EPEL first:

    dnf install -y epel-release
    dnf install -y dkms

## 2. NVIDIA CUDA repo for RHEL 10 returns 404

developer.download.nvidia.com/compute/cuda/repos/rhel10/x86_64/ is empty
at the time of writing. The RHEL 9 repo works because the RPMs are
compatible:

    baseurl: https://developer.download.nvidia.com/compute/cuda/repos/rhel9/x86_64

If gpgcheck fails with 404 on RPM-GPG-KEY-nvidia, disable gpg check for
that repo until NVIDIA publishes a RHEL 10 key.

## 3. Docker CE repo path changed

download.docker.com/linux/centos/9 no longer serves metadata. Use the
rhel path instead:

    https://download.docker.com/linux/rhel/9/x86_64/stable

Mirror in China: mirrors.aliyun.com/docker-ce/linux/centos/9/x86_64/stable

## 4. Docker fails to start: xt_addrtype not supported

    failed to register "bridge" driver: Extension addrtype revision 0
    not supported, missing kernel module?

iptables on EL10 runs over nf_tables, and the required kernel modules
are not in the minimal install. Install them:

    dnf install -y kernel-modules-extra
    modprobe xt_addrtype
    modprobe br_netfilter

To persist across reboots:

    /etc/modules-load.d/docker.conf
    xt_addrtype
    xt_conntrack
    xt_MASQUERADE
    br_netfilter

## 5. Docker socket missing after stop/start on Alibaba Cloud

The instance uses stop-and-start (saving mode). systemd sometimes loses
enabled state and /etc/docker/daemon.json is not persisted if the
shutdown was not clean. After restart, run:

    systemctl daemon-reload
    systemctl start docker
    cat /etc/docker/daemon.json     # recreate if missing

## 6. nvidia-ctk configure overwrites daemon.json

Running nvidia-ctk runtime configure --runtime=docker rewrites
/etc/docker/daemon.json and drops the registry-mirrors entry. Keep
mirrors in the same file:

    {
      "registry-mirrors": ["https://docker.m.daocloud.io"],
      "runtimes": {
        "nvidia": { "args": [], "path": "nvidia-container-runtime" }
      }
    }

## 7. HuggingFace unreachable

huggingface.co is not reachable from the mainland A10 node. Use
hf-mirror.com for one-off downloads, or modelscope for the primary path:

    export HF_ENDPOINT=https://hf-mirror.com
    hf download Qwen/Qwen3-8B --local-dir <path>

    modelscope download --model Qwen/Qwen3-8B --local-dir <path>

Weights are mounted into the container from data/hf-cache/models/ so the
container never downloads anything at runtime. This keeps the container
image and the model lifecycle separate.

## 8. --served-model-name still shows the old model

Changing --model in vllm.service.j2 is not enough. The vLLM CLI arg
--served-model-name determines the id returned by /v1/models. Update
both, then:

    systemctl daemon-reload
    systemctl restart vllm

## 9. Grafana dashboard import on Grafana 13

Grafana 13 removed the "Import via dashboard JSON" entry from the
sidebar. Open /dashboard/import directly. If a downloaded dashboard
references ${DS_PROMETHEUS} and provisioning does not substitute it,
import through the API instead:

    curl -X POST http://localhost:3000/api/dashboards/import \
      -H 'Content-Type: application/json' \
      -u admin:changeme \
      -d @import.json

## 10. Prometheus rules contain $labels and crash Jinja2

Rule files use Prometheus template variables like {{ $labels.gpu }}.
Do not put them under templates/ (Jinja2 will try to render them).
Store under files/ and deploy with copy.
