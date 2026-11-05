# 查询任务（neutron）

## 问题

For each port status, report the status and the range, variance, and standard deviation (using STDDEV only and never STDDEV_POP) of the number of port security bindings per port, considering only ports that have at least one port security binding and restricting to ports belonging to tenant ID '17ea94ad74b64b9d92f4888336a598c7'. Do not return any rounded answers.

## 库

neutron

## 涉及表

["PORTS", "PORTS"]

## 连接键

[["PORTS.ID", "PORTSECURITYBINDINGS.PORT_ID"]]

## 列映射

{"port status": ["PORTS.STATUS"], "number of port security bindings per port": ["PORTSECURITYBINDINGS.PORT_ID", "PORTS.ID"]}

## 领域知识

["Tenant ID \"17ea94ad74b64b9d92f4888336a598c7\" is predicated by \"ports.tenant_id IN ('17ea94ad74b64b9d92f4888336a598c7')\""]

## 子问题

[]
