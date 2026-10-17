select order_id, customer_id, created_at, status, currency, order_discount, shipping
from {{ source('shop', 'orders') }}
