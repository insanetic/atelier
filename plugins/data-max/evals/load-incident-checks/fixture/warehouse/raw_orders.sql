-- Snowflake. Loaded nightly at 02:00 UTC by our ingestion job (append of the last 3 days of the source API).
create table raw.orders (
  order_id      number not null,
  customer_id   varchar,
  created_at    timestamp_ntz,   -- UTC
  status        varchar,         -- paid | refunded | pending
  currency      varchar(3),
  amount        number(18,2),
  _loaded_at    timestamp_ntz    -- set by the ingestion job
);
-- the dashboard reads analytics.daily_revenue = select created_at::date, currency, sum(amount) from raw.orders where status='paid' group by 1,2
