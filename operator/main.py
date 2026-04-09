"""
MC Server Operator
Watches MinecraftServer CRDs and manages Minecraft pod lifecycle.
"""

import kopf
import kubernetes
import logging
import os

from helpers import build_deployment, build_service, build_pvc, get_node_address

# ---------------------------------------------------------------------------
# Operator Setup
# ---------------------------------------------------------------------------

try:
    kubernetes.config.load_incluster_config()
except kubernetes.config.ConfigException:
    kubernetes.config.load_kube_config()

apps_v1 = kubernetes.client.AppsV1Api()
core_v1 = kubernetes.client.CoreV1Api()

GROUP = "mc.erikjearl.io"
VERSION = "v1alpha1"
PLURAL = "minecraftservers"

@kopf.on.startup()
def on_startup(logger, settings, **kwargs):
    """Configure the operator on startup."""

    # Logging level — override with LOG_LEVEL env var (e.g. DEBUG, WARNING)
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info(f"mc-server-operator starting (log level: {log_level})")

    # Kopf posting settings — reduce noise from status patch retries
    settings.posting.level = logging.WARNING

    logger.info("MC Operator startup complete — watching MinecraftServer resources")


# ---------------------------------------------------------------------------
# Operator handlers
# ---------------------------------------------------------------------------

@kopf.on.create(GROUP, VERSION, PLURAL)
def on_create(spec, name, namespace, logger, patch, **kwargs):
    """Handle MinecraftServer creation — spin up PVC, Deployment, and Service."""
    logger.info(f"Creating MinecraftServer: {name}")

    # Create PVC
    pvc = build_pvc(name, namespace, storage_class="local-path")
    kopf.adopt(pvc)
    try:
        core_v1.create_namespaced_persistent_volume_claim(namespace=namespace, body=pvc)
        logger.info(f"PVC created for {name}")
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 409:
            logger.info(f"PVC for {name} already exists — skipping creation")
        else:
            raise

    # Create Deployment
    deployment = build_deployment(name, namespace, spec)
    kopf.adopt(deployment)
    try:
        apps_v1.create_namespaced_deployment(namespace=namespace, body=deployment)
        logger.info(f"Deployment created for {name}")
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 409:
            logger.info(f"Deployment for {name} already exists — skipping creation")
        else:
            raise

    # Create Service
    service = build_service(name, namespace)
    kopf.adopt(service)
    try:
        svc = core_v1.create_namespaced_service(namespace=namespace, body=service)
        node_port = svc.spec.ports[0].node_port
        logger.info(f"Service created for {name} on NodePort {node_port}")
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 409:
            logger.info(f"Service for {name} already exists — reading back node_port")
            svc = core_v1.read_namespaced_service(name=name, namespace=namespace)
            node_port = svc.spec.ports[0].node_port
        else:
            raise

    # Update CRD status
    patch.status["phase"] = "Running"
    patch.status["port"] = node_port
    patch.status["address"] = get_node_address(core_v1, node_port)
    patch.status["deploymentRef"] = name
    patch.status["serviceRef"] = name


@kopf.on.update(GROUP, VERSION, PLURAL)
def on_update(spec, name, namespace, logger, **kwargs):
    """Handle MinecraftServer updates — reconcile Deployment spec."""
    logger.info(f"Detected Update for MinecraftServer: {name}")
    # TODO: Possible patch to services?
    # deployment = build_deployment(name, namespace, spec)
    # apps_v1.patch_namespaced_deployment(name=name, namespace=namespace, body=deployment)
    # logger.info(f"Deployment updated for {name}")


@kopf.on.delete(GROUP, VERSION, PLURAL)
def on_delete(name, namespace, logger, **kwargs):
    """Handle MinecraftServer deletion — owned resources are garbage-collected."""
    logger.info(f"MinecraftServer {name} deleted — owned resources will be cleaned up.")