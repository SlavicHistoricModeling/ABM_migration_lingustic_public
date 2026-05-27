# ODD protocol: Slavic / Arabic linguistic-expansion ABM

> Documentation of the agent-based model used in this study, formatted
> per the ODD protocol (Overview, Design concepts, Details) of
> Grimm et al. (2006, 2010, 2020). This is the protocol description
> for the model in its current state at commit `acd3ae3` of
> `slavic_migration_submited_v1.py`.
>
> the parent submission and PLOS ONE both expect ODD-style documentation. This file
> is paper-ready prose (the prose instance can lift sections nearly
> verbatim into Methods §2 of the manuscript).

## 1. Purpose and patterns

### 1.1 Purpose

The model tests, rather than presumes, whether mass migration is a
demographically and logistically plausible mechanism for the Slavic
linguistic dominance documented in the Balkans by ~860 CE. The
model's primary claim is a **negative** result: under empirically
defensible inputs (replacement-level non-migrant fertility, calibrated
Justinianic-plague mortality, archaeologically-anchored migration
rates), no migration scenario short of unrealistic mass relocation
delivers the observed ~80 %+ Slavic share. A secondary, tentatively-
labelled hypothesis — a proto-Slavic substrate of 30–40 % pre-existing
Slavic speakers — is tested as one parsimonious resolution.

The model is **calibrated against the Arabic case** (Caliphal
expansion, 630–800 CE), where institutional support (jizya, military
elite, sharia, religious Arabic) is well-documented but the ABM does
not attempt to simulate. On a balanced engine, the model delivers
~36 % Arabic dominance demographically vs. the historical ~55 % — a
15 pp gap that is an **upper bound on the combined contribution of
mechanisms the ABM does not model**: institutional reinforcement
(Kennedy 2007; Versteegh 2014) AND bilingual transitional states
(Kandler 2010). The two cannot be cleanly separated without a
bilingualism workstream not yet implemented; the conservative
phrasing is therefore "combined ceiling", not "institutional
premium". This gap, not a single matched number, is the empirical
anchor for the headline argument.

### 1.2 Patterns the model is required to reproduce

- **Engine-stability pattern**: under no migration, no plague, the
  population should be approximately stationary across 260 years (the
  Slavic scenario length). The ±10 % envelope around 5,000 agents is
  the only stability gate the model is required to clear before any
  scenario claim is made. Confirmed at commit `ad8cd05`: terminal
  drift +8.1 % over 260 yr.
- **Plague-depression pattern**: under the configured differential
  plague-mortality input (15 % non-Slavic vs. 4 % Slavic, compounded
  over three plague years), the with-plague no-migration population
  settles at ~73 % of initial. This is reported as a *model output*,
  not validated against — the input parameter is itself one of the
  things being studied.
- **Arabic ~55 % target** (reinterpreted): the previous draft of this
  model claimed to "reproduce" Arabic ~55 % under default parameters.
  At the calibration we now use, this claim is no longer made: the
  model delivers ~36 % Arabic, and the 15 pp shortfall against ~55 %
  is **the finding** that the paper is built around.

## 2. Entities, state variables, and scales

### 2.1 Entities

The model has two entity types: **agents** (representing local
population aggregates) and **grid cells** (representing spatial
locations).

### 2.2 Agent state variables

| Variable | Range / type | Role |
|---|---|---|
| `id` | integer | Unique stable identifier (used to maintain start-of-year snapshots; see §3.3). |
| `x`, `y` | integers in `[0, GRID_SIZE)` | Cell coordinates on a toroidal 50 × 50 grid (`GRID_SIZE = 50`). |
| `language` | one of {slavic, illyrian_thracian, greek, germanic, avar, other} | The agent's current language, which can change through assimilation. |
| `age` | integer in `[0, MAX_AGE]` | Age in years. Initialised from the equilibrium geometric distribution under flat 2 % / yr mortality; incremented by 1 each tick. |
| `sex` | {male, female} | Determines reproductive eligibility. |

Each agent represents approximately 1,000 individuals (5,000 agents
≈ 5 M pre-migration Balkan population at scenario start).

### 2.3 Cell state variables

Grid cells hold a list of resident agent IDs. Each cell is implicitly
labelled with one of three **regions** (`balkans`, `central`,
`eastern`) determined by `(x, y)` position. The region partition
constrains which initial groups can be placed where (e.g. Slavic
agents cannot start in the Balkans, per Curta 2001's archaeological
spread).

### 2.4 Environmental variables (global)

| Variable | Value | Role |
|---|---|---|
| Current year (offset from scenario start) | `[0, params["years"])` | Drives plague-year mortality switching and the 50-yr Slavic-newcomer fertility depression window. |
| `PLAGUE_YEARS` | `[0, 10, 25]` (Slavic) / `[0, 10]` (Arabic) | Years (relative to scenario start) in which the alternate `plague_mortality` is applied. |

### 2.5 Spatial and temporal scales

- **Spatial extent**: 50 × 50 toroidal grid = 2,500 cells.
- **Spatial resolution**: one cell ≈ 2,000 individuals at the canonical
  scaling.
- **Temporal extent**: 260 yr (Slavic scenarios; 600–860 CE) or 170 yr
  (Arabic scenario; 630–800 CE).
- **Temporal resolution**: one year per tick. All processes apply
  per-year per-agent.

## 3. Process overview and scheduling

### 3.1 Tick (one model year) — process order

1. **Migration** (years 0–99 only). Add `migration_rate` Slavic agents
   per year at random positions in the eastern half of the grid
   (Slavic scenarios) or anywhere (Arabic). Migrants are uniformly
   aged 15–40, sex randomised.
2. **Start-of-year snapshots**. Build two dictionaries from the
   current agent list: `cell_langs` (cell → list of languages
   present in that cell) and `agent_id_to_lang` (id → language).
   These snapshots fix the language landscape for the rest of the
   tick so that within-tick processing is order-independent (see
   §4.5).
3. **Per-agent updates** (single pass through the agent list):
   - Increment age.
   - **Mortality**. Roll against `BASE_MORTALITY = 0.02 / yr`, except
     in `PLAGUE_YEARS` where the agent's group `plague_mortality`
     applies. Dead agents are dropped from the grid and skipped.
   - **Reproduction** (females aged 15–40 only). Roll against the
     group's per-female annual birth rate (with the newcomer-Slavic
     reduction in the eastern half during years 0–49). On a birth,
     the child's **language is set by the mother-tongue rule**
     (see §7.4): mother ≤ `INHERITANCE_AGE_MAX` (= 25) → child
     inherits mother's language; otherwise → child draws from the
     local cell-pool, with a 3-other-agent fallback to the
     mother's language.
   - **Assimilation** (using the start-of-year snapshots). Build the
     agent's 8-neighbour Moore-cell language list from
     `agent_id_to_lang`. Apply the language-shift rule
     conditional on > 50 % majority and the relevant per-year
     probability:
     - If agent is Slavic and majority of neighbours are
       Christianised non-Slavic, with probability
       `reverse_assimilation_rate` the agent switches to the
       most-common Christianised neighbour language.
     - If agent is non-Slavic and majority of neighbours are Slavic,
       with probability `slavic_assimilation_rate` the agent
       switches to Slavic.
4. **Bookkeeping**. New (born + migrated) agents are appended; dead
   agents removed. Record the year's Slavic share and total
   population for the run log.

### 3.2 Run

Each scenario runs `args.num_runs` independent runs (default 10),
each seeded from `args.seed` (with internal RNG advancing
deterministically through migration → grid init → tick loop). Final
outputs are per-year means and SDs across runs, plus per-year
min/max populations.

### 3.3 Scheduling notes (cross-cutting design choice)

The start-of-year snapshots (`cell_langs`, `agent_id_to_lang`) make
within-tick processing order-independent: an agent processed late in
the agent-list pass sees the **same** language landscape as one
processed early. This was a deliberate change from the original
listing (commit `183f30f`), which had implicit order-dependence.
The snapshots also reduce the assimilation neighbour scan from
O(*n*²) to O(*n* · *k*) where *k* is the Moore-neighbourhood size
(≤ ~30 agents per neighbourhood at the canonical scale).

## 4. Design concepts

### 4.1 Basic principles

The model encodes the standard demographic-ABM frame (Kandler 2009;
Kandler and Steele 2008) — births, deaths, local copying — with
three additions:

1. **Migration as input**, not a derived dynamic. The migration rate
   is a scenario parameter; the model tests *consequences* of
   migration sizes, not how migrants got there.
2. **Reverse assimilation**. Slavic agents in majority-Christianised
   neighbourhoods can adopt the dominant language — the symmetric
   counterpart to Slavic assimilation. Absent from prestige-biased
   models that assume one-way drift toward the high-status language.
3. **Mother-tongue rule with a sociolinguistic threshold**. Younger
   mothers pass on their own language; older mothers' children draw
   from the local community. The threshold (`INHERITANCE_AGE_MAX`)
   is a free parameter swept in sensitivity.

### 4.2 Emergence

The Slavic share at scenario end is the emergent quantity of
interest. It is **not** programmed in: it falls out of the per-year
balance between migration inflow, plague-mortality differential,
fertility differential, mother-tongue draws, and the two-way
assimilation flux. No agent is rewarded or selected for being
Slavic; the share rises only if the demographic arithmetic permits.

### 4.3 Adaptation, objectives, fitness, learning

None. Agents have no objectives and do not optimise. Birth, death,
and language-switch are stochastic events governed by per-tick
probabilities.

### 4.4 Sensing

Each agent senses only its own state and the Moore-neighbourhood
language composition (via the start-of-year `agent_id_to_lang`
snapshot). No global sensing.

### 4.5 Interaction

Local. The assimilation rule is the only cross-agent interaction and
acts only within the 8 Moore-cell neighbourhood. Births deposit the
new agent in the mother's cell; migration deposits the new agent
into a random cell of the entry region. The start-of-year snapshot
is the mechanism that makes the result independent of the
within-tick agent-processing order.

### 4.6 Stochasticity

All within-tick events (mortality, birth, language switch, mother-
tongue cell-pool draw, migration entry coordinates) are stochastic.
Random seed `args.seed` (default 42) makes runs reproducible. The
reported uncertainty (mean ± SD) is across `args.num_runs` (10 for
the headline matrix).

### 4.7 Collectives

The implicit collective is **group** (the six language labels),
which determines per-group birth rate, plague mortality, region
eligibility, and Christianisation status. Groups have no positional
identity beyond their members.

### 4.8 Observation

Per-year per-run population, per-year per-run Slavic share. Outputs
are stored per scenario in `results_<scenario>.txt` with population
checkpoints (year 0/25/50/100/150/200/260) and Slavic-share
checkpoints at the same offsets, both as mean ± SD across runs.

## 5. Initialization

### 5.1 Grid and agent setup

5,000 agents are placed at scenario start. Each agent is assigned a
group by the initial-fraction allocation (see §6.1), then placed at
random `(x, y)` coordinates with rejection sampling to enforce
region eligibility: Illyrian/Thracian, Greek, Germanic, Avar groups
go in the Balkans / central regions; Slavic in eastern / central
(but **not** Balkans, in the no-substrate default); "other" in
eastern.

### 5.2 Initial ages

Ages are initialised from `min(MAX_AGE, expovariate(BASE_MORTALITY))`
— the equilibrium geometric distribution under flat 2 % / yr
mortality (commit `ad8cd05`). The earlier uniform-age init created
a ~24 % drift transient over 260 yr in the no-plague baseline; the
geometric init reduces it to +8.1 % drift (within ±10 % fence).

### 5.3 Sex

Random uniform {male, female} per agent.

### 5.4 Substrate option

If `--substrate` is set, the initial Slavic fraction is **raised to
30 %**, and Slavic agents are allowed in Balkans cells. This is the
substrate-hypothesis initialisation, used in the substrate response
curve.

## 6. Input data

### 6.1 Initial group fractions

| Scenario start | slavic | illyrian_thracian | greek | germanic | avar | other |
|---|---|---|---|---|---|---|
| 600 CE (Slavic) | 0.10 | 0.30 | 0.20 | 0.20 | 0.10 | 0.10 |
| 630 CE (Arabic) | 0.05 | 0.00 | 0.00 | 0.00 | 0.00 | 0.95 |

Substrate variant raises the 600 CE Slavic fraction to 0.30 and
re-balances by drawing from non-Slavic groups proportionally.

Sources: ethnographic-historical reconstruction (Curta 2001;
Barford 2001); population scale from demographic-history sources
(Russell 1987; see `olalde_audit.md` Finding 2 — the canonical PDF
mis-sources this to Olalde 2023 and Ralph & Coop 2013, both of
which are ancestry-composition studies, not demographic-count
sources; correction queued for the Methods rewrite).

### 6.2 Per-group demographic and assimilation parameters

See `parameter_table.md` for the full list with statuses
(structural / well-grounded / weakly grounded / free parameter) and
sensitivity ranges. The summary inputs by scenario are:

| Parameter | slavic1 | slavic2 | slavic3 | arabic |
|---|---|---|---|---|
| `migration_rate` (yr⁻¹, first 100 yr) | 10 | 30 | 50 | 10 |
| `slavic_assimilation_rate` | 0.005 | 0.01 | 0.02 | 0.02 |
| `reverse_assimilation_rate` | 0.03 | 0.02 | 0.015 | 0.0 |
| `CBR_SLAVIC` (per head·yr) | 0.021 | 0.023 | 0.025 | 0.022 |
| `non_slavic_plague_mortality` | 0.15 | 0.15 | 0.20 | 0.12 |
| Scenario length (yr) | 260 | 260 | 260 | 170 |

All groups use `CBR_NON_SLAVIC = 0.020` except slavic, which uses
`CBR_SLAVIC[scenario]`; `BASE_MORTALITY = 0.02 / yr`; Slavic plague
mortality fixed at 0.04 (or, under `--uniform_mortality`, raised to
match `non_slavic_plague_mortality` — the counterfactual).

## 7. Submodels

### 7.1 Crude-birth-rate to per-female calibration

Birth rolls are per reproductive-age female per year. Naïvely
specifying a crude birth rate (CBR ≈ 2–3 %) and applying it per
female would under-supply births by a factor of ~6.6 (the share of
the population that is female and aged 15–40 at equilibrium under
flat mortality is ~0.151). The model therefore exposes a CBR
constant per group (`CBR_NON_SLAVIC = 0.020`,
`CBR_SLAVIC[scenario]`, `CBR_SLAVIC_NEW = 0.011`) and converts via
`per_female_rate(cbr) = cbr / REPRO_SHARE` where
`REPRO_SHARE = 0.151`. The conversion is what the engine baseline
at `ad8cd05` validates: under no migration and no plague, the
population is stationary within ±10 % across 260 yr.

### 7.2 Plague mortality

In years listed in `PLAGUE_YEARS`, the per-agent mortality roll
uses the agent's group `plague_mortality` instead of
`BASE_MORTALITY`. The Slavic group has 0.04 vs. the non-Slavic
0.15 / 0.20 differential. Under `--uniform_mortality`, the Slavic
group's plague mortality is raised to the non-Slavic value: the
counterfactual that isolates how much of the Slavic share depends
on the differential vs. on migration / assimilation alone.

### 7.3 Migration

For each year in `[0, 100)`, `migration_rate` Slavic agents are
inserted. Insertion coordinates are uniform over the eastern half
of the grid (Slavic scenarios) or the full grid (Arabic). Each
inserted migrant has uniform age `[15, 40]` and random sex.

### 7.4 Mother-tongue inheritance

On a birth:

- If mother's age ≤ `INHERITANCE_AGE_MAX` (= 25): the child's
  language is the mother's. (Younger mothers in tightly-knit early-
  medieval communities pass on their own language unmodified.)
- Otherwise: the child's language is drawn from the **cell-pool** —
  the list of languages of other agents in the same cell, with the
  mother's language removed.
  - If the cell-pool has fewer than 3 other agents, the local pool
    is too small to be meaningful, and the child falls back to the
    mother's language.

The cell-pool draw uses `random.choice`, so the probability of
each language is its empirical share in the cell. This is the
community-acquisition mechanism: where no institution standardises
language transmission, children learn from the local community.

### 7.5 Two-way assimilation

For each agent each year, build the Moore-cell neighbour-language
list (from `agent_id_to_lang` start-of-year snapshot). If the
agent's language is non-Slavic and Slavic > 50 % of neighbours:
roll against `slavic_assimilation_rate` to switch to Slavic. If the
agent is Slavic and Christianised non-Slavic > 50 % of neighbours:
roll against `reverse_assimilation_rate` to switch to the
most-common Christianised neighbour language. Both directions
share the > 50 % threshold (the minimal majoritarian local rule).
The Arabic scenario sets `reverse_assimilation_rate = 0` because
the Arabic context lacked an analogue to the Byzantine
Christianising institutional channel.

### 7.6 Bookkeeping at end of tick

Surviving agents (those not in `dead`) are concatenated with
`new_agents` (births + migrations) to form the next-tick agent
list. Per-tick Slavic share and total population are recorded for
the run log.

## References (Methods section subset)

The full bibliography is in the manuscript; the references this
protocol relies on directly are:

- Curta, F. (2001). *The Making of the Slavs.* Cambridge.
- Grimm, V., et al. (2006). "A standard protocol for describing
  individual-based and agent-based models." *Ecological Modelling*
  198, 115–126.
- Grimm, V., et al. (2010). "The ODD protocol: a review and first
  update." *Ecological Modelling* 221, 2760–2768.
- Grimm, V., et al. (2020). "The ODD Protocol for Describing
  Agent-Based and Other Simulation Models: A Second Update."
  *JASSS* 23 (2), 7.
- Kandler, A. (2009). "Demography and language competition."
  *Human Biology* 81, 181–210.
- Kandler, A., & Steele, J. (2008). "Ecological models of language
  competition." *Anthropological Linguistics* 50, 1–26.
- Mordechai, L., et al. (2019). "The Justinianic Plague: An
  inconsequential pandemic?" *PNAS* 116, 25546–25554. [the
  plague-maximalist contestation — relevant to §7.2 and the
  plague-mortality sensitivity sweep]
- Russell, J. C. (1987). *Medieval Demography.* AMS Press.
