"""
MC Server Operator — Frontend
Simple FastAPI app that renders a Jinja2 form and creates MinecraftServer CRDs.
"""

import logging
import os
from typing import Optional

import kubernetes
from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

# ---------------------------------------------------------------------------
# Kubernetes client setup
# ---------------------------------------------------------------------------

try:
    kubernetes.config.load_incluster_config()
except kubernetes.config.ConfigException:
    kubernetes.config.load_kube_config()

custom_api = kubernetes.client.CustomObjectsApi()

GROUP = "mc.erikjearl.io"
VERSION = "v1alpha1"
PLURAL = "minecraftservers"
DEFAULT_NAMESPACE = os.environ.get("MC_NAMESPACE", "default")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="MC Server Launcher")
templates = Jinja2Templates(directory="templates")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def list_servers(namespace: str) -> list[dict]:
    """Return all MinecraftServer objects in the given namespace."""
    try:
        result = custom_api.list_namespaced_custom_object(
            group=GROUP,
            version=VERSION,
            namespace=namespace,
            plural=PLURAL,
        )
        return result.get("items", [])
    except kubernetes.client.exceptions.ApiException as e:
        logger.error(f"Failed to list servers: {e}")
        return []


def create_server(
    name: str,
    namespace: str,
    game_version: str,
    server_properties: dict[str, str],
) -> None:
    """Create a MinecraftServer custom resource."""
    manifest = {
        "apiVersion": f"{GROUP}/{VERSION}",
        "kind": "MinecraftServer",
        "metadata": {
            "name": name,
            "namespace": namespace,
        },
        "spec": {
            "gameVersion": game_version,
            "serverProperties": server_properties,
        },
    }
    custom_api.create_namespaced_custom_object(
        group=GROUP,
        version=VERSION,
        namespace=namespace,
        plural=PLURAL,
        body=manifest,
    )
    logger.info(f"Created MinecraftServer {name} in {namespace}")


def delete_server(name: str, namespace: str) -> None:
    """Delete a MinecraftServer custom resource."""
    custom_api.delete_namespaced_custom_object(
        group=GROUP,
        version=VERSION,
        namespace=namespace,
        plural=PLURAL,
        name=name,
    )
    logger.info(f"Deleted MinecraftServer {name} from {namespace}")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/")
def index(request: Request, error: Optional[str] = None, success: Optional[str] = None):
    """Render main page: server list + launch form."""
    servers = list_servers(DEFAULT_NAMESPACE)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "servers": servers,
            "namespace": DEFAULT_NAMESPACE,
            "error": error,
            "success": success,
        },
    )


@app.post("/servers/create")
def create(
    name: str = Form(...),
    game_version: str = Form(...),
    seed: str = Form(""),
    gamemode: str = Form("survival"),
    difficulty: str = Form("normal"),
    max_players: str = Form("4"),
    motd: str = Form(""),
    memory: str = Form("2G"),
    online_mode: str = Form("true"),
    whitelist: str = Form("false"),
):
    """Handle server creation form POST."""
    # Build serverProperties from form fields
    props: dict[str, str] = {
        "GAMEMODE": gamemode,
        "DIFFICULTY": difficulty,
        "MAX_PLAYERS": max_players,
        "MEMORY": memory,
        "ONLINE_MODE": online_mode,
        "WHITE_LIST": whitelist,
    }
    if seed.strip():
        props["SEED"] = seed.strip()
    if motd.strip():
        props["MOTD"] = motd.strip()

    try:
        create_server(
            name=name.strip().lower(),
            namespace=DEFAULT_NAMESPACE,
            game_version=game_version.strip(),
            server_properties=props,
        )
        return RedirectResponse(url=f"/?success={name}+created", status_code=303)
    except kubernetes.client.exceptions.ApiException as e:
        msg = f"Failed to create server: {e.reason}"
        logger.error(msg)
        return RedirectResponse(url=f"/?error={msg}", status_code=303)


@app.post("/servers/{name}/delete")
def delete(name: str):
    """Handle server deletion form POST."""
    try:
        delete_server(name=name, namespace=DEFAULT_NAMESPACE)
        return RedirectResponse(url=f"/?success={name}+deleted", status_code=303)
    except kubernetes.client.exceptions.ApiException as e:
        msg = f"Failed to delete server: {e.reason}"
        logger.error(msg)
        return RedirectResponse(url=f"/?error={msg}", status_code=303)