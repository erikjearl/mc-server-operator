# mc-server-operator

A Kubernetes operator for deploying Minecraft servers on demand using [`itzg/minecraft-server`](https://github.com/itzg/docker-minecraft-server).

## How it works

Users create a `MinecraftServer` custom resource. The operator watches for these and automatically provisions a PVC, Deployment, and NodePort Service for each one. When the resource is deleted, owned resources are garbage-collected.

## CRD: MinecraftServer

```yaml
apiVersion: mc.erikjearl.io/v1alpha1
kind: MinecraftServer
metadata:
  name: speedrun-1-16
  namespace: default
spec:
  gameVersion: "1.16.1"           # required — Minecraft version or "LATEST"
  serverProperties:               # optional — itzg env var overrides
    GAMEMODE: survival
    DIFFICULTY: normal
    MAX_PLAYERS: "2"
    SEED: "-1234567890"
    MOTD: "Speedrun practice server"
    ONLINE_MODE: "true"
```

`serverProperties` accepts any environment variable supported by [itzg/minecraft-server](https://github.com/itzg/docker-minecraft-server#readme).

## Status fields

| Field | Description |
|---|---|
| `phase` | `Running` or `Failed` |
| `port` | Assigned NodePort |
| `address` | `<node-ip>:<port>` to connect from Minecraft |
| `deploymentRef` | Name of the managed Deployment |
| `serviceRef` | Name of the managed Service |

## Repo structure

```
mc-server-operator/
├── operator/
│   ├── main.py          # Kopf operator — event handlers
│   ├── helpers.py       # Manifest builders and utilities
│   ├── requirements.txt
│   └── Dockerfile
├── crd/
│   └── minecraftserver-crd.yaml
├── helm/
│   └── mc-server-operator/
├── examples/
│   ├── basic-server.yaml              # Example MinecraftServer CR
│   └── basic-server-deployment.yaml   # What the operator generates from it
└── docs/
    └── design.md
```

## Running locally

```bash
# Apply the CRD
kubectl apply -f crd/minecraftserver-crd.yaml

# Run the operator
cd operator
pip install -r requirements.txt
kopf run main.py --verbose

# Create a server
kubectl apply -f examples/basic-server.yaml

# Check status
kubectl get mcs
```

## Tech

- **Operator**: Python + [Kopf](https://kopf.readthedocs.io/)
- **Minecraft**: [`itzg/minecraft-server`](https://github.com/itzg/docker-minecraft-server)
- **Packaging**: Helm