# Brief direction artistique — à copier et remplir

Coller ce bloc dans le chat (ou un fichier `da-brief.md`) en complétant chaque section. Plus le brief est précis, plus la refonte sera cohérente sans retouches UX.

---

## Prompt DA (modèle)

```
/refonte-da

## Contexte produit
- Application : EYWAI (SIRH / RH)
- Public : [ex. DRH, managers, employés, super-admin]
- Ton de marque : [ex. institutionnel sobre / chaleureux humain / tech premium / etc.]
- Références visuelles (liens, captures, noms) : [optionnel]

## Palette (HSL de préférence, ou noms + intention)
- Primary (action principale) : [ex. 220 70% 40% — bleu profond]
- Primary foreground (texte sur primary) : [ex. 0 0% 100%]
- Secondary (surfaces secondaires) : [...]
- Accent (mise en avant, pas forcément vert) : [...]
- Background / Foreground (texte corps) : [...]
- Muted (fonds discrets, texte secondaire) : [...]
- Success / Warning / Danger (sémantiques) : [...]
- Border / Input / Ring (focus) : [...]

## Sidebar (si spécifique)
- Fond sidebar : [...]
- Item actif / hover : [...]
- Bordure : [...]

## Typographie
- Famille titres : [ex. garder système / Inter / etc.]
- Famille corps : [...]
- Échelle : [ex. plus compact / plus aéré — sans changer la structure des pages]
- Graisses dominantes : [ex. 500 titres, 400 corps]

## Formes & profondeur
- Border radius global (--radius) : [ex. 0.375rem sobre / 0.75rem doux / 0 presque carré]
- Ombres : [ex. plates / légères / marquées — décrire intention]
- Dégradés : [oui/non — où : cartes KPI, headers, boutons primary uniquement, etc.]

## Motion
- Vitesse : [ex. 150ms discret / 300ms actuel]
- Style : [ease standard / pas de bounce]

## Modes
- Thème sombre : [obligatoire / optionnel / à repenser entièrement]
- Contraintes : [ex. primary plus clair en dark, fond pas #000 pur]

## Graphiques & données
- Style séries : [monochrome primary / palette harmonisée de N couleurs]
- Grille / axes : [discrets muted / contrastés]

## Interdits explicites
- [ex. pas de violet, pas de vert fluo, pas de coins pill partout]

## Périmètre de cette session
- [ ] Tout le site
- [ ] Sous-ensemble : [lister routes ou zones]

## Notes libres
[autres contraintes marque, logo, favicon, etc.]
```

---

## Exemple minimal rempli

```
/refonte-da

## Contexte produit
- Ton : institutionnel moderne, rassurant RH
- Références : Linear.app sobriété + touches chaudes

## Palette
- Primary : 215 50% 32%
- Accent : 25 85% 52% (terracotta, remplace le vert succès décoratif)
- Background : 40 20% 98%
- Foreground : 215 25% 18%
- Success : 152 45% 38% | Warning : 38 90% 48% | Danger : 0 72% 55%
- Radius : 0.375rem, ombres légères, dégradés uniquement sur CTA primary

## Typo
- Inter partout, titres semibold, corps regular

## Modes
- Dark : fond 215 20% 10%, primary plus lumineux

## Interdits
- Pas de gradient violet/bleu, pas de green-500 Tailwind en dur

## Périmètre
- Tout le site
```
