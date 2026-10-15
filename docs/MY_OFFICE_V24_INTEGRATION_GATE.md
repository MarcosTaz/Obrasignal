# My Office — staged integration contract (V24)
This is a **non-activated** integration contract. It does not change the existing web entry, login, Radar, Profile, mobile entry or production site.

## Truth / module routing
Only `radar` and `profile` are confirmed as existing routes in `mobile/App.web.js`. The remaining five modules are explicitly `not-integrated`. No fictitious opportunities, scores, dossiers or exports are created.

## Visual approval gate
The historically approved seven scenes and 49 individually calibrated window geometries are NOT in this commit. The V23 candidate zip contains only the Champagne scene. The V24 preliminary local zip has a 3.6 MB Champagne raster and coarse clickable hotspots: it is not proof of exact alignment nor native-16K rendering. Do not replace the approved visuals with a generic grid or activate this feature.

## Next controlled phases
1. Import and checksum all approved scene masters, including six missing images, through a verified asset pipeline.
2. Implement seven independently calibrated maps (49 real HTML/React windows), deterministic FocusLayer transitions and stable typography.
3. Connect each area to authenticated tenant-scoped API endpoints; fail closed with UNKNOWN for incomplete evidence.
4. Test auth, tenant separation, routes, accessibility, rapid cursor transitions, screenshot geometry, reduced motion, mobile, five locales, and performance budgets.
5. Keep feature gated until tests and visual approval. Then open a reviewable PR; no merge or production deploy without explicit authorization.

Run this contract's regression suite: `node --test mobile/src/my-office-contract.test.mjs`.
