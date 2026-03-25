"""
MC SpeedRun World Server Hoster — Kopf Operator
Watches MinecraftServer CRDs and manages Minecraft pod lifecycle.
"""

import kopf
import kubernetes
import logging

# ---------------------------------------------------------------------------
# Kubernetes client setup
# ---------------------------------------------------------------------------

kubernetes.config.load_incluster_config() if False else kubernetes.config.load_kube_config()
apps_v1 = kubernetes.client.AppsV1Api()
core_v1 = kubernetes.client.CoreV1Api()

GROUP = "mc.homelab.io"
VERSION = "v1"
PLURAL = "minecraftservers"
MC_IMAGE = "itzg/minecraft-server"
NAMESPACE = "default"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_deployment(name: str, spec: dict) -> dict:
    """Build a Kubernetes Deployment manifest for a Minecraft server pod."""
    seed = spec.get("seed", "")
    game_version = spec.get("gameVersion", "LATEST")
    game_mode = spec.get("gameMode", "survival").upper()
    difficulty = spec.get("difficulty", "normal").upper()
    max_players = str(spec.get("maxPlayers", 4))
    allow_cheats = "true" if spec.get("allowCheats", False) else "false"

    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": name,
            "labels": {"app": name, "managed-by": "mc-operator"},
        },
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": {"app": name}},
            "template": {
                "metadata": {"labels": {"app": name}},
                "spec": {
                    "containers": [
                        {
                            "name": "minecraft",
                            "image": MC_IMAGE,
                            "env": [
                                {"name": "EULA", "value": "TRUE"},
                                {"name": "VERSION", "value": game_version},
                                {"name": "MODE", "value": game_mode},
                                {"name": "DIFFICULTY", "value": difficulty},
                                {"name": "MAX_PLAYERS", "value": max_players},
                                {"name": "ALLOW_CHEATS", "value": allow_cheats},
                                {"name": "SEED", "value": seed},
                            ],
                            "ports": [{"containerPort": 25565, "protocol": "TCP"}],
                            "resources": {
                                "requests": {"memory": "1Gi", "cpu": "500m"},
                                "limits": {"memory": "2Gi", "cpu": "2"},
                            },
                        }
                    ]
                },
            },
        },
    }


def build_service(name: str) -> dict:
    """Build a NodePort Service to expose the Minecraft port."""
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": name,
            "labels": {"app": name, "managed-by": "mc-operator"},
        },
        "spec": {
            "type": "NodePort",
            "selector": {"app": name},
            "ports": [{"port": 25565, "targetPort": 25565, "protocol": "TCP"}],
        },
    }


# ---------------------------------------------------------------------------
# Operator handlers
# ---------------------------------------------------------------------------

@kopf.on.create(GROUP, VERSION, PLURAL)
def on_create(spec, name, namespace, logger, patch, **kwargs):
    """Handle MinecraftServer creation — spin up Deployment + Service."""
    logger.info(f"Creating MinecraftServer: {name}")

    # Create Deployment
    deployment = build_deployment(name, spec)
    kopf.adopt(deployment)
    apps_v1.create_namespaced_deployment(namespace=namespace, body=deployment)
    logger.info(f"Deployment created for {name}")

    # Create Service
    service = build_service(name)
    kopf.adopt(service)
    svc = core_v1.create_namespaced_service(namespace=namespace, body=service)
    node_port = svc.spec.ports[0].node_port
    logger.info(f"Service created for {name} on NodePort {node_port}")

    # Update CRD status
    patch.status["phase"] = "Running"
    patch.status["port"] = node_port
    patch.status["message"] = f"Server started on port {node_port}"


@kopf.on.update(GROUP, VERSION, PLURAL)
def on_update(spec, name, namespace, logger, **kwargs):
    """Handle MinecraftServer updates — reconcile Deployment spec."""
    logger.info(f"Updating MinecraftServer: {name}")

    deployment = build_deployment(name, spec)
    apps_v1.patch_namespaced_deployment(name=name, namespace=namespace, body=deployment)
    logger.info(f"Deployment updated for {name}")


@kopf.on.delete(GROUP, VERSION, PLURAL)
def on_delete(name, namespace, logger, **kwargs):
    """Handle MinecraftServer deletion — owned resources are garbage-collected."""
    logger.info(f"MinecraftServer {name} deleted — owned resources will be cleaned up.")


# ---------------------------------------------------------------------------
# TTL enforcement (runs periodically)
# ---------------------------------------------------------------------------

@kopf.timer(GROUP, VERSION, PLURAL, interval=60)
def ttl_check(spec, name, namespace, logger, patch, **kwargs):
    """Periodically check if the server has exceeded its TTL and delete it."""
    ttl = spec.get("ttlSeconds")
    if not ttl:
        return

    # TODO: implement idle/uptime tracking and auto-delete when TTL exceeded
    logger.debug(f"TTL check for {name}: ttlSeconds={ttl} (tracking not yet implemented)")