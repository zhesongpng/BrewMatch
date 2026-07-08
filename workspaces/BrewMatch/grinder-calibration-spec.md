# Grinder Calibration Spec

Source of truth for how BrewMatch translates a recipe's grind target into each
grinder's own setting. Rebuilt 2026-07-06 from manufacturer-official and
authoritative references after the old catalog (a hand-estimated generic-1-10 →
clicks table) produced wrong, confusing numbers.

## Why the old model was wrong

1. **Raw "clicks" is not a shared unit.** Electric grinders read a printed dial
   number (no zeroing); hand grinders count clicks/rotations from a zero point.
   One "clicks" column can't serve both.
2. **Variants change the numbers ~3.6×.** The Timemore C3/C3S moves 83 µm per
   click; the C3 ESP moves 23 µm per click. The same grind size needs ~3.6× more
   clicks on the ESP. A single "Timemore C3" entry is wrong for one of them.
3. **The old numbers were outside real ranges.** The old catalog put a pour-over
   at 23 clicks on a standard C3 — but the C3/C3S only has 15 clicks per rotation
   (confirmed on a real unit — several web sources say 12, which is wrong) and a
   usable range of ~7–20 clicks total. 23 was past the coarsest recommended
   setting.
4. **"7/10" means nothing to a user.** The internal 1–10 scale (needed by the ML
   model) was shown raw. Users can't act on it.

## The model

**Anchor everything to grind size in microns** — the one physical unit true
across every grinder — then convert to each grinder's native setting and show a
plain-language coarseness band. The internal 1–10 `grind_setting` (used by the
taste model + optimizer) is kept, but is converted for display and never shown raw.

### 1-10 → microns bridge

`microns = 200 + grind_setting × 100` → setting 1 = 300 µm (fine) … setting 10 =
1200 µm (very coarse). Sensible for BrewMatch's pour-over focus; a 4:6 recipe
(~setting 7) lands at 900 µm (medium-coarse), matching the method.

### Coarseness bands (microns)

| Band          | Microns  | Methods                      |
| ------------- | -------- | ---------------------------- |
| Fine          | < 420    | Espresso                     |
| Medium        | 420–820  | V60 / pour-over              |
| Medium-coarse | 820–1020 | **Tetsu Kasuya 4:6**, Chemex |
| Coarse        | > 1020   | French press, cold brew      |

Authoritative micron targets: espresso 180–380 · pour-over/V60 500–800 · 4:6
~850–1000 (medium-coarse, coarser than a normal V60) · filter/drip 800–1000 ·
French press ~900–1300.

### Per-grinder conversion

Each grinder stores **anchor points** — `(microns, native_setting)` pairs taken
from the researched brew-method settings below. A target micron value is
linear-interpolated between the nearest anchors and clamped to the grinder's
usable range. Interpolating between real, sourced anchors is far more reliable
than a micron-per-click formula from zero (which ignores burr offset and
non-linearity, the reason third-party click numbers often miss).

Every displayed setting is a **starting point** + a taste-adjust nudge:

- sour / weak / drains fast → **finer** (fewer clicks / lower dial)
- bitter / harsh / stalls → **coarser** (more clicks / higher dial)

Hand grinders also get a "zero it first" instruction; burr wear shifts zero, so
re-zero periodically.

## Per-grinder reference (native unit + anchors)

Native value meaning: `clicks` = clicks from closed; `rotations` = turns from
closed; `dial` = printed dial number, no zeroing.

| Grinder (id)                         | Reading   | Zero? | Espresso | V60     | 4:6     | French press | Spec                                       |
| ------------------------------------ | --------- | ----- | -------- | ------- | ------- | ------------ | ------------------------------------------ |
| Timemore C3 / C3S (`timemore-c3`)    | clicks    | yes   | 7–10     | 14 ‡    | 16–18   | 18–20        | 15 clicks/rot (confirmed), range 7–20      |
| Timemore C3 ESP (`timemore-c3-esp`)  | rotations | yes   | 0.6–1.0  | 1.4–2.0 | 2.0–2.3 | 2.3–2.6      | 30 clicks/rot, 23 µm/click                 |
| Timemore C2 (`timemore-c2`)          | clicks    | yes   | 8–11     | 14–17   | 18–20   | 20–24        | range 6–24                                 |
| Kingrinder K6 (`kingrinder-k6`)      | rotations | yes   | 0.2–0.45 | 0.5–1.2 | 1.0–1.3 | 1.2–2.3      | 60 clicks/rot, 16 µm/click                 |
| Comandante C40 (`comandante-c40`)    | clicks    | yes   | 10–16    | 22–28   | 26–30   | 28–34        | red-dot zero; re-check monthly             |
| 1Zpresso K-Max (`1zpresso-kmax`)     | rotations | yes   | 1.8–2.5  | 3.5–4.5 | 4.5–5.0 | 5.0–6.0      | 90 clicks/rot, 22 µm/click                 |
| 1Zpresso J-Max (`1zpresso-jmax`)     | rotations | yes   | 1.0–1.5  | ~3.4 †  | ~4.0 †  | ~4.3 †       | 90 clicks/rot, 8.8 µm/click (fine burr)    |
| Baratza Encore (`baratza-encore`)    | dial      | no    | 8        | 15      | 19–21   | 28           | official; range 1–40                       |
| Fellow Ode Gen 2 (`fellow-ode-gen2`) | dial      | no    | —        | 4.2–5.1 | 6.0–7.0 | 9.1–10.0     | 1–11 + sub-clicks; finest ≈275 µm          |
| Niche Zero (`niche-zero`)            | dial      | no    | 5–20     | 35–45   | 40–45   | 45+          | stepless; units vary — starting point only |

† 1Zpresso J-Max filter settings are best-estimate; the official J-Max brew chart
was not retrievable. Confirm against 1zpresso.coffee/manual-jmax before treating
as authoritative.

‡ Timemore C3 V60 anchor is user-grounded (2026-07-08): 14 clicks, their real
setting for the James Hoffmann V60 recipe — not a sourced review-site range like
the other cells in this row. Espresso/4:6/French press for this grinder are
still the original review-sourced ranges, unconfirmed against a real unit.

Grinder ids are preserved from the previous catalog so saved user profiles keep
working; `timemore-c3` = the standard C3/C3S. The ESP is a new, separate entry.

## Sources

- Grind size in microns: honestcoffeeguide.com/coffee-grind-size-chart,
  thebasicbarista.com brew-method chart
- Tetsu Kasuya 4:6: beanrockcoffee.com 4:6 method, roastaroma.com Kasuya method
- Timemore C3 (C3S vs ESP, clicks/rotation): brewcoffeehome.com/timemore-c3-review,
  honestcoffeeguide.com/timemore-c3-grind-settings, coffeegeek.co C3 ESP Pro review
- Kingrinder K6: kingrinder.com/blog/gs-exterior, honestcoffeeguide.com K6
- Comandante C40: completehomebarista.com C40 settings
- 1Zpresso K-Max / J-Max: 1zpresso.coffee/grind-setting, completehomebarista.com K-Max
- Baratza Encore (official): support.clivecoffee.com baratza-recommended-grinder-settings
- Fellow Ode Gen 2: coffeemaster.app Fellow Ode Gen 2 settings
- Niche Zero: nichecoffee.co.uk ultimate grind size guide
