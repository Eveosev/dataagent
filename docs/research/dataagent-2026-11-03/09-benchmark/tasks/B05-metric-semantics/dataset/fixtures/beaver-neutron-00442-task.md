# 查询任务（neutron）

## 问题

For the top 3 networks with the most subnets among RBAC entries where the action is 'access_as_shared', show each network (with its subnet count) and each subnet’s tenant ID, along with (on those same networks) the number of DOWN ports whose standard attribute ID is greater than the average standard attribute ID for DOWN ports in the same resource type, and the average of their running-sum standard attribute ID window values. Do not return any rounded answers.

## 库

neutron

## 涉及表

["STANDARDATTRIBUTES", "PORTS", "NETWORKRBACS", "SUBNETS"]

## 连接键

[["PORTS.STANDARD_ATTR_ID", "STANDARDATTRIBUTES.ID"], ["NETWORKRBACS.OBJECT_ID", "SUBNETS.NETWORK_ID"]]

## 列映射

{"ports whose status is DOWN": ["PORTS.STATUS"], "port ID": ["PORTS.ID"], "tenant ID": ["PORTS.TENANT_ID"], "MAC address": ["PORTS.MAC_ADDRESS"], "standard attribute IDs": ["STANDARDATTRIBUTES.ID"], "resource type group": ["STANDARDATTRIBUTES.RESOURCE_TYPE"], "top 3 networks": ["NETWORKRBACS.OBJECT_ID"], "most subnets": ["SUBNETS.NETWORK_ID"], "RBAC entries": ["NETWORKRBACS.OBJECT_ID"], "action is 'access_as_shared'": ["NETWORKRBACS.ACTION"], "network object ID": ["NETWORKRBACS.OBJECT_ID"], "number of subnets": ["SUBNETS.NETWORK_ID"]}

## 领域知识

[]

## 表结构

### PORTS

- 列：["TENANT_ID", "ID", "NAME", "NETWORK_ID", "MAC_ADDRESS", "ADMIN_STATE_UP", "STATUS", "DEVICE_ID", "DEVICE_OWNER", "DNS_NAME", "STANDARD_ATTR_ID"]
- 类型：["VARCHAR(255)", "VARCHAR(36)", "VARCHAR(255)", "VARCHAR(36)", "VARCHAR(32)", "TINYINT(1)", "VARCHAR(16)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "BIGINT"]
- 示例：[["e7e8e8eca25741c8abc96fc07a103b94", "000a1fab-1d06-449d-a126-fd838e023596", null, "0a1d0a27-cffa-4de3-92c5-9d3fd3f2e74d", "fa:16:3e:3c:e3:07", 1, "DOWN", "9b65e785-2a8f-4e6c-8dc7-54d94f0f1e93", "compute:nova", null, 36812], ["d09e84d9274e406a8a8f8efe08b2af93", "0012b1a9-8387-4c17-8578-755f5984aec4", null, "0a1d0a27-cffa-4de3-92c5-9d3fd3f2e74d", "fa:16:3e:7f:0f:45", 1, "DOWN", "624f304e-96c3-4251

### NETWORKRBACS

- 列：["ID", "OBJECT_ID", "TENANT_ID", "TARGET_TENANT", "ACTION"]
- 类型：["VARCHAR(36)", "VARCHAR(36)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)"]
- 示例：[["0cd46c97-b166-4f00-a793-534af0e7fe76", "4207d69c-903d-48d3-be48-debcb46b3241", "6f9adccbd03e4d2186756896957a14bf", "2160dff3f28c4a368d52fd373abdba78", "access_as_shared"], ["263594e2-ff49-4f74-93bc-c71f73b48152", "4207d69c-903d-48d3-be48-debcb46b3241", "6f9adccbd03e4d2186756896957a14bf", "df4ca50218b54171a83464a67dd8ec78", "access_as_shared"], ["50f95f5c-367f-42d3-875e-5df2162b9de0", "8ad137b5-

## 子问题

["For ports whose status is DOWN, show the port ID, tenant ID, and MAC address, along with the running sum of the standard attribute IDs within each resource type group ordered by standard attribute ID.", "List the top 3 networks that have the most subnets, considering only RBAC entries where the action is 'access_as_shared'. For each of these networks, return the network object ID and the number of subnets on that network.", "For ports whose status is DOWN, list the port ID, tenant ID, and MAC address, along with the running sum of standard attribute IDs within each resource type group ordered by standard attribute ID; only include ports whose standard attribute ID is greater than the average standard attribute ID among DOWN ports for the same resource type.", "Among the top 3 networks that have the most subnets (considering only RBAC entries where the action is 'access_as_shared'), list each network object ID and its subnet count, and also show the tenant ID of each subnet on those networks. Do not repeat the network ID if it is the same as the previous row."]
