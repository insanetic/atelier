# Expression Cookbook

Copy-pasteable JSON for the shapes that come up building metrics. Every snippet
here is an **expression** that goes in the `$project` array (aliased `value`) or a
**filter** that goes in `$where`, unless noted. Adapt the identifiers, qualifiers,
and the schema/alias in `$from` to the source you're working in.

These are **DSL** snippets. The one-line glosses above each block (e.g.
`COALESCE(SUM(res.net), 0) AS value`) are a **PostgreSQL-flavored shorthand for
understanding only** — the actual artifact is the JSON DSL beneath them. The DSL
resembles PostgreSQL, but it is a standalone representation: it is not SQL, and
nothing here produces SQL.

The authoritative grammar is `semantic-layer-schema.json` (sibling file). When in
doubt about whether something is expressible, check there.

## Contents

1. [Three kinds of literal: `$arg`, `$var`, `$scalar`](#three-kinds-of-literal)
2. [Two ways to call a function: `$variadic` vs `$agg`](#two-ways-to-call-a-function)
3. [The mandatory connection filter](#the-mandatory-connection-filter)
4. [Sum (the standard total)](#sum)
5. [Count and distinct count](#count-and-distinct-count)
6. [Ratio / rate (CTR pattern)](#ratio--rate-ctr-pattern)
7. [Rounded percentage over a flag denominator (interaction-rate pattern)](#rounded-percentage-over-a-flag-denominator)
8. [Money: convert minor units / micros to the major unit](#money-unit-conversion)
9. [Conditional sum/count (filtered aggregate)](#conditional-sumcount)
10. [CASE expression](#case-expression)
11. [Joins without changing the value (anti–fan-out)](#joins-without-changing-the-value)
12. [Single-value scalar subquery](#single-value-scalar-subquery)

---

## Three kinds of literal

Choosing the right one keeps queries safe and correct:

- **`$arg`** — a bound runtime variable (`:name`). Magic variables only:
  `:connection_id`, `:window_start`, `:window_end`, `:periodicity_unit`, or a custom
  one declared in `requirements.md`.
- **`$var`** — a bound parameter. A literal **business value** you compare against,
  e.g. a status string. Bound rather than inlined, so it's injection-safe and
  plan-cacheable.
- **`$scalar`** — an inline literal. Plain numbers, booleans, and null — e.g. the `0`
  in a `coalesce`, the `100` in a percentage, `true`/`false`.

```json
{ "$arg": ":connection_id" }
{ "$var": "Book" }
{ "$scalar": 0 }
```

Rule of thumb: numbers/booleans → `$scalar`; string values you filter on → `$var`;
anything `:`-prefixed → `$arg`.

---

## Two ways to call a function

A function call (`sum`, `count`, `coalesce`, `divide`, `round`, …) can be written two
ways. They are not interchangeable, and picking the wrong one silently drops a clause:

- **`$variadic`** — the default. Just `$fn` + `$operands`. Use it for everything that
  doesn't need an aggregate-only modifier: every `coalesce`/`divide`/`round`/`multiply`,
  and plain `sum`/`count`/`avg`.
- **`$agg`** — the aggregate node. Same `$fn` + `$operands`, **plus** three modifiers
  only an aggregate can carry: `$filter` (a `FILTER (WHERE …)` clause, see
  *Conditional sum/count*), `$orderBy` (ordered aggregates), and an aggregate-level
  `$distinct`. Reach for `$agg` **only when you need one of those three**; otherwise
  `$variadic` is the lighter, conventional form.

So the rule is mechanical: **need a per-aggregate `FILTER`, ordering, or
aggregate-level distinct → `$agg`; everything else → `$variadic`.** Most metrics never
need `$agg` at all — it shows up once below, in the conditional-aggregate pattern.

(Distinct has a second, more common form: `$distinct: true` placed on the *operand*
rather than the aggregate — see *Count and distinct count*. Prefer the operand form
for `COUNT(DISTINCT col)`; reserve aggregate-level `$distinct` for when you already
need `$agg` for another reason.)

---

## The mandatory connection filter

Goes in `$where`. **`$where` is always an `$and` array** — even when there is only the
connection filter, wrap it in `$and` so adding business filters later (and the
runtime's injected filters) compose cleanly without restructuring. Qualify
`_connection_id` with the alias of the table it lives on.

```json
{
  "$and": [
    {
      "$eq": {
        "$left":  [ { "$identifier": "_connection_id", "$qualifier": { "$table": "res" } } ],
        "$right": [ { "$arg": ":connection_id" } ]
      }
    }
  ]
}
```

---

## Sum

`COALESCE(SUM(res.net), 0) AS value`. The `coalesce` turns an empty window into `0`
rather than null.

```json
{
  "$variadic": {
    "$fn": "coalesce",
    "$operands": [
      { "$variadic": { "$fn": "sum", "$operands": [ { "$identifier": "net", "$qualifier": { "$table": "res" } } ] } },
      { "$scalar": 0 }
    ]
  },
  "$as": "value"
}
```

Average is identical with `"$fn": "avg"` instead of `sum`. Add
`"$shortCast": ["DOUBLE"]` on the outer expression when you want a floating-point
result rather than the column's native type.

---

## Count and distinct count

`COUNT(res.id) AS value` — counts need no `coalesce` (an empty set counts to `0`):

```json
{ "$variadic": { "$fn": "count", "$operands": [ { "$identifier": "id", "$qualifier": { "$table": "res" } } ] }, "$as": "value" }
```

`COUNT(DISTINCT res.foreign_id) AS value` — put `"$distinct": true` **on the
operand** (not on the aggregate). This is the convention: a plain `$variadic` count
with the distinct on the column, so you don't need `$agg` just for a distinct count.

```json
{ "$variadic": { "$fn": "count", "$operands": [ { "$distinct": true, "$identifier": "foreign_id", "$qualifier": { "$table": "res" } } ] }, "$as": "value" }
```

---

## Ratio / rate (CTR pattern)

This is the shape for any "X per Y" or percentage: CTR, conversion rate,
average-order-value, average-per-night. The two safety pieces are
**non-negotiable**:

- divide by `nullif(denominator, 0)` so a zero denominator yields null, not an error;
- cast the numerator to `NUMERIC` (or `DOUBLE`) so you get real division instead of
  integer truncation.

`COALESCE( SUM(clicks)::NUMERIC / NULLIF(SUM(impressions), 0) * 100, 0 ) AS value`:

```json
{
  "$variadic": {
    "$fn": "coalesce",
    "$operands": [
      {
        "$variadic": {
          "$fn": "multiply",
          "$operands": [
            {
              "$variadic": {
                "$fn": "divide",
                "$operands": [
                  { "$variadic": { "$fn": "sum", "$operands": [ { "$identifier": "clicks", "$qualifier": { "$table": "ins" }, "$shortCast": ["NUMERIC"] } ] } },
                  { "$variadic": { "$fn": "nullif", "$operands": [
                    { "$variadic": { "$fn": "sum", "$operands": [ { "$identifier": "impressions", "$qualifier": { "$table": "ins" } } ] } },
                    { "$scalar": 0 }
                  ] } }
                ]
              }
            },
            { "$scalar": 100 }
          ]
        }
      },
      { "$scalar": 0 }
    ]
  },
  "$as": "value"
}
```

Drop the `multiply … 100` layer if you want the raw ratio rather than a percentage.
Division uses `"$fn": "divide"` and multiplication `"$fn": "multiply"`.

---

## Rounded percentage over a flag denominator

A richer rate, worth studying because it differs from the plain CTR shape in three
ways — it counts **boolean flags** rather than a measure, its denominator is an
**eligibility flag** (not `COUNT(*)`), and it **rounds** the percentage. This is the
"interaction rate" shape: of the interactions *eligible* to count, what share were
replied to?

`ROUND( COALESCE( 100.0 * SUM(com.replied::INT)::NUMERIC / NULLIF(SUM(com.use_for_interaction_rate::INT), 0), 0 ), 2 ) AS value`

Key ideas, each reusable on its own:

- **Count a boolean by casting to `INT` inside `SUM`** — `SUM(flag::INT)` is the
  number of `true` rows. `$shortCast: ["INT"]` on the column does the cast.
- **Denominator is a different flag**, `use_for_interaction_rate` — only rows the
  business marks as eligible count toward the base. Swapping `COUNT(*)` for a flag
  sum is how you scope a rate to a qualifying population.
- **`round(expr, 2)`** trims the percentage to two decimals.
- **`coalesce(…, 0)` wraps the whole thing** — note the raw definition this is based
  on omitted that and could return `null` on an empty window. The skill's rule is to
  guarantee a non-null `value`, so the outer `coalesce` is added here.

```json
{
  "$variadic": {
    "$fn": "round",
    "$operands": [
      {
        "$variadic": {
          "$fn": "coalesce",
          "$operands": [
            {
              "$variadic": {
                "$fn": "multiply",
                "$operands": [
                  { "$scalar": 100.0 },
                  {
                    "$variadic": {
                      "$fn": "divide",
                      "$operands": [
                        {
                          "$shortCast": ["NUMERIC"],
                          "$variadic": { "$fn": "sum", "$operands": [
                            { "$identifier": "replied", "$qualifier": { "$table": "com" }, "$shortCast": ["INT"] }
                          ] }
                        },
                        {
                          "$variadic": { "$fn": "nullif", "$operands": [
                            { "$variadic": { "$fn": "sum", "$operands": [
                              { "$identifier": "use_for_interaction_rate", "$qualifier": { "$table": "com" }, "$shortCast": ["INT"] }
                            ] } },
                            { "$scalar": 0 }
                          ] }
                        }
                      ]
                    }
                  }
                ]
              }
            },
            { "$scalar": 0 }
          ]
        }
      },
      { "$scalar": 2 }
    ]
  },
  "$as": "value"
}
```

See `references/examples/hotel_data_source/interaction_rate.v1.0.json` for the full
metric file built around this.

---

## Money unit conversion

Money columns are frequently stored as **scaled integers**, not the major currency
unit. Before summing, confirm the scale with the user (or the DDL) and convert **in
the projection** so the output reads in the proper unit. Getting this wrong is an
error of 100× or 1,000,000×.

- **Minor units / cents** (`1999` = 19.99): divide the sum by `100`.
- **Micros** (ad platforms, `19990000` = 19.99): divide by `1000000`.
- **Already major units** (e.g. a `NUMERIC(12,2)` amount): no conversion — just sum.

Three things make this correct, and they're easy to get wrong:

- **Cast to `NUMERIC`, not `DOUBLE`.** Money must stay exact decimal; `DOUBLE` is
  floating point and accumulates rounding error. Put the cast on the **summed amount,
  before** the divide — that both forces real (non-truncating) division *and* makes
  the result `NUMERIC`, so no further cast after the divide is needed.
- **No `nullif` on the divisor.** The divisor is a constant (`100` / `1000000`),
  never zero — unlike the rate patterns above where the denominator is a `SUM` that
  can be zero. Only guard a divisor that could actually be zero.
- **A null or zero numerator is already handled.** An empty window makes `SUM(...)`
  null → `null / 100 = null` → the outer `coalesce(…, 0)` returns `0`. A real `0`
  divides to `0`. So the outer `coalesce` is what guarantees a non-null `value` here.

`COALESCE( SUM(res.amount_cents)::NUMERIC / 100, 0 ) AS value`:

```json
{
  "$variadic": {
    "$fn": "coalesce",
    "$operands": [
      {
        "$variadic": {
          "$fn": "divide",
          "$operands": [
            {
              "$shortCast": ["NUMERIC"],
              "$variadic": { "$fn": "sum", "$operands": [
                { "$identifier": "amount_cents", "$qualifier": { "$table": "res" } }
              ] }
            },
            { "$scalar": 100 }
          ]
        }
      },
      { "$scalar": 0 }
    ]
  },
  "$as": "value"
}
```

For micros, change the `{ "$scalar": 100 }` to `{ "$scalar": 1000000 }`. The divisor
is a plain inline number, so it's a `$scalar`, not a `$var`.

---

## Conditional sum/count

To aggregate only some rows without filtering the whole query, use the aggregate's
`$filter`. This is the one pattern that needs `$agg` instead of `$variadic` (see
*Two ways to call a function*): `$filter` is an aggregate-only modifier.
`COUNT(res.id) FILTER (WHERE res.status = 'Cancel') AS value`:

```json
{
  "$agg": {
    "$fn": "count",
    "$operands": [ { "$identifier": "id", "$qualifier": { "$table": "res" } } ],
    "$filter": {
      "$eq": {
        "$left":  [ { "$identifier": "status", "$qualifier": { "$table": "res" } } ],
        "$right": [ { "$var": "Cancel" } ]
      }
    }
  },
  "$as": "value"
}
```

This is the building block for a **rate over the same table** — e.g. cancellation
rate = filtered count `divide` total count, wrapped exactly like the ratio pattern
above. Keeping both halves in one query (rather than a join) avoids fan-out entirely.

---

## CASE expression

For bucketing or conditional values. `CASE WHEN res.nights >= 7 THEN 1 ELSE 0 END`:

```json
{
  "$case": {
    "$cases": [
      {
        "$condition": { "$gte": { "$left": [ { "$identifier": "nights", "$qualifier": { "$table": "res" } } ], "$right": [ { "$scalar": 7 } ] } },
        "$expr": { "$scalar": 1 }
      }
    ],
    "$else": { "$scalar": 0 }
  }
}
```

Wrap it in `sum` to count rows meeting the condition.

---

## Joins without changing the value

A one-to-many join **multiplies** any `SUM`/`COUNT` on the one-side. Example: one
`reservation` (`res`) has many `reservation_room_rate` rows (`rr`). If you join them
to filter on a rate attribute, `SUM(res.net)` is counted once per matching rate row
— silently wrong.

**The fix:** collapse the many-side to **one row per join key** *before* joining,
in a CTE, then inner-join once. Here, "revenue of reservations that include a
breakfast-included rate":

```json
{
  "$with": {
    "$ctes": [
      {
        "$expr": { "$identifier": "breakfast_res" },
        "$set": {
          "$select": {
            "$distinct": {},
            "$project": [
              { "$identifier": "_connection_id", "$qualifier": { "$table": "rr" } },
              { "$identifier": "foreign_reservation_id", "$qualifier": { "$table": "rr" } }
            ],
            "$from": [ { "$identifier": "reservation_room_rate", "$qualifier": { "$schema": "hotel_data_source" }, "$as": "rr" } ],
            "$where": {
              "$and": [
                { "$eq": { "$left": [ { "$identifier": "_connection_id", "$qualifier": { "$table": "rr" } } ], "$right": [ { "$arg": ":connection_id" } ] } },
                { "$eq": { "$left": [ { "$identifier": "breakfast_included", "$qualifier": { "$table": "rr" } } ], "$right": [ { "$scalar": true } ] } }
              ]
            }
          }
        }
      }
    ]
  },
  "$project": [
    {
      "$variadic": {
        "$fn": "coalesce",
        "$operands": [
          { "$variadic": { "$fn": "sum", "$operands": [ { "$identifier": "net", "$qualifier": { "$table": "res" } } ] } },
          { "$scalar": 0 }
        ]
      },
      "$as": "value"
    }
  ],
  "$from": [ { "$identifier": "reservation", "$qualifier": { "$schema": "hotel_data_source" }, "$as": "res" } ],
  "$join": [
    {
      "$inner": true,
      "$expr": { "$identifier": "breakfast_res", "$as": "b" },
      "$on": {
        "$and": [
          { "$eq": { "$left": [ { "$identifier": "_connection_id", "$qualifier": { "$table": "b" } } ], "$right": [ { "$identifier": "_connection_id", "$qualifier": { "$table": "res" } } ] } },
          { "$eq": { "$left": [ { "$identifier": "foreign_reservation_id", "$qualifier": { "$table": "b" } } ], "$right": [ { "$identifier": "foreign_id", "$qualifier": { "$table": "res" } } ] } }
        ]
      }
    }
  ],
  "$where": {
    "$and": [
      { "$eq": { "$left": [ { "$identifier": "_connection_id", "$qualifier": { "$table": "res" } } ], "$right": [ { "$arg": ":connection_id" } ] } }
    ]
  }
}
```

Because `breakfast_res` is `DISTINCT` on the join key, each `res` row matches at most
once and `SUM(res.net)` stays correct. Always join on `_connection_id` too. After
writing any join, re-derive the row multiplicity in your head: if a parent row can
match more than one child row, you have fan-out — fix it before shipping.

(`"$distinct": {}` on a select node makes it distinct over **all** projected
columns; the empty object is that "distinct over everything" form.)

---

## Single-value scalar subquery

When the number you want comes from a different grain than the rows you're filtering,
a scalar subquery in the projection keeps the outer result a single value. Use
`$selectNode` (a subquery expression). Keep the connection filter inside it too.

```json
{
  "$selectNode": {
    "$select": {
      "$project": [
        { "$variadic": { "$fn": "coalesce", "$operands": [
          { "$variadic": { "$fn": "sum", "$operands": [ { "$identifier": "net", "$qualifier": { "$table": "s" } } ] } },
          { "$scalar": 0 }
        ] } }
      ],
      "$from": [ { "$identifier": "reservation_service", "$qualifier": { "$schema": "hotel_data_source" }, "$as": "s" } ],
      "$where": {
        "$and": [
          { "$eq": { "$left": [ { "$identifier": "_connection_id", "$qualifier": { "$table": "s" } } ], "$right": [ { "$arg": ":connection_id" } ] } }
        ]
      }
    }
  },
  "$as": "value"
}
```
