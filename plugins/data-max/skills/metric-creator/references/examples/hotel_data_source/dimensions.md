# hotel_data_source — Dimensions

Dimensions for the `hotel_data_source` source, shared across its metrics. A single
source can span **several tables** (a hotel data source might cover PMS, marketing,
and CRM data); here two tables are in play:

- `reservation`, aliased `res` — used by `total_revenue` and `avg_revenue_per_night`.
- `communication`, aliased `com` — used by `interaction_rate`.

Dimensions are tied to the table they live on, so a metric only sees the dimensions
defined on the table(s) it selects. Temporal columns are defined as a
**group/perspective pair** so a metric can be both bucketed over time (group → the
runtime buckets it with `:periodicity_unit`) and filtered to a window (perspective →
the runtime adds the `:window_start`/`:window_end` filter). Every metric therefore
has at least one `group` and one `perspective` dimension.

---

## reservation (`res`)

### Created On (group)
- **Display Name:** Created On
- **Scope:** group
- **Semantic Type:** temporal
- **Identifier:** create_date_time
- **Alias:** res_create_date_time_label
- **Qualifier:** res
- **Used by:** total_revenue, avg_revenue_per_night

### Created On (filter)
- **Display Name:** Created On
- **Scope:** perspective
- **Semantic Type:** temporal
- **Identifier:** create_date_time
- **Alias:** res_create_date_time_label
- **Qualifier:** res
- **Used by:** total_revenue, avg_revenue_per_night

### Booking Channel (group)
- **Display Name:** Booking Channel
- **Scope:** group
- **Semantic Type:** categorical
- **Identifier:** booking_channel_name
- **Alias:** res_booking_channel_name_label
- **Qualifier:** res
- **Used by:** total_revenue, avg_revenue_per_night

### Booking Channel (filter)
- **Display Name:** Booking Channel
- **Scope:** perspective
- **Semantic Type:** categorical
- **Identifier:** booking_channel_name
- **Alias:** res_booking_channel_name_label
- **Qualifier:** res
- **Used by:** total_revenue, avg_revenue_per_night

---

## communication (`com`)

### Created On (group)
- **Display Name:** Created On
- **Scope:** group
- **Semantic Type:** temporal
- **Identifier:** created_date
- **Alias:** com_created_date_label
- **Qualifier:** com
- **Used by:** interaction_rate

### Created On (filter)
- **Display Name:** Created On
- **Scope:** perspective
- **Semantic Type:** temporal
- **Identifier:** created_date
- **Alias:** com_created_date_label
- **Qualifier:** com
- **Used by:** interaction_rate

### Channel (group)
- **Display Name:** Channel
- **Scope:** group
- **Semantic Type:** categorical
- **Identifier:** channel
- **Alias:** com_channel_label
- **Qualifier:** com
- **Used by:** interaction_rate

### Channel (filter)
- **Display Name:** Channel
- **Scope:** perspective
- **Semantic Type:** categorical
- **Identifier:** channel
- **Alias:** com_channel_label
- **Qualifier:** com
- **Used by:** interaction_rate
