# ⛏️ MC SpeedRun World Server Hoster

> A Kubernetes-native platform for deploying on-demand Minecraft speedrun servers — hosted from your home lab.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-1.25+-326CE5.svg)](https://kubernetes.io/)
[![Kopf](https://img.shields.io/badge/Operator-Kopf-orange.svg)](https://kopf.readthedocs.io/)

---

## Overview

**MC SpeedRun World Server Hoster** is a home-lab Kubernetes platform that lets users spin up fully-configured Minecraft servers on demand — no manual setup required.

Users pick a whitelisted speedrun seed, choose their game version and ruleset, and get back an IP and port to connect to. Everything runs inside the cluster. When the session ends, the server cleans itself up.

The system is built around a **Custom Resource Definition (CRD)** called `MinecraftServer`. A lightweight [Kopf](https://kopf.readthedocs.io/) Python operator watches those resources and manages the full pod lifecycle — creating, monitoring, and tearing down Minecraft server pods automatically.

---

## Features

- 🎮 **On-demand Minecraft servers** — launch a server from a web form, get an IP/port back
- 🌱 **Whitelisted speedrun seeds** — curated list of seeds with preset configurations
- 📦 **Kubernetes-native** — every server is a CRD-driven pod using [`itzg/minecraft-server`](https://github.com/itzg/docker-minecraft-server)
- 🐍 **Kopf Python operator** — simple, readable operator code; easy to extend
- ⏳ **TTL auto-cleanup** — servers self-delete after an idle timeout
- 🧩 **Metadata presets** — named configs for common speedrun categories (e.g. `java-1.16-any%`)
- 📊 **Status reporting** — operator writes server IP, port, and phase back to the CRD status

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Home Lab K8s Cluster                 │
│                                                             │
│   [Web UI]  ──▶  [API Backend]  ──▶  [MinecraftServer CRD] │
│                                             │               │
│                                    [Kopf Operator]          │
│                                             │               │
│                               ┌────────────▼────────────┐  │
│                               │   Minecraft Server Pod   │  │
│                               │  (itzg/minecraft-server) │  │
│                               └─────────────────────────-┘  │
└─────────────────────────────────────────────────────────────┘
```

### Components

| Component | Tech | Description |
|-----------|------|-------------|
| Web Frontend | Next.js + Tailwind | Browse seeds, launch/manage servers |
| API Backend | Node.js / Python | Validates requests, creates CRD resources |
| Kubernetes Operator | Python + Kopf | Watches CRDs, manages pod lifecycle |
| CRD: `MinecraftServer` | Kubernetes CRD | Declarative spec for a single MC server |
| Minecraft Pod | `itzg/minecraft-server` | The actual game server container |
| Helm Chart | Helm | Packages everything for reproducible installs |

---

## MinecraftServer CRD

Each server instance is described by a `MinecraftServer` custom resource:

```yaml
apiVersion: mc.homelab.io/v1
kind: MinecraftServer
metadata:
  name: my-speedrun-server
spec:
  seed: "-1234567890"
  gameVersion: "1.16.1"
  gameMode: "survival"
  difficulty: "normal"
  maxPlayers: 4
  allowCheats: false
  whitelistedUsers:
    - "runner1"
  metadataPreset: "java-1.16-any%"
  ttlSeconds: 3600
```

The operator picks this up and:
1. Deploys a Minecraft pod with matching env vars
2. Applies the named metadata preset (gamerules, settings)
3. Creates a `NodePort` Service to expose the MC port
4. Monitors health and enforces the TTL
5. Writes `status.ip`, `status.port`, and `status.phase` back to the resource

---

## Repo Structure

```
mc-server-operator/
├── operator/               # Kopf Python operator
│   ├── main.py             # Operator entrypoint (handlers)
│   ├── requirements.txt
│   └── Dockerfile
├── crd/
│   └── minecraftserver-crd.yaml   # CRD schema
├── helm/
│   └── mc-server-operator/        # Helm chart
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── crd.yaml
│           ├── operator-deployment.yaml
│           └── rbac.yaml
├── web/                    # Web UI (Next.js) — WIP
│   └── ...
├── docs/
│   └── design.md           # Full system design document
└── README.md
```

---

## Getting Started

> ⚠️ This project is in early development. Instructions below are for local/dev use.

### Prerequisites

- Kubernetes cluster (kubeadm, k3s, or minikube)
- `kubectl` configured
- `helm` installed
- Python 3.11+

### 1. Apply the CRD

```bash
kubectl apply -f crd/minecraftserver-crd.yaml
```

### 2. Run the Operator Locally (dev mode)

```bash
cd operator
pip install -r requirements.txt
kopf run main.py --verbose
```

### 3. Create a Test Server

```bash
kubectl apply -f - <<EOF
apiVersion: mc.homelab.io/v1
kind: MinecraftServer
metadata:
  name: test-server
spec:
  seed: "-1234567890"
  gameVersion: "1.16.1"
  gameMode: "survival"
  difficulty: "normal"
  maxPlayers: 2
  allowCheats: false
  ttlSeconds: 3600
EOF
```

### 4. Check Status

```bash
kubectl get minecraftservers
kubectl describe minecraftserver test-server
```

---

## Infrastructure

| Node | Role | Notes |
|------|------|-------|
| Dell PC | Control Plane + Worker | Primary workloads, MC server pods |
| Personal PC | Worker | Auxiliary node, monitoring stack |

Both machines on the same LAN (or VPN). Cluster networking via Flannel or Calico.

---

## Roadmap

- [ ] Kopf operator — core CRUD lifecycle
- [ ] CRD schema + validation
- [ ] TTL / idle cleanup
- [ ] Web UI — seed browser + launch form
- [ ] API backend
- [ ] Helm chart packaging
- [ ] Metadata presets system
- [ ] Status reporting (IP, port, phase)
- [ ] NGINX ingress + DDNS setup guide
- [ ] Grafana metrics dashboard
- [ ] Discord bot integration
- [ ] CI/CD via GitHub Actions + GHCR

---

## Known Limitations

| Limitation | Mitigation |
|------------|------------|
| Home internet bandwidth | Use LAN or Tailscale/ZeroTier VPN for remote players |
| Dynamic IP / NAT | DDNS via DuckDNS or Cloudflare |
| 2-node cluster capacity | Set pod resource limits; use pod priority classes |
| No HA control plane | Accepted for home lab; document recovery steps |
| Storage redundancy | Local-path provisioner + manual world backups |

---

## Tech Stack

- **Operator**: Python + [Kopf](https://kopf.readthedocs.io/)
- **Minecraft Image**: [`itzg/minecraft-server`](https://github.com/itzg/docker-minecraft-server)
- **Frontend**: Next.js + Tailwind CSS *(planned)*
- **Backend API**: Python (FastAPI) or Node.js *(planned)*
- **Packaging**: Helm
- **Cluster**: k3s or kubeadm on bare metal home lab

---

## License

MIT — see [LICENSE](LICENSE)