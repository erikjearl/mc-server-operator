# MC SpeedRun World Server Hoster — System Design

> Full design document. See README for a quick overview.

## 1. Project Overview

This platform enables users to deploy, configure, and play Minecraft speedrun worlds on-demand
using a containerized Kubernetes infrastructure hosted on a home lab cluster.

## 2. Use Case

Users visit a website, choose a speedrun world seed and settings, and get a fully containerized
Minecraft server to connect to — without any manual setup.

### User-Facing Features

- Website to browse and provision MC speedrun worlds (whitelisted seed list)
- UI to provision and manage K8s cluster resources
- Host containerized Minecraft servers on demand
- Spec fields: seed, rules/settings, game version, TTL

## 3. Infrastructure & Hardware

| Node | Role | Notes |
|------|------|-------|
| Dell PC | Control Plane + Primary Worker | Main workloads; higher CPU/RAM |
| Personal PC | Secondary Worker | Auxiliary node; monitoring stack |

> Both machines must be on the same LAN or connected via VPN.

### Networking

- Internal cluster networking: Flannel or Calico CNI
- NodePort or LoadBalancer services for MC server ports (25565+)
- Ingress controller (NGINX) for the web UI
- DDNS (DuckDNS / Cloudflare) for external access

## 4. Request Flow

1. User fills out the web form: seed, game version, rules
2. Frontend POSTs to the API backend
3. Backend creates a `MinecraftServer` CRD in K8s
4. Operator detects new CRD → deploys a Minecraft pod
5. Operator returns server IP/port → API sends to user
6. User connects their MC client to the assigned address

## 5. CRD Spec Fields

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| seed | string | "-1234567890" | World generation seed |
| gameVersion | string | "1.16.1" | Minecraft version |
| gameMode | string | "survival" | Game mode |
| difficulty | string | "normal" | Server difficulty |
| maxPlayers | integer | 4 | Max simultaneous players |
| allowCheats | boolean | false | Whether /gamemode is permitted |
| whitelistedUsers | []string | ["runner1"] | MC usernames allowed to join |
| metadataPreset | string | "java-1.16-any%" | Named speedrun config preset |
| ttlSeconds | integer | 3600 | Auto-delete after idle seconds |

## 6. Operator (Kopf / Python)

### Responsibilities

- Watch for `MinecraftServer` CRD create / update / delete events
- Reconcile desired state: create Deployment + Service per CRD
- Monitor pod health and restart failed servers
- Enforce TTL: delete pods after idle timeout expires
- Report status (IP, port, phase) back to CRD status subresource

### Why Kopf?

Kopf (Kubernetes Operator Pythonic Framework) is lightweight, readable, and easy to extend.
Perfect for a home lab prototype. Can always be rewritten in Go (Operator SDK / Kubebuilder)
if production scale requires it.

## 7. Web UI

### Pages

- **Home / Browse** — list available whitelisted speedrun seeds
- **Launch Server** — form: seed, version, rules, max players, whitelist
- **My Servers** — dashboard: active servers, IP/port, time remaining
- **Admin Panel** — cluster resources, node capacity, running pods

### Stack

- Frontend: Next.js + Tailwind CSS
- Backend API: FastAPI (Python) or Node.js (Express)
- Auth: invite code or GitHub OAuth

## 8. Helm Chart

Packages the full system for reproducible installs:

- Operator Deployment + RBAC
- CRD manifests
- Web UI Deployment + Service + Ingress
- API Backend Deployment + Service
- ConfigMaps for presets and whitelisted seeds
- Optional: Prometheus ServiceMonitor

## 9. Known Limitations

| Limitation | Mitigation |
|------------|------------|
| Home internet bandwidth | LAN play or Tailscale/ZeroTier VPN |
| Dynamic IP / NAT | DDNS (DuckDNS, Cloudflare) |
| 2-node capacity | Pod resource limits + priority classes |
| No HA control plane | Accepted; document recovery steps |
| Storage redundancy | local-path provisioner + manual backups |

## 10. Future Enhancements

- CRDs for Fabric, Forge, Paper, Bedrock
- Automatic world recording / replay upload
- LiveSplit / in-game timer overlay
- Discord bot (slash commands to launch servers)
- Grafana dashboard (players, uptime, resource usage)
- Horizontal pod autoscaling