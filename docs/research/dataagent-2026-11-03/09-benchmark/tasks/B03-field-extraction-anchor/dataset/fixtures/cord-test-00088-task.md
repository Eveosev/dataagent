# 任务

从这张收据图片中抽取全部字段，按 JSON 输出。

## 字段结构

- menu：菜品列表（nm 名称、cnt 数量、price 单价、itemsubtotal 小计）
- sub_total：subtotal_price / discount_price / tax_price
- total：total_price 等
- 其余键按图片内容抽取

## 要求

- 金额保留原样（含千分位与小数点写法）
- 缺失字段省略，不要编造
