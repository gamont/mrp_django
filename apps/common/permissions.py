from __future__ import annotations

from rest_framework.permissions import BasePermission, SAFE_METHODS


class MRPModelPermission(BasePermission):
    """Usa as permissões Django ``view/add/change/delete`` em toda a API.

    Para ações POST em detalhe (por exemplo ``release``, ``complete`` e
    ``receive``), exige ``change_<model>``. Para POST de coleção, exige
    ``add_<model>``. Superusuários mantêm acesso irrestrito.
    """

    message = "O usuário não possui a permissão exigida para esta operação."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not getattr(user, "is_authenticated", False):
            return False
        if user.is_superuser:
            return True

        queryset = getattr(view, "queryset", None)
        model = getattr(queryset, "model", None)
        if model is None and hasattr(view, "get_queryset"):
            try:
                model = view.get_queryset().model
            except Exception:
                model = None
        if model is None:
            return False

        action = getattr(view, "action", None)
        override = getattr(view, "permission_required_by_action", {}).get(action)
        if override:
            required = [override] if isinstance(override, str) else list(override)
            return all(user.has_perm(permission) for permission in required)

        if request.method in SAFE_METHODS:
            action_name = "view"
        elif request.method == "DELETE":
            action_name = "delete"
        elif request.method in {"PUT", "PATCH"}:
            action_name = "change"
        elif request.method == "POST":
            action_name = "change" if getattr(view, "detail", False) or action not in {None, "create"} else "add"
        else:
            return False

        permission = f"{model._meta.app_label}.{action_name}_{model._meta.model_name}"
        return user.has_perm(permission)
