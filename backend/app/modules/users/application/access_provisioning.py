"""Provisionnement déclaratif, idempotent et auditable des accès.

Le manifeste ne contient ni secret ni UUID métier. La résolution s'appuie sur
l'e-mail Auth, puis sur le nom normalisé Unicode. Toute ambiguïté devient un
conflit explicite. Les permissions scopées sont planifiées et appliquées via
le résolveur central (équipes UUID + exceptions).
"""

from __future__ import annotations

import json
import secrets
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol


PROJECT_REF = "slleauhyjnmiawosvlcg"
PRODUCTION_CONFIRMATION = "APPLY_ACCESS_MATRIX"
DECISIONS = frozenset({"reuse", "create", "conflict", "no-op"})


def normalize_identity(value: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(without_marks.casefold().split())


def normalized_full_name(row: dict[str, Any]) -> str:
    return normalize_identity(
        row.get("full_name")
        or f"{row.get('first_name') or ''} {row.get('last_name') or ''}"
    )


def safe_spreadsheet_value(value: Any) -> Any:
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return f"'{value}"
    return value


@dataclass(frozen=True)
class ProvisioningItem:
    subject: str
    decision: str
    action: str
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.decision not in DECISIONS:
            raise ValueError(f"Décision inconnue: {self.decision}")


@dataclass
class ProvisioningPlan:
    project_ref: str
    items: list[ProvisioningItem] = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        return any(item.decision == "conflict" for item in self.items)

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_ref": self.project_ref,
            "summary": {
                decision: sum(item.decision == decision for item in self.items)
                for decision in sorted(DECISIONS)
            },
            "items": [asdict(item) for item in self.items],
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, indent=2, sort_keys=True)


class ProvisioningGateway(Protocol):
    def list_companies(self) -> list[dict[str, Any]]: ...
    def list_profiles(self) -> list[dict[str, Any]]: ...
    def list_accesses(self) -> list[dict[str, Any]]: ...
    def list_employees(self) -> list[dict[str, Any]]: ...
    def list_teams(self, company_id: str) -> list[dict[str, Any]]: ...
    def list_permissions_by_code(self) -> dict[str, str]: ...
    def get_user_permission_snapshot(
        self, user_id: str, company_id: str
    ) -> list[dict[str, Any]]: ...
    def create_account(
        self,
        email: str,
        name: str,
        password: str,
        *,
        company_id: str,
        role: str = "custom",
        username: str | None = None,
    ) -> str: ...
    def create_access(self, user_id: str, company_id: str, role: str) -> None: ...
    def update_access_role(self, access_id: str, role: str) -> None: ...
    def deactivate_access(self, access_id: str) -> None: ...
    def set_must_change_password(self, user_id: str, value: bool) -> None: ...
    def replace_permission_grants(
        self,
        user_id: str,
        company_id: str,
        granted_by: str,
        grants: list[dict[str, Any]],
    ) -> None: ...


class AccessProvisioner:
    """Transforme un manifeste et un état DB en décisions applicables."""

    def __init__(self, manifest: dict[str, Any], gateway: ProvisioningGateway) -> None:
        self.manifest = manifest
        self.gateway = gateway

    def plan(self) -> ProvisioningPlan:
        companies = self._companies_by_alias()
        profiles = self.gateway.list_profiles()
        accesses = self.gateway.list_accesses()
        employees = self.gateway.list_employees()
        permission_ids = self.gateway.list_permissions_by_code()
        items: list[ProvisioningItem] = []

        for person in self.manifest["people"]:
            key = person["key"]
            if person.get("no_op"):
                items.append(ProvisioningItem(f"person:{key}", "no-op", "none"))
                continue

            profile, conflict = self._resolve_person(person, profiles, companies)
            if conflict:
                items.append(
                    ProvisioningItem(
                        f"account:{key}", "conflict", "resolve_identity", conflict
                    )
                )
                continue

            user_id: str | None
            if profile is None:
                if person.get("account") != "technical_login":
                    items.append(
                        ProvisioningItem(
                            f"account:{key}",
                            "conflict",
                            "resolve_identity",
                            {"reason": "Compte canonique absent; création non autorisée"},
                        )
                    )
                    continue
                name = person["identity"].get("name", "")
                username = (person.get("identity") or {}).get("username")
                if not username and name:
                    from app.modules.employees.domain.rules import (
                        build_collaborator_username_base,
                    )

                    parts = name.split(None, 1)
                    username = build_collaborator_username_base(
                        parts[0], parts[1] if len(parts) > 1 else parts[0]
                    )
                email = (person.get("identity") or {}).get("email")
                # Auth exige un email ; l'identifiant métier exposé est prenom.nom
                if not email and username:
                    email = f"{username}@users.eywai"
                if not email or not username:
                    items.append(
                        ProvisioningItem(
                            f"account:{key}",
                            "conflict",
                            "resolve_identity",
                            {"reason": "username prenom.nom requis pour compte technique"},
                        )
                    )
                    continue
                accesses_req = person.get("accesses") or []
                primary = accesses_req[0] if accesses_req else {}
                primary_company_id = companies.get(primary.get("company")) if primary else None
                if not primary_company_id:
                    items.append(
                        ProvisioningItem(
                            f"account:{key}",
                            "conflict",
                            "resolve_company",
                            {"reason": "Entreprise primaire requise pour profiles.company_id"},
                        )
                    )
                    continue
                profile_role = primary.get("role") or "custom"
                items.append(
                    ProvisioningItem(
                        f"account:{key}",
                        "create",
                        "create_account",
                        {
                            "email": email,
                            "username": username,
                            "name": name,
                            "must_change_password": True,
                            "company_id": primary_company_id,
                            "role": profile_role,
                        },
                    )
                )
                user_id = None
            else:
                user_id = str(profile["id"])
                items.append(
                    ProvisioningItem(
                        f"account:{key}",
                        "no-op",
                        "none",
                        {"user_id": user_id},
                    )
                )

            for requested in person.get("accesses", []):
                company_alias = requested["company"]
                company_id = companies.get(company_alias)
                subject = f"access:{key}:{company_alias}"
                if not company_id:
                    items.append(
                        ProvisioningItem(
                            subject,
                            "conflict",
                            "resolve_company",
                            {"company": company_alias},
                        )
                    )
                    continue

                existing = self._find_access(accesses, user_id, company_id)
                if existing and existing.get("role") == requested["role"]:
                    items.append(
                        ProvisioningItem(
                            subject,
                            "no-op",
                            "none",
                            {"access_id": existing.get("id")},
                        )
                    )
                elif existing and self._role_upgrade_allowed(
                    existing.get("role"), requested["role"]
                ):
                    items.append(
                        ProvisioningItem(
                            subject,
                            "reuse",
                            "update_access_role",
                            {
                                "access_id": existing["id"],
                                "role": requested["role"],
                                "previous_role": existing.get("role"),
                            },
                        )
                    )
                elif existing:
                    items.append(
                        ProvisioningItem(
                            subject,
                            "conflict",
                            "role_mismatch",
                            {
                                "existing_role": existing.get("role"),
                                "requested_role": requested["role"],
                            },
                        )
                    )
                else:
                    items.append(
                        ProvisioningItem(
                            subject,
                            "create",
                            "create_access",
                            {
                                "user_key": key,
                                "company_id": company_id,
                                "role": requested["role"],
                            },
                        )
                    )

                grant_item = self._plan_grants(
                    key=key,
                    person=person,
                    requested=requested,
                    company_id=company_id,
                    user_id=user_id,
                    employees=employees,
                    permission_ids=permission_ids,
                )
                if grant_item:
                    items.append(grant_item)

            if person.get("sync_accesses") and user_id:
                wanted_company_ids = {
                    companies[a["company"]]
                    for a in person.get("accesses") or []
                    if a.get("company") in companies
                }
                for access in accesses:
                    if str(access.get("user_id")) != str(user_id):
                        continue
                    if access.get("is_active") is False:
                        continue
                    if str(access.get("company_id")) in wanted_company_ids:
                        continue
                    items.append(
                        ProvisioningItem(
                            f"access:{key}:revoke:{access.get('id')}",
                            "reuse",
                            "deactivate_stale_access",
                            {
                                "access_id": access["id"],
                                "company_id": access.get("company_id"),
                            },
                        )
                    )

            if person.get("duplicate_access", {}).get("deactivate") and profile:
                for duplicate in self._duplicate_profiles(
                    person, profiles, profile["id"]
                ):
                    for access in accesses:
                        if str(access["user_id"]) != str(duplicate["id"]):
                            continue
                        if access.get("is_active") is False:
                            continue
                        items.append(
                            ProvisioningItem(
                                f"duplicate:{key}:{duplicate['id']}:{access['id']}",
                                "reuse",
                                "deactivate_duplicate",
                                {
                                    "access_id": access["id"],
                                    "source_user_id": duplicate["id"],
                                },
                            )
                        )

        return ProvisioningPlan(project_ref=PROJECT_REF, items=items)

    def apply(
        self,
        plan: ProvisioningPlan,
        *,
        passwords_out: dict[str, str] | None = None,
        granted_by: str = "00000000-0000-0000-0000-000000000000",
    ) -> dict[str, str]:
        """Applique un plan sans conflit. Retourne {user_key: password} pour les créations."""
        if plan.has_conflicts:
            raise ValueError("Préflight en conflit: aucune écriture n'est autorisée")
        account_ids: dict[str, str] = {}
        created_passwords: dict[str, str] = {}

        for item in plan.items:
            if item.subject.startswith("account:") and item.decision == "no-op":
                account_ids[item.subject.removeprefix("account:")] = item.details[
                    "user_id"
                ]
            elif item.action == "create_account":
                password = generate_initial_password()
                user_id = self.gateway.create_account(
                    item.details["email"],
                    item.details["name"],
                    password,
                    company_id=item.details["company_id"],
                    role=item.details.get("role") or "custom",
                    username=item.details.get("username"),
                )
                self.gateway.set_must_change_password(user_id, True)
                key = item.subject.removeprefix("account:")
                account_ids[key] = user_id
                created_passwords[key] = password

        for item in plan.items:
            if item.action == "create_access":
                self.gateway.create_access(
                    account_ids[item.details["user_key"]],
                    item.details["company_id"],
                    item.details["role"],
                )
            elif item.action == "update_access_role":
                self.gateway.update_access_role(
                    item.details["access_id"], item.details["role"]
                )
            elif item.action == "deactivate_duplicate":
                self.gateway.deactivate_access(item.details["access_id"])
            elif item.action == "deactivate_stale_access":
                self.gateway.deactivate_access(item.details["access_id"])
            elif item.action == "replace_grants":
                user_key = item.details["user_key"]
                user_id = account_ids.get(user_key) or item.details.get("user_id")
                if not user_id:
                    raise ValueError(f"user_id manquant pour grants {user_key}")
                self.gateway.replace_permission_grants(
                    user_id=str(user_id),
                    company_id=item.details["company_id"],
                    granted_by=granted_by,
                    grants=item.details["grants"],
                )

        if passwords_out is not None:
            passwords_out.update(created_passwords)
        return created_passwords

    def _plan_grants(
        self,
        *,
        key: str,
        person: dict[str, Any],
        requested: dict[str, Any],
        company_id: str,
        user_id: str | None,
        employees: list[dict[str, Any]],
        permission_ids: dict[str, str],
    ) -> ProvisioningItem | None:
        codes = self._permission_codes_for_access(person, requested)
        if not codes and requested.get("role") in ("admin", "rh"):
            # Rôles pleins : pas de grants custom obligatoires
            return None
        if not codes:
            return None

        scope_mode = requested.get("scope_mode") or "company"
        team_ids: list[str] = []
        if scope_mode == "teams":
            team_names = requested.get("team_names") or []
            live_teams = self.gateway.list_teams(company_id)
            by_name = {
                normalize_identity(t.get("name")): str(t["id"]) for t in live_teams
            }
            for name in team_names:
                tid = by_name.get(normalize_identity(name))
                if not tid:
                    return ProvisioningItem(
                        f"grants:{key}:{requested['company']}",
                        "conflict",
                        "resolve_team",
                        {"team_name": name, "company_id": company_id},
                    )
                team_ids.append(tid)

        grants: list[dict[str, Any]] = []
        missing: list[str] = []
        for code in codes:
            pid = permission_ids.get(code)
            if not pid:
                missing.append(code)
                continue
            targets = self._targets_for_permission(
                person=person,
                company_alias=requested["company"],
                company_id=company_id,
                permission_code=code,
                user_id=user_id,
                employees=employees,
            )
            if isinstance(targets, dict) and targets.get("conflict"):
                return ProvisioningItem(
                    f"grants:{key}:{requested['company']}",
                    "conflict",
                    "resolve_employee_target",
                    targets,
                )
            grant_scope = scope_mode
            # Exceptions allow sur scope none (Michael payslips cross-company)
            if requested.get("scope_mode") == "none":
                grant_scope = "none"
            grants.append(
                {
                    "permission_id": pid,
                    "permission_code": code,
                    "scope_mode": grant_scope,
                    "team_ids": list(team_ids) if grant_scope == "teams" else [],
                    "targets": targets,
                }
            )
        if missing:
            return ProvisioningItem(
                f"grants:{key}:{requested['company']}",
                "conflict",
                "resolve_permission",
                {"missing": missing},
            )

        # Idempotence : comparer au snapshot si user connu
        if user_id:
            current = self.gateway.get_user_permission_snapshot(user_id, company_id)
            if self._grants_equivalent(current, grants):
                return ProvisioningItem(
                    f"grants:{key}:{requested['company']}",
                    "no-op",
                    "none",
                    {"company_id": company_id},
                )

        return ProvisioningItem(
            f"grants:{key}:{requested['company']}",
            "create" if user_id is None else "reuse",
            "replace_grants",
            {
                "user_key": key,
                "user_id": user_id,
                "company_id": company_id,
                "grants": grants,
            },
        )

    def _permission_codes_for_access(
        self, person: dict[str, Any], requested: dict[str, Any]
    ) -> list[str]:
        sets = self.manifest.get("permission_sets") or {}
        codes: list[str] = []
        if requested.get("permission_set"):
            codes.extend(sets.get(requested["permission_set"]) or [])
        codes.extend(requested.get("permission_codes") or [])
        # permissions globales person.permissions (legacy)
        for ref in person.get("permissions") or []:
            if isinstance(ref, str) and ref in sets:
                codes.extend(sets[ref])
            elif isinstance(ref, str):
                codes.append(ref)
        # Déduplique en conservant l'ordre
        seen: set[str] = set()
        out: list[str] = []
        for c in codes:
            if c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def _targets_for_permission(
        self,
        *,
        person: dict[str, Any],
        company_alias: str,
        company_id: str,
        permission_code: str,
        user_id: str | None,
        employees: list[dict[str, Any]],
    ) -> list[dict[str, str]] | dict[str, Any]:
        targets: list[dict[str, str]] = []
        for exc in person.get("target_exceptions") or []:
            if exc.get("company") and exc["company"] != company_alias:
                continue
            if exc.get("permission") != permission_code:
                continue
            effect = exc.get("effect")
            if effect not in ("allow", "deny"):
                return {"conflict": True, "reason": "effect invalide", "exc": exc}
            if (exc.get("employee") or {}).get("self"):
                if not user_id:
                    return {
                        "conflict": True,
                        "reason": "self target sans user_id",
                    }
                self_emps = [
                    e
                    for e in employees
                    if str(e.get("user_id") or e.get("id")) == str(user_id)
                    and str(e.get("company_id")) == str(company_id)
                ]
                if len(self_emps) != 1:
                    # fallback : employee.id == user_id (comptes liés 1:1)
                    self_emps = [
                        e
                        for e in employees
                        if str(e.get("id")) == str(user_id)
                        and str(e.get("company_id")) == str(company_id)
                    ]
                if len(self_emps) != 1:
                    return {
                        "conflict": True,
                        "reason": "employé self introuvable",
                        "user_id": user_id,
                        "company_id": company_id,
                    }
                targets.append(
                    {"employee_id": str(self_emps[0]["id"]), "effect": effect}
                )
                continue
            for name in exc.get("employees") or []:
                matches = [
                    e
                    for e in employees
                    if str(e.get("company_id")) == str(company_id)
                    and normalized_full_name(e) == normalize_identity(name)
                ]
                if len(matches) != 1:
                    return {
                        "conflict": True,
                        "reason": "cible salarié ambiguë ou absente",
                        "name": name,
                        "company_id": company_id,
                        "matches": [m["id"] for m in matches],
                    }
                targets.append(
                    {"employee_id": str(matches[0]["id"]), "effect": effect}
                )
        return targets

    def _grants_equivalent(
        self, current: list[dict[str, Any]], desired: list[dict[str, Any]]
    ) -> bool:
        def norm(rows: list[dict[str, Any]]) -> list[tuple]:
            out = []
            for g in rows:
                teams = tuple(sorted(str(t) for t in (g.get("team_ids") or [])))
                targets = tuple(
                    sorted(
                        (
                            str(t.get("employee_id")),
                            str(t.get("effect")),
                        )
                        for t in (g.get("targets") or [])
                    )
                )
                out.append(
                    (
                        str(g.get("permission_id") or g.get("permission_code")),
                        str(g.get("scope_mode") or "company"),
                        teams,
                        targets,
                    )
                )
            return sorted(out)

        # Compare on permission_id when available
        cur_by_code = {
            str(g.get("permission_code") or g.get("permission_id")): g for g in current
        }
        des_by_code = {
            str(g.get("permission_code") or g.get("permission_id")): g for g in desired
        }
        if set(cur_by_code) != set(des_by_code):
            return False
        return norm(current) == norm(desired)

    def _companies_by_alias(self) -> dict[str, str]:
        resolved: dict[str, str] = {}
        live = self.gateway.list_companies()
        for alias, names in self.manifest["companies"].items():
            wanted = {normalize_identity(n) for n in names}
            matches = [
                row
                for row in live
                if normalize_identity(row.get("company_name")) in wanted
            ]
            if len(matches) == 1:
                resolved[alias] = str(matches[0]["id"])
        return resolved

    def _resolve_person(
        self,
        person: dict[str, Any],
        profiles: list[dict[str, Any]],
        companies: dict[str, str],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        identity = person["identity"]
        email = identity.get("email")
        if email:
            matches = [
                row
                for row in profiles
                if normalize_identity(row.get("email")) == normalize_identity(email)
            ]
            if len(matches) == 1:
                return matches[0], None
            if len(matches) > 1:
                return None, {
                    "reason": "E-mail ambigu",
                    "matches": [row["id"] for row in matches],
                }
            # technical_login : email pas encore créé → None sans conflit
            if person.get("account") == "technical_login":
                return None, None

        name = normalize_identity(identity.get("name"))
        matches = [row for row in profiles if normalized_full_name(row) == name]
        if person.get("canonical_employee_account") and person.get("prefer_role"):
            preferred = [
                m for m in matches if (m.get("role") or "") == person["prefer_role"]
            ]
            if len(preferred) == 1:
                return preferred[0], None
        if person.get("active_account_hint"):
            company_id = companies.get(person["active_account_hint"])
            if company_id:
                hinted = [
                    m
                    for m in matches
                    if company_id
                    in {
                        str(c)
                        for c in (m.get("company_ids") or [])
                        if c
                    }
                    or str(m.get("primary_company_id") or "") == company_id
                ]
                if len(hinted) == 1:
                    return hinted[0], None
        if len(matches) == 1:
            return matches[0], None
        if len(matches) > 1:
            return None, {
                "reason": "Nom ambigu",
                "matches": [row["id"] for row in matches],
            }
        return None, None

    def _duplicate_profiles(
        self, person: dict[str, Any], profiles: list[dict[str, Any]], canonical_id: str
    ) -> list[dict[str, Any]]:
        name = normalize_identity(person["identity"].get("name"))
        return [
            row
            for row in profiles
            if str(row["id"]) != str(canonical_id)
            and normalized_full_name(row) == name
        ]

    @staticmethod
    def _role_upgrade_allowed(existing: str | None, requested: str) -> bool:
        """Autorise collaborateur→custom/rh/admin et custom→rh/admin; refuse les rétrogrades."""
        order = {
            "collaborateur": 0,
            "collaborateur_rh": 1,
            "custom": 2,
            "rh": 3,
            "admin": 4,
        }
        if existing is None:
            return False
        return order.get(requested, -1) >= order.get(existing, 99)

    @staticmethod
    def _find_access(
        accesses: list[dict[str, Any]], user_id: str | None, company_id: str
    ) -> dict[str, Any] | None:
        if not user_id:
            return None
        for access in accesses:
            if str(access.get("user_id")) != str(user_id):
                continue
            if str(access.get("company_id")) != str(company_id):
                continue
            if access.get("is_active") is False:
                continue
            return access
        return None


def generate_initial_password() -> str:
    """Mot de passe temporaire fort, sans préfixe marque (transmission Excel une fois)."""
    # 24 chars url-safe + chiffre/lettre maj pour diversifier les contraintes courantes
    return f"{secrets.token_urlsafe(18)}{secrets.randbelow(90) + 10}A"


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def build_access_summaries(manifest: dict[str, Any]) -> dict[str, str]:
    """Résumé humain des droits pour l'Excel (sans secrets)."""
    company_labels = {
        "mbc": "Mont Blanc Composite",
        "cartol": "Cartol Industrie",
        "lewis": "LEWIS",
        "colorplast": "Colorplast",
        "comitech": "Comitech Composite",
        "maji": "MAJI",
        "zone_404": "Zone 404 Mars",
    }
    role_labels = {
        "admin": "Administrateur (accès complet)",
        "rh": "RH (accès complet — paie, bulletins, NDF, planning, avances…)",
        "custom": "Personnalisé",
    }
    sets = manifest.get("permission_sets") or {}
    code_labels = {
        "payslips.validate": "Valider bulletins",
        "expenses.approve": "Approuver notes de frais",
        "schedules.validate": "Valider plannings",
        "schedules.view_all": "Voir tous les plannings",
        "schedules.update": "Modifier plannings",
        "advances.approve": "Approuver avances",
        "advances.view_all": "Voir toutes les avances",
        "advances.process": "Traiter avances",
        "enroll_employee_training": "Inscrire formations",
        "view_objectives_reporting": "Reporting objectifs",
        "evaluate_objective": "Évaluer objectifs",
        "create_individual_objective": "Créer objectifs",
        "analytics.export": "Exporter analytics",
        "analytics.view_all": "Voir analytics",
        "contracts.view_all": "Contrats (lecture)",
        "bank_dispatch.send": "Envoi dispatch bancaire",
    }
    out: dict[str, str] = {}
    for person in manifest.get("people") or []:
        if person.get("no_op"):
            continue
        key = person["key"]
        lines: list[str] = []
        for access in person.get("accesses") or []:
            alias = access["company"]
            label = company_labels.get(alias, alias)
            role = access.get("role") or "custom"
            head = f"• {label} — {role_labels.get(role, role)}"
            extras: list[str] = []
            scope = access.get("scope_mode") or "company"
            if role == "custom":
                if scope == "teams":
                    teams = ", ".join(access.get("team_names") or [])
                    extras.append(f"Périmètre équipes {teams}")
                elif scope == "none":
                    extras.append("Périmètre exceptions nominatives uniquement")
                else:
                    extras.append("Périmètre toute l’entreprise")
            codes: list[str] = []
            if access.get("permission_set"):
                codes.extend(sets.get(access["permission_set"]) or [])
            codes.extend(access.get("permission_codes") or [])
            if role == "custom" and codes:
                labels = [code_labels.get(c, c) for c in codes]
                extras.append("Actions : " + ", ".join(labels))
            elif codes and "bank_dispatch.send" in codes:
                extras.append("Envoi dispatch bancaire inclus")
            lines.append(head)
            for extra in extras:
                lines.append(f"  – {extra}")
        for exc in person.get("target_exceptions") or []:
            company = company_labels.get(exc.get("company"), exc.get("company"))
            perm = code_labels.get(exc.get("permission"), exc.get("permission"))
            effect = "exclu" if exc.get("effect") == "deny" else "autorisé"
            who = "soi-même" if (exc.get("employee") or {}).get("self") else ", ".join(
                exc.get("employees") or []
            )
            lines.append(f"  – Exception — {perm} ({company}): {who} ({effect})")
        out[key] = "\n".join(lines)
    return out


def write_access_workbook(
    plan: ProvisioningPlan,
    output_path: Path,
    passwords: dict[str, str] | None = None,
    usernames: dict[str, str] | None = None,
    access_summaries: dict[str, str] | None = None,
    names: dict[str, str] | None = None,
) -> None:
    """Écrit le relevé local (0600). Colonnes : Identifiant, Nom, Mot de passe, Droits."""
    import os

    from openpyxl import Workbook
    from openpyxl.styles import Alignment

    if passwords is None:
        raise ValueError("La génération du classeur de mots de passe exige un apply")
    usernames = usernames or {}
    access_summaries = access_summaries or {}
    names = names or {}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Comptes"
    headers = ["Identifiant", "Nom", "Mot de passe", "Droits et accès"]
    sheet.append(headers)
    sheet.column_dimensions["A"].width = 28
    sheet.column_dimensions["B"].width = 28
    sheet.column_dimensions["C"].width = 36
    sheet.column_dimensions["D"].width = 90

    for item in plan.items:
        if not item.subject.startswith("account:"):
            continue
        key = item.subject.removeprefix("account:")
        ident = usernames.get(key) or item.details.get("username") or key
        name = (
            item.details.get("name")
            or names.get(key)
            or ""
        )
        pwd = passwords.get(key, "")
        droits = access_summaries.get(key) or item.details.get("access_summary") or ""
        sheet.append(
            [
                safe_spreadsheet_value(ident),
                safe_spreadsheet_value(name),
                safe_spreadsheet_value(pwd),
                safe_spreadsheet_value(droits),
            ]
        )
        sheet.row_dimensions[sheet.max_row].height = min(
            220, 15 + 14 * (1 + str(droits).count("\n"))
        )

    for cell in sheet["D"]:
        cell.alignment = Alignment(wrap_text=True, vertical="top")

    workbook.save(str(output_path))
    os.chmod(output_path, 0o600)


class InMemoryProvisioningGateway:
    """Gateway de tests / second run no-op."""

    def __init__(
        self,
        *,
        companies: list[dict[str, Any]] | None = None,
        profiles: list[dict[str, Any]] | None = None,
        accesses: list[dict[str, Any]] | None = None,
        employees: list[dict[str, Any]] | None = None,
        teams: dict[str, list[dict[str, Any]]] | None = None,
        permissions: dict[str, str] | None = None,
    ) -> None:
        self.companies = companies or []
        self.profiles = profiles or []
        self.accesses = accesses or []
        self.employees = employees or []
        self.teams = teams or {}
        self.permissions = permissions or {}
        self.grants: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._seq = 0

    def list_companies(self) -> list[dict[str, Any]]:
        return list(self.companies)

    def list_profiles(self) -> list[dict[str, Any]]:
        return list(self.profiles)

    def list_accesses(self) -> list[dict[str, Any]]:
        return list(self.accesses)

    def list_employees(self) -> list[dict[str, Any]]:
        return list(self.employees)

    def list_teams(self, company_id: str) -> list[dict[str, Any]]:
        return list(self.teams.get(company_id, []))

    def list_permissions_by_code(self) -> dict[str, str]:
        return dict(self.permissions)

    def get_user_permission_snapshot(
        self, user_id: str, company_id: str
    ) -> list[dict[str, Any]]:
        return list(self.grants.get((user_id, company_id), []))

    def create_account(
        self,
        email: str,
        name: str,
        password: str,
        *,
        company_id: str,
        role: str = "custom",
        username: str | None = None,
    ) -> str:
        self._seq += 1
        user_id = f"u-{self._seq}"
        first_name, _, last_name = name.partition(" ")
        self.profiles.append(
            {
                "id": user_id,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "company_id": company_id,
                "role": role,
                "username": username,
                "must_change_password": False,
            }
        )
        return user_id

    def create_access(self, user_id: str, company_id: str, role: str) -> None:
        self._seq += 1
        self.accesses.append(
            {
                "id": f"a-{self._seq}",
                "user_id": user_id,
                "company_id": company_id,
                "role": role,
                "is_active": True,
            }
        )

    def update_access_role(self, access_id: str, role: str) -> None:
        for row in self.accesses:
            if row["id"] == access_id:
                row["role"] = role

    def deactivate_access(self, access_id: str) -> None:
        for row in self.accesses:
            if row["id"] == access_id:
                row["is_active"] = False

    def set_must_change_password(self, user_id: str, value: bool) -> None:
        for row in self.profiles:
            if row["id"] == user_id:
                row["must_change_password"] = value

    def replace_permission_grants(
        self,
        user_id: str,
        company_id: str,
        granted_by: str,
        grants: list[dict[str, Any]],
    ) -> None:
        self.grants[(user_id, company_id)] = list(grants)
