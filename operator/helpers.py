"""
Helper functions for building Kubernetes resource manifests
for the mc-server-operator.
"""

MC_IMAGE = "itzg/minecraft-server:latest"


def build_env(spec: dict) -> list:
    """
    Build the env list for the Minecraft container.

    Always injects EULA=TRUE and VERSION from spec.gameVersion.
    Any key/value pairs in spec.serverProperties are appended as-is
    (they are expected to be valid itzg/minecraft-server env var names).
    """
    env = [
        {"name": "EULA", "value": "TRUE"},
        {"name": "VERSION", "value": spec.get("gameVersion", "LATEST")},
    ]

    for key, value in spec.get("serverProperties", {}).items():
        env.append({"name": str(key), "value": str(value)})

    return env


def build_deployment(name: str, namespace: str, spec: dict) -> dict:
    """Build a Kubernetes Deployment manifest for a Minecraft server pod."""
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": {"app": name, "managed-by": "mc-operator"},
        },
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": {"app": name}},
            "strategy": {"type": "Recreate"},
            "template": {
                "metadata": {"labels": {"app": name}},
                "spec": {
                    "containers": [
                        {
                            "name": "minecraft",
                            "image": MC_IMAGE,
                            "ports": [{"containerPort": 25565, "protocol": "TCP"}],
                            "env": build_env(spec),
                            "volumeMounts": [
                                {"name": "data", "mountPath": "/data"}
                            ],
                            "resources": {
                                "requests": {"memory": "2Gi", "cpu": "500m"},
                                "limits": {"memory": "3Gi", "cpu": "2000m"},
                            },
                            "readinessProbe": {
                                "tcpSocket": {"port": 25565},
                                "initialDelaySeconds": 60,
                                "periodSeconds": 10,
                                "failureThreshold": 6,
                            },
                            "livenessProbe": {
                                "tcpSocket": {"port": 25565},
                                "initialDelaySeconds": 120,
                                "periodSeconds": 30,
                                "failureThreshold": 3,
                            },
                        }
                    ],
                    "volumes": [
                        {
                            "name": "data",
                            "persistentVolumeClaim": {"claimName": name},
                        }
                    ],
                },
            },
        },
    }


def build_service(name: str, namespace: str, node_port: int = None) -> dict:
    """Build a NodePort Service to expose the Minecraft port."""
    port_spec = {
        "port": 25565,
        "targetPort": 25565,
        "protocol": "TCP",
    }
    if node_port is not None:
        port_spec["nodePort"] = node_port

    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": {"app": name, "managed-by": "mc-operator"},
        },
        "spec": {
            "type": "NodePort",
            "selector": {"app": name},
            "ports": [port_spec],
        },
    }


def get_node_address(core_v1, node_port: int) -> str:
    """
    Return '<node-ip>:<node_port>' for the first Ready node with an InternalIP.
    NodePort is available on every node, so any node IP is valid.
    """
    nodes = core_v1.list_node()
    for node in nodes.items:
        for addr in node.status.addresses:
            if addr.type == "InternalIP":
                return f"{addr.address}:{node_port}"
    return f"<unknown>:{node_port}"


def build_pvc(name: str, namespace: str, storage_size: str = "5Gi", storage_class: str = None) -> dict:
    """Build a PersistentVolumeClaim for Minecraft world data."""
    spec = {
        "accessModes": ["ReadWriteOnce"],
        "resources": {"requests": {"storage": storage_size}},
    }
    if storage_class:
        spec["storageClassName"] = storage_class

    return {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": {"app": name, "managed-by": "mc-operator"},
        },
        "spec": spec,
    }