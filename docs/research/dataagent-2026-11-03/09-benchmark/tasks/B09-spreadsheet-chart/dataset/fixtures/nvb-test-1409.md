# nvBench2 test

## 问题

I want to mark a bar chart using the complaint outcome code and complaint ID, with aggregation by count.

## 表结构

{"table_columns": ["complaint_id", "product_id", "customer_id", "complaint_outcome_code", "complaint_status_code", "complaint_type_code", "date_complaint_raised", "date_complaint_closed", "staff_id"], "column_examples": {"complaint_id": ["12", "10", "1"], "product_id": ["120", "117", "119"], "customer_id": ["118", "117", "120"], "complaint_outcome_code": ["OK"], "complaint_status_code": ["Closed", "Open", "New"], "complaint_type_code": ["Product Unusable", "Product Failure"], "date_complaint_raised": ["1973-02-10", "1995-01-13", "2007-10-14"], "date_complaint_closed": ["1970-10-14", "1985-12-30", "2013-09-14"], "staff_id": ["120", "115", "117"]}, "unique_value_counts": {"complaint_id": 12, "product_id": 4, "customer_id": 7, "complaint_outcome_code": 1, "complaint_status_code": 3, "complaint_type_code": 2, "date_complaint_raised": 6, "date_complaint_closed": 6, "staff_id": 6}}
