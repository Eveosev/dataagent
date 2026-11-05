# nvBench2 test

## 问题

Please mark a bar chart with driver_employee_id and location_code, and aggregate by count.

## 表结构

{"table_columns": ["location_code", "actual_order_id", "delivery_status_code", "driver_employee_id", "truck_id", "delivery_date"], "column_examples": {"location_code": ["34 Benz St", "73 Nancy Av", "58 Roof Av"], "actual_order_id": ["1", "6", "8"], "delivery_status_code": ["Delivered", "On Road", "Ready"], "driver_employee_id": ["2", "12", "6"], "truck_id": ["6", "5", "4"], "delivery_date": ["2018-02-26", "2018-03-12", "2018-03-22"]}, "unique_value_counts": {"location_code": 4, "actual_order_id": 11, "delivery_status_code": 3, "driver_employee_id": 10, "truck_id": 8, "delivery_date": 15}}
