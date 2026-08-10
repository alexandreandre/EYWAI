"""Passe nos DSN au validateur officiel DSN-VAL et dépouille son rapport.

DSN-VAL est l'outil de la CNAV distribué par net-entreprises. Il dit ce qu'un
dépôt refuserait, ce que la comparaison au fichier du cabinet ne dit pas :
`dsn_conformance_report.py` mesure un écart, celui-ci mesure une conformité.

Installation (une fois, ~110 Mo) — l'outil n'est pas versionné :

    curl -L -o /tmp/dsnval.zip \\
      https://dsn-val.net-entreprises.fr/2026.1/autocontrole-dsn-val_linux_2026.1.0.16_64.zip
    unzip -q /tmp/dsnval.zip -d data/_outils/dsnval

⚠️ Sur macOS, il n'existe pas de build officiel : on prend celui de Linux et on
force la plateforme (`-os linux -ws gtk -arch x86_64`). Equinox détecte sinon
`macosx/aarch64`, ne résout aucun bundle et s'arrête. Il faut aussi un **Java 8
ou 11** — Java 21 ne convient pas. L'erreur `NoClassDefFoundError SWTError`
dans la sortie est sans conséquence : c'est l'atelier graphique qui refuse de
démarrer, la validation en mode batch se poursuit.

Usage :
    python scripts/dsn_valider.py --societe colorplast
    python scripts/dsn_valider.py --tout          # les 5 sociétés, nous + cabinet
    python scripts/dsn_valider.py --rapports-seuls  # redépouiller sans revalider
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

RACINE = Path(__file__).resolve().parents[2]
A_VALIDER = RACINE / "data" / "_dsn_conformance" / "_a_valider"
RAPPORTS = RACINE / "data" / "_dsn_conformance" / "_rapports_dsnval"
DSNVAL = Path(os.environ.get("DSNVAL_HOME", RACINE / "data" / "_outils" / "dsnval"))

#: Java 8 ou 11 obligatoire. Corretto 11 arm64 est celui du poste de dev.
JAVA_DEFAUT = "/Library/Java/JavaVirtualMachines/amazon-corretto-11.jdk/Contents/Home/bin/java"


def valider(fichier: Path) -> Path | None:
    """Lance DSN-VAL sur un fichier, renvoie le chemin du rapport XML."""
    script = DSNVAL / "Autocontrol-ValidateurModeBatchLinux64.sh"
    if not script.exists():
        print(f"DSN-VAL introuvable dans {DSNVAL} — voir l'entête du script.")
        return None

    RAPPORTS.mkdir(parents=True, exist_ok=True)
    environnement = dict(os.environ)
    environnement.setdefault("DSNVAL_JAVA", os.environ.get("DSNVAL_JAVA", JAVA_DEFAUT))

    resultat = subprocess.run(
        [
            "sh",
            str(script),
            "--noCheckUpdate",
            # macOS : forcer la plateforme, sinon Equinox ne résout rien.
            "-os", "linux", "-ws", "gtk", "-arch", "x86_64",
            "-o", str(RAPPORTS),
            str(fichier),
        ],
        capture_output=True,
        text=True,
        env=environnement,
        cwd=str(DSNVAL),
    )
    trouve = re.search(r"Nombre d'anomalies : (\d+)", resultat.stdout)
    nombre = trouve.group(1) if trouve else "?"
    print(f"  {fichier.name:<36} {nombre:>6} anomalies")
    rapport = RAPPORTS / f"{fichier.name}.xml"
    return rapport if rapport.exists() else None


def depouiller() -> None:
    """Agrège tous les rapports de *nos* fichiers, par règle et par impact."""
    par_regle: dict[str, dict] = defaultdict(
        lambda: {"n": 0, "societes": set(), "bloquant": False, "msg": ""}
    )
    totaux: dict[str, int] = {}

    for chemin in sorted(RAPPORTS.glob("*-eywai.dsn.xml")):
        societe = chemin.name.split("-")[0]
        noeuds = [
            n
            for n in ET.parse(chemin).getroot().iter()
            if n.tag.split("}")[-1] == "declaration_anomalie"
        ]
        totaux[societe] = len(noeuds)
        for anomalie in noeuds:
            description = next(
                (c for c in anomalie if c.tag.split("}")[-1] == "description"), None
            )
            if description is None:
                continue
            champs = {
                c.tag.split("}")[-1]: (c.text or "").strip() for c in description
            }
            code = champs.get("code", "?")
            message = re.sub(r"\s+", " ", champs.get("message", "?"))
            # Les règles de structure citent la rubrique dans le message :
            # les regrouper par bloc, sinon on lit 200 lignes pour un seul défaut.
            cle = code
            if code in ("CST-02", "CST-03"):
                bloc = re.search(r"S\d{2}\.G\d{2}\.\d{2}", message)
                cle = f"{code} {bloc.group(0)}" if bloc else code
            entree = par_regle[cle]
            entree["n"] += 1
            entree["societes"].add(societe)
            entree["bloquant"] |= champs.get("categorie") == "bloquant"
            entree["msg"] = entree["msg"] or message

    if not totaux:
        print(f"Aucun rapport dans {RAPPORTS}.")
        return

    detail = ", ".join(f"{s} {n}" for s, n in sorted(totaux.items()))
    print(f"\nAnomalies par société : {detail}")
    print(f"Total {sum(totaux.values())}, pour {len(par_regle)} règles distinctes.\n")
    print(f"{'':1}{'règle':<25} {'occ':>6} {'soc':>4}  message")
    print("-" * 108)
    for cle, e in sorted(par_regle.items(), key=lambda kv: -kv[1]["n"]):
        marque = "!" if e["bloquant"] else " "
        print(f"{marque}{cle:<25} {e['n']:>6} {len(e['societes']):>4}  {e['msg'][:76]}")
    print("\n!  = bloquant : le dépôt serait refusé.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--societe")
    parser.add_argument("--tout", action="store_true", help="toutes les sociétés")
    parser.add_argument(
        "--rapports-seuls",
        action="store_true",
        help="redépouiller les rapports existants sans relancer la validation",
    )
    args = parser.parse_args()

    if not args.rapports_seuls:
        fichiers = sorted(A_VALIDER.glob("*.dsn"))
        if args.societe:
            fichiers = [f for f in fichiers if f.name.startswith(f"{args.societe}-")]
        if not fichiers:
            print(
                f"Aucun fichier dans {A_VALIDER}. "
                "Lancer d'abord scripts/dsn_generer_pour_validation.py"
            )
            return 1
        print(f"Validation de {len(fichiers)} fichier(s) :")
        for fichier in fichiers:
            valider(fichier)

    depouiller()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
