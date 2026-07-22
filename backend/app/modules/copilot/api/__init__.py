"""Routes Copilot : agent sécurisé et endpoint historique désactivé."""

from app.modules.copilot.api.router import router, router_agent

__all__ = ["router", "router_agent"]
