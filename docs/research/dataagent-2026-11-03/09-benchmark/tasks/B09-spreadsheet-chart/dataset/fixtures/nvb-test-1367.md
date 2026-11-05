# nvBench2 test

## 问题

I want to plot a bar chart with booking status code and guest ID, filtering booking status code to only confirmed or provisional.

## 表结构

{"table_columns": ["apt_booking_id", "apt_id", "guest_id", "booking_status_code", "booking_start_date", "booking_end_date"], "column_examples": {"apt_booking_id": ["497", "365", "889"], "apt_id": ["10", "7", "2"], "guest_id": ["2", "14", "15"], "booking_status_code": ["Provisional", "Confirmed"], "booking_start_date": ["2016-04-01", "2016-09-28", "2017-07-03"], "booking_end_date": ["2017-09-28", "2017-10-25", "2018-03-20"]}, "unique_value_counts": {"apt_booking_id": 15, "apt_id": 10, "guest_id": 10, "booking_status_code": 2, "booking_start_date": 15, "booking_end_date": 15}}
