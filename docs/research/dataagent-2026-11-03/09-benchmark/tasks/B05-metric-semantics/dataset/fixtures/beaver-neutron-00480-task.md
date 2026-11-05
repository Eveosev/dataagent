# 查询任务（neutron）

## 问题

For ports with status DOWN, use the existing combined result (device-owner aggregates cross-joined to DOWN port details) as an inner result, then summarize it by port status and device owner to show the total number of rows produced and the minimum standard attribute ID. Include subtotals per port status and a grand total. Do not return any rounded answers.

## 库

neutron

## 涉及表

["PORTS", "SECURITYGROUPPORTBINDINGS", "ML2_PORT_BINDINGS"]

## 连接键

[["PORTS.ID", "SECURITYGROUPPORTBINDINGS.PORT_ID"], ["ML2_PORT_BINDINGS.PORT_ID", "PORTS.ID"]]

## 列映射

{"port status": ["PORTS.STATUS"], "device owner": ["PORTS.DEVICE_OWNER"], "ports": ["PORTS.ID"], "bound to a security group": ["SECURITYGROUPPORTBINDINGS.PORT_ID"], "standard attribute ID": ["PORTS.STANDARD_ATTR_ID"], "status DOWN": ["PORTS.STATUS"], "port ID": ["PORTS.ID"], "port name": ["PORTS.NAME"], "MAC address": ["PORTS.MAC_ADDRESS"], "binding host": ["ML2_PORT_BINDINGS.HOST"], "VIF type": ["ML2_PORT_BINDINGS.VIF_TYPE"], "rank within status group ordered by port ID": ["PORTS.STATUS", "PORTS.ID"]}

## 领域知识

[]

## 表结构

### SECURITYGROUPPORTBINDINGS

- 列：["PORT_ID", "SECURITY_GROUP_ID"]
- 类型：["VARCHAR(36)", "VARCHAR(36)"]
- 示例：[["3d0d3872-f929-46ba-8adc-4fb128b557c6", "0008e629-5619-41e0-b86c-4eecfeaacb6c"], ["d1c34ee8-d108-4e9e-940b-9d6530c9fec9", "0008e629-5619-41e0-b86c-4eecfeaacb6c"], ["73f69596-247f-443b-b8b7-5b44b138c112", "0028f2b0-b1a0-4932-a6c5-93ec69119656"]]

## 子问题

["For each port status and device owner, considering only ports that are bound to a security group, return the number of distinct ports and the minimum standard attribute ID.", "For ports whose status is DOWN, show the port ID, port name, MAC address, the binding host, VIF type, and the rank of each port within its status group ordered by port ID.", "For ports with status DOWN, return (1) the number of distinct DOWN ports that are bound to a security group and the minimum standard attribute ID for each device owner, and (2) the DOWN port details (port ID, port name, MAC address, binding host, VIF type, and the rank within the DOWN status group ordered by port ID), output together in one result set."]
