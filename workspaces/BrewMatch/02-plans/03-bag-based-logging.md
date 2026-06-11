# Plan — Bag-Based Brew Logging (Goal B / B1)

Created: 2026-06-11
Status: **APPROVED — not yet built** (user confirmed scope 2026-06-11; build on go-ahead)

## The problem in one sentence

Every cup you brew, you have to re-key the whole bean (origin, process, roast,
flavors…) from scratch — because the app never _saves_ a bean, it only copies
it into each brew record and forgets it at the end of the session.

## The fix in one sentence

Enter a **bag of coffee once** when you open it, then **pick it from a list**
for every brew until it runs out.

---

## How logging works today (the friction)

1. **Describe Your Beans** — fill a form every time: origin, region, process,
   roast, variety, flavor notes, altitude → _Save Bean Profile_.
2. **Recipes** — pick a recipe.
3. **Brew Session** — brew, mark complete, rate, submit.

The bean from step 1 is held only for the current session and copied into the
brew record. Refresh or come back tomorrow → it's gone → you re-type it.
There is currently **no concept of a roaster or a coffee name** anywhere in the
app — a bean is just "Ethiopia, washed, light."

---

## Confirmed decisions (locked 2026-06-11)

| Decision                                           | Choice                                            |
| -------------------------------------------------- | ------------------------------------------------- |
| Save beans as reusable **bags**                    | ✅ Yes — core of the feature                      |
| **Roaster name**                                   | ✅ Include                                        |
| **Coffee / product name** (e.g. "Ethiopia Guji")   | ✅ Include — pairs with roaster to identify a bag |
| **"Running low" counter** (brews left in the bag)  | ✅ Include now                                    |
| **Bag size default**                               | ✅ Default 250 g, editable per bag                |
| **"Running low" method**                           | ✅ Option B — capture actual dose used per brew   |
| **Editable dose on brew screen** (rescales recipe) | ✅ Include — dose drives water + pours            |

---

## What changes

**1. A new saved "bag" you own (the core change).**
The app's database today has three tables (users, brews, sessions) and nothing
for beans. We add a place to store each user's bags. A bag holds the bean
details you already enter, **plus** new fields:

- Roaster
- Coffee / product name
- Bag size in grams (e.g. 200)
- Date opened
- Active / finished flag

**2. "Describe Your Beans" becomes "Your Coffees."**
Instead of a blank form every time, you see a short list of your open bags and
tap one. An **"Add a new bag"** button opens today's form (now with
roaster / name / size added) — used **once per bag, not once per cup**.

**3. Roaster + coffee name added to the bean itself.**
So they flow into your history and diagnosis too — past brews read
"Onyx — Ethiopia Guji" instead of just "Ethiopia."

**4. Brewing barely changes.**
The brew screen already uses whatever bean is selected, so once you tap a bag
the rest of the flow is identical — just without the typing.

**5. Editable dose on the brew screen (drives accuracy for everything else).**
Today the brew screen is a read-only printout: it shows the recipe's dose (e.g.
15 g), ratio, and pour amounts, none of which can be changed. We add an
**editable dose field at the top of the brew screen**, pre-filled with the
recipe's dose. When you change it (say to 18 g), the **water total and every
pour step rescale proportionally** to keep the recipe's ratio intact
(new water = old water × your_dose ÷ recipe_dose). This fixes three things at
once: the on-screen guide matches the coffee you're actually making, the
"running low" math below uses your real dose, and the model learns from what
you truly brewed instead of an assumed 15 g.

**6. "Running low" tracking (Option B — actual dose).**
Grams left = bag size − sum of the **actual doses** you entered on the brew
screen (per section 5), not the recipe's assumed dose. Shows "≈N brews left";
marking a bag finished drops it off the active list.

**7. Existing brews are untouched.**
Purely additive. Nothing about current history changes or needs rebuilding.
Roaster / coffee name will simply be blank on brews logged before this feature.

---

## Honest cons / scope notes

- This is a **real feature, not a tweak**: a new database table, a small
  add/pick/finish-bag screen, and new fields on the bean.
- It touches the **data layer**, so it must work on **both** the local database
  and the live Supabase one — the new table has to be created on the live DB
  too (watch the dependency-lock + deploy steps from the persistence work).
- **One-time setup per bag** (~30 seconds when you open a bag), in exchange for
  zero typing across the dozen-plus cups you get from it.

---

## Affected files (for whoever builds this)

- `src/data_models.py` — add `roaster` + `name` (and any bag fields) to the bean
  model / a new bag model.
- `src/app/db.py` — new `coffee_bags` table in `init_db` (SQLite **and**
  Postgres), plus CRUD helpers (create / list-active / mark-finished / grams-used).
- `src/app/pages/bean_input.py` — becomes the "Your Coffees" picker + add-bag form.
- `src/app/pages/brew_session.py` — add the editable dose field at the top;
  rescale water + every pour step by `your_dose ÷ recipe_dose`; remember which
  bag a brew came from; feed the actual dose into the "running low" counter;
  carry roaster/name into the brew record.
- `tests/` — unit tests for the new table + helpers; a unit test for the
  proportional rescaling math (dose change → water/pours scale, ratio preserved);
  a regression test proving a saved bag is reusable across sessions and the
  actual-dose subtraction decrements it.

---

## Open follow-ups (not part of this plan)

- This is **B1** of Goal B. B2 (retrain button) and B3 (learning indicator)
  remain separate.
- Whether to keep a "quick one-off bean without saving a bag" escape hatch —
  defer; default is bags-first.
