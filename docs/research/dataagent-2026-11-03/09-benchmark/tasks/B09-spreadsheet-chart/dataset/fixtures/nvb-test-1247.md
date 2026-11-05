# nvBench2 test

## 问题

I want to create a heatmap that includes customer_id and code, aggregating by count.

## 表结构

{"table_columns": ["order_id", "customer_id", "order_status_code", "shipping_method_code", "order_placed_datetime", "order_delivered_datetime", "order_shipping_charges"], "column_examples": {"order_id": ["3", "14", "6"], "customer_id": ["14", "9", "2"], "order_status_code": ["Paid", "Cancelled", "Delivered"], "shipping_method_code": ["Unspecified", "FedEx", "UPS"], "order_placed_datetime": ["2008-10-23", "2013-06-16", "2017-05-28"], "order_delivered_datetime": ["2018-03-20", "2018-03-20", "2018-03-20"], "order_shipping_charges": [21.24, 46.4, 99.26]}, "unique_value_counts": {"order_id": 15, "customer_id": 9, "order_status_code": 3, "shipping_method_code": 3, "order_placed_datetime": 15, "order_delivered_datetime": 1, "order_shipping_charges": 15}}
