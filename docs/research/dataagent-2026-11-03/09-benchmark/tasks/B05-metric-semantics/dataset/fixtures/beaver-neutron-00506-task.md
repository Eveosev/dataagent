# 查询任务（neutron）

## 问题

For administratively up ports belonging to tenant ID `98333a1a28e746fa8c629c83a818ad57` that have IP allocations, return each port’s ID, tenant ID, network ID, MAC address, host, VIF type, VNIC type, status, device owner, the windowed average standard attribute ID (2 preceding to 2 following within each VIF type), and the port’s IP allocation and subnet-id row counts—restricted to ports whose IP allocation count is greater than the tenant’s average IP allocation count. Do not return any rounded answers.

## 库

neutron

## 涉及表

["PORTS", "IPALLOCATIONS", "ML2_PORT_BINDINGS"]

## 连接键

[["PORTS.ID", "PORTSECURITYBINDINGS.PORT_ID"], ["IPALLOCATIONS.PORT_ID", "PORTS.ID"], ["ML2_PORT_BINDINGS.PORT_ID", "PORTS.ID"]]

## 列映射

{"port": ["PORTS.ID"], "administratively up": ["PORTS.ADMIN_STATE_UP", "PORTS.ADMIN_STATE_UP"], "IP allocation": ["IPALLOCATIONS.IP_ADDRESS"], "port ID": ["PORTS.ID", "ML2_PORT_BINDINGS.PORT_ID", "PORTS.ID"], "tenant ID": ["PORTS.TENANT_ID", "PORTS.TENANT_ID"], "MAC address": ["PORTS.MAC_ADDRESS", "PORTS.MAC_ADDRESS"], "number of IP allocations": ["IPALLOCATIONS.IP_ADDRESS"], "distinct subnets": ["IPALLOCATIONS.SUBNET_ID"], "host": ["ML2_PORT_BINDINGS.HOST"], "VIF type": ["ML2_PORT_BINDINGS.VIF_TYPE"], "VNIC type": ["ML2_PORT_BINDINGS.VNIC_TYPE"], "network ID": ["PORTS.NETWORK_ID"], "status": ["PORTS.STATUS"], "device owner": ["PORTS.DEVICE_OWNER"], "standard attribute ID": ["PORTS.STANDARD_ATTR_ID"]}

## 领域知识

["Tenant ID \"98333a1a28e746fa8c629c83a818ad57\" is predicated by \"ports.tenant_id IN ('98333a1a28e746fa8c629c83a818ad57')\""]

## 表结构

### IPALLOCATIONS

- 列：["PORT_ID", "IP_ADDRESS", "SUBNET_ID", "NETWORK_ID"]
- 类型：["VARCHAR(36)", "VARCHAR(64)", "VARCHAR(36)", "VARCHAR(36)"]
- 示例：[[null, "10.214.241.199/8", "76123b94-2ae9-40c4-a4c6-03ee98d081d9", "0a1d0a27-cffa-4de3-92c5-9d3fd3f2e74d"], ["000a1fab-1d06-449d-a126-fd838e023596", "10.122.48.57/8", "76123b94-2ae9-40c4-a4c6-03ee98d081d9", "0a1d0a27-cffa-4de3-92c5-9d3fd3f2e74d"], ["0012b1a9-8387-4c17-8578-755f5984aec4", "10.46.5.190/8", "76123b94-2ae9-40c4-a4c6-03ee98d081d9", "0a1d0a27-cffa-4de3-92c5-9d3fd3f2e74d"]]

## 子问题

["For each port that is administratively up, belongs to tenant ID `98333a1a28e746fa8c629c83a818ad57`, and has at least one IP allocation, list the port ID, tenant ID, MAC address, the number of IP allocations on that port, and the total number of distinct subnets those IP allocations belong to.", "For ports that are administratively up and belong to tenant ID `98333a1a28e746fa8c629c83a818ad57`, show the port ID, host, VIF type, VNIC type, tenant ID, network ID, MAC address, status, device owner, and the average standard attribute ID in a window of 2 preceding and 2 following rows partitioned by VIF type and ordered by standard attribute ID."]
