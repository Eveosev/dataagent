# 查询任务（neutron）

## 问题

For DOWN ports in network ID `0a1d0a27-cffa-4de3-92c5-9d3fd3f2e74d`, return each port’s name, network ID, MAC address, admin state, status, device owner, bound security group ID, and the minimum admin_state_up over a window of 3 preceding and 1 following rows (ordered by port ID). Also include (for the same port status and device owner) the total number of non-shared ports whose standard attribute resource type is `ports` plus the earliest standard-attribute updated timestamp, but only keep rows where that port_count is greater than the average port_count across all (status, device_owner) groups. Do not return any rounded answers.

## 库

neutron

## 涉及表

["STANDARDATTRIBUTES", "PORTS", "SECURITYGROUPPORTBINDINGS"]

## 连接键

[["PORTS.STANDARD_ATTR_ID", "STANDARDATTRIBUTES.ID"], ["PORTS.ID", "SECURITYGROUPPORTBINDINGS.PORT_ID"]]

## 列映射

{"port status": ["PORTS.STATUS"], "device owner": ["PORTS.DEVICE_OWNER", "PORTS.DEVICE_OWNER"], "ports": ["PORTS.ID"], "standard attribute resource type": ["STANDARDATTRIBUTES.RESOURCE_TYPE"], "standard attribute updated timestamp": ["STANDARDATTRIBUTES.UPDATED_AT"], "standard attribute id": ["PORTS.STANDARD_ATTR_ID", "STANDARDATTRIBUTES.ID"], "ports that are DOWN": ["PORTS.STATUS"], "port name": ["PORTS.NAME"], "network ID": ["PORTS.NETWORK_ID"], "MAC address": ["PORTS.MAC_ADDRESS"], "admin state": ["PORTS.ADMIN_STATE_UP"], "status": ["PORTS.STATUS"], "bound security group ID": ["SECURITYGROUPPORTBINDINGS.SECURITY_GROUP_ID"], "port ID (ordering)": ["PORTS.ID"], "minimum admin_state_up (window)": ["PORTS.ADMIN_STATE_UP"]}

## 领域知识

["\"exclusion of shared networks\" is predicated by \"networks.id NOT IN (SELECT networkrbacs.object_id FROM networkrbacs WHERE networkrbacs.action = 'access_as_shared' AND (networkrbacs.target_tenant = '*' OR networkrbacs.target_tenant = '9f13bf11e06e4d81b44c8c3e62d4362b'))\"", "Network ID \"0a1d0a27-cffa-4de3-92c5-9d3fd3f2e74d\" is predicated by \"ports.network_id IN ('0a1d0a27-cffa-4de3-92c5-9d3fd3f2e74d')\""]

## 表结构

### PORTS

- 列：["TENANT_ID", "ID", "NAME", "NETWORK_ID", "MAC_ADDRESS", "ADMIN_STATE_UP", "STATUS", "DEVICE_ID", "DEVICE_OWNER", "DNS_NAME", "STANDARD_ATTR_ID"]
- 类型：["VARCHAR(255)", "VARCHAR(36)", "VARCHAR(255)", "VARCHAR(36)", "VARCHAR(32)", "TINYINT(1)", "VARCHAR(16)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "BIGINT"]
- 示例：[["e7e8e8eca25741c8abc96fc07a103b94", "000a1fab-1d06-449d-a126-fd838e023596", null, "0a1d0a27-cffa-4de3-92c5-9d3fd3f2e74d", "fa:16:3e:3c:e3:07", 1, "DOWN", "9b65e785-2a8f-4e6c-8dc7-54d94f0f1e93", "compute:nova", null, 36812], ["d09e84d9274e406a8a8f8efe08b2af93", "0012b1a9-8387-4c17-8578-755f5984aec4", null, "0a1d0a27-cffa-4de3-92c5-9d3fd3f2e74d", "fa:16:3e:7f:0f:45", 1, "DOWN", "624f304e-96c3-4251

## 子问题

["For each port status and device owner, considering only ports whose standard attribute resource type is 'ports' and excluding shared networks (i.e., networks whose IDs appear in networkrbacs with action = 'access_as_shared' and target_tenant = '*' or '9f13bf11e06e4d81b44c8c3e62d4362b'), return the number of ports and the earliest (minimum) standard attribute updated timestamp.", "For ports that are DOWN and belong to network ID `0a1d0a27-cffa-4de3-92c5-9d3fd3f2e74d`, show the port name, network ID, MAC address, admin state, status, device owner, the bound security group ID, and the minimum admin_state_up value in a window of 3 preceding and 1 following row ordered by port ID.", "For DOWN ports in network ID `0a1d0a27-cffa-4de3-92c5-9d3fd3f2e74d`, list each port\u2019s name, network ID, MAC address, admin state, status, device owner, bound security group ID, and the minimum admin_state_up over a window of 3 preceding and 1 following rows (ordered by port ID), and also show (for the same port status and device owner) the total number of non-shared ports whose standard attribute resource type is `ports` plus the earliest standard-attribute updated timestamp."]
