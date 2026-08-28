# Grubel–Lloyd on the universe-tier HS6 panel

Computes GL on the US-vs-world commodity panel, 2022-01 .. 2026-06, and puts
gold in the context of all 5,628 HS6 lines.

| File | What it does |
|---|---|
| `code/00_parquet_to_dta.py` | Mechanical conversion only — Stata cannot read parquet |
| `code/01_grubel_lloyd.do` | The whole method. Eight sections, A–H |
| `output/gl_results.log` | Full results |
| `output/gl_gold_monthly.csv` | HS 7108, monthly, both GL variants |
| `output/gl_by_commodity_year.csv` | Every HS6 × year |

```bash
.venv/Scripts/python.exe claude/gl-universe/code/00_parquet_to_dta.py
.venv/Scripts/python.exe claude/stata-console/code/run_do.py claude/gl-universe/code/01_grubel_lloyd.do
```

## What is computed

`GL = 1 − |X − M| / (X + M)`, at HS6, monthly. 0 is pure one-way trade, 1 is
exports exactly balancing imports in the same line.

The Census `DF` field lets GL be built **twice**, which is not normally possible:

| | X = |
|---|---|
| `gl_total` | domestic exports + re-exports — the number any other dataset gives you |
| `gl_dom` | domestic exports only |
| `wedge` | `gl_total − gl_dom` |

## Scope limit, stated up front

The universe tier is `CTY_CODE="-"`, **US against the world**. Gold arriving from
Switzerland and leaving for the UK nets out inside that aggregate, so this
understates two-way trade by construction. The bilateral version needs the
by-country pull and is the next step, not this one.

## Correction to an earlier claim in this file

The first draft described the wedge as one-directional contamination that always
inflates GL. **That is wrong.** The wedge is signed:

```
X < M  ->  re-exports push X toward M  ->  wedge > 0, GL inflated
X > M  ->  re-exports push X past M    ->  wedge < 0, GL depressed
```

Gold is the case that shows it. The US is a large net *exporter* of HS 7108 by
value in all five years, so its wedge is negative throughout — stripping
re-exports **raises** gold's GL. Both signs mean the same thing about the data;
the direction has to be read off the balance, not assumed.

## Results

### The headline is deflating, and should be reported that way

On `gl_total`, gold is **unexceptional**: it sits at the 35th–57th percentile of
the cross-section in every year. Anyone claiming gold has an anomalous GL against
the world aggregate is not looking at this number.

```
  year   gold GL_total   pct of commodities below   n compared
  2022          0.4422           49.1                 52,250
  2023          0.4687           50.2                 51,733
  2024          0.5464           57.3                 51,693
  2025          0.4010           45.4                 51,116
  2026          0.2719           34.6                 25,447
```

### On domestic exports only it looks different

HS 7108 aggregated, annual:

```
  year    X_bn    M_bn   gl_total   gl_dom    wedge
  2022   37.17    9.60      0.411    0.553   -0.142
  2023   25.79   15.10      0.738    0.958   -0.220
  2024   29.64   15.94      0.699    0.822   -0.122
  2025   83.48   30.18      0.531    0.766   -0.235
  2026   70.47    8.76      0.221    0.392   -0.171
```

`gl_dom` of **0.958 in 2023** and 0.822 in 2024 is near-perfect two-way trade in
a commodity where one kilo of 995 fine is identical to any other. There is no
product differentiation available to explain it.

Caveat that has to travel with this: US-origin is a customs classification, not a
geological one. Metal imported, refined or recast in the US and shipped out may
qualify as domestic export, so `gl_dom` is not a clean US-mined series.

### Gold is not at the top of the wedge ranking — precious stones and rhodium are

Of 3,479 commodity-years above $1bn trade, ranked on |wedge|:

```
  hs6      year   gl_total   gl_dom   wedge   trade_bn
  710239   2022      0.864    0.094   0.770       40.1   diamonds, worked
  180100   2024      0.752    0.009   0.743        1.8   cocoa beans
  710239   2024      0.903    0.168   0.735       27.0
  711031   2023      0.782    0.061   0.720        5.0   rhodium, unwrought
  711031   2025      0.747    0.034   0.713        4.0
```

Gold's best rank is **223rd** (710812, 2023, wedge −0.220). Four of the top five
are chapter 71 or chapter 97 — high-value, low-bulk, storable. That the
concentration is in this class of goods and not spread across trade is the
finding; that gold is *not* the extreme case within it is worth knowing before
the paper claims otherwise.

### The form shift in 710813 is the most striking single number

```
  hs6      year    X_bn    M_bn   re-export share
  710813   2024    0.60    1.06        0.036
  710813   2025    8.55    4.28        0.648
  710813   2026   47.26    1.78        0.648
```

Semi-manufactured gold exports go from $0.6bn to $47bn in two years, and the
re-export share goes from 4% to 65%. Meanwhile unwrought 710812 exports fall from
$74.6bn (2025) to $22.4bn (2026 part-year). A shift between 710812 and 710813 is
a **form** change, which is the transformation category in `CLAUDE.md` — and
transformation doubles the recorded trade footprint of one relocation. This is
the single line most worth chasing next.

### Two negative results

**1. GEN and CON imports are identical for gold, to the cent, every year.**
`CLAUDE.md` records an expectation that the general-vs-consumption gap is
"potentially load-bearing" for gold, because general imports include bonded
warehouses and FTZs. It is not: the gap is zero. That channel cannot be used to
separate metal in bond from metal entering the economy. The do-file prints this
as a labelled negative result rather than leaving it to be rediscovered.

**2. HS 710820, monetary gold, does not appear in the pull at all.** Consistent
with the BPM6 exclusion noted in `CLAUDE.md`, and confirmed against the raw
parquet rather than inferred. Central bank flows must come from IMF IFS.

### Frequency matters, but not in one direction

```
  year   mean of monthly GL   GL of annual totals   difference
  2022            0.4692              0.4106          -0.0586
  2023            0.7130              0.7385          +0.0255
  2024            0.6377              0.6995          +0.0618
  2025            0.4217              0.5311          +0.1094
  2026            0.2435              0.2212          -0.0223
```

Annual aggregation moves gold's GL by up to 0.11 and the sign is not stable, so
"annual aggregation erases the phenomenon" is too strong as stated. It distorts
it unpredictably, which is a sufficient reason to stay monthly.

### Economy-wide, for calibration

```
  year   GL_total   GL_dom   wedge   trade_bnUSD
  2022     0.4914   0.4249  0.0665       5,312.4
  2023     0.5114   0.4434  0.0681       5,098.5
  2024     0.5011   0.4293  0.0718       5,326.9
  2025     0.4723   0.3969  0.0755       5,594.4
  2026     0.4736   0.3956  0.0780       2,983.4
```

Trade-weighted, all commodities. The aggregate wedge is positive and rising —
re-exports are a growing share of US exports — while gold's is negative, because
gold sits on the other side of balance.

## Validation

The universe totals were checked against the independent by-country gold-tier
pull: HS 7108 imports and exports agree **to the cent** in all five years
(2022: 9.60 / 37.17; 2023: 15.10 / 25.79; 2024: 15.94 / 29.64; 2025: 30.18 /
83.48; 2026: 8.76 / 70.47, in $bn). Two different API request shapes, same
numbers.

## One thing outside the GL results, found while checking them

The monthly series has a $10.45bn HS 7108 import month in **2025-07** against a
~$1bn baseline, of which **$5.80bn is a single month from Switzerland** — more
than Switzerland sent in the entire rest of 2025 ($2.44bn). Exports then run
$12–18bn/month through 2025-10 and 2026-02. Not part of the GL computation, but
it is the arbitrage triangle firing and it belongs in the event chronology.
