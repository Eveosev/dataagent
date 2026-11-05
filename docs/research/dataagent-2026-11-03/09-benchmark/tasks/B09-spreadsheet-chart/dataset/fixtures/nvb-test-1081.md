# nvBench2 test

## 问题

Show a chart with property_address, room_count, and buyer_offered_price, and aggregate the mean of room_count.

## 表结构

{"table_columns": ["property_id", "property_type_code", "date_on_market", "date_sold", "property_name", "property_address", "room_count", "vendor_requested_price", "buyer_offered_price", "agreed_selling_price", "apt_feature_1", "apt_feature_2"], "column_examples": {"property_id": ["9", "10", "11"], "property_type_code": ["Field", "Apartment", "House"], "date_on_market": ["1976-06-10", "1993-08-04", "2017-09-14"], "date_sold": ["1971-04-14", "1990-11-14", "2012-08-19"], "property_name": ["avalon", "ten tower", "park"], "property_address": ["084 Lakin Vista Apt. 394\nFishertown, MA 16876", "743 Ephraim Greens\nAnniemouth, HI 47084-3853", "49578 Ayden Mountains\nNew Russellhaven, UT 46626"], "room_count": [1, 6, 9], "vendor_requested_price": [13.4715, 2573, 661536468.4429], "buyer_offered_price": [0, 10.1067, 27537286], "agreed_selling_price": [0, 44132.4621, 456840888.16], "apt_feature_1": ["consequatur", "aut", "fuga"], "apt_feature_2": ["eos", "suscipit", "odio"]}, "unique_value_counts": {"property_id": 15, "property_type_code": 5, "date_on_market": 15, "date_sold": 15, "property_name": 15, "property_address": 15, "room_count": 8, "vendor_requested_price": 15, "buyer_offered_price": 13, "agreed_selling_price": 14, "apt_feature_1": 12, "apt_feature_2": 13}}
