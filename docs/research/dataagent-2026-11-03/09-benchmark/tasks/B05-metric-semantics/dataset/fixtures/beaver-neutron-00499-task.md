# 查询任务（neutron）

## 问题

For each admin-state-up port in tenant ID '98333a1a28e746fa8c629c83a818ad57' that is bound to a security group which also appears on at least one DOWN port in network ID '0a1d0a27-cffa-4de3-92c5-9d3fd3f2e74d', list the port ID, tenant ID, port name, the number of security group bindings, the total DNS record count, compute the DNS-per-security-group-binding ratio (DNS records divided by security group bindings, rounded to 2 decimals), and also show (for that shared security group) the number of DOWN-port rows and the average of the windowed minimum admin_state_up value (rounded to 2 decimals).

## 库

neutron

## 涉及表

["SECURITYGROUPPORTBINDINGS", "PORTS", "PORTDNSES"]

## 连接键

[["PORTS.ID", "SECURITYGROUPPORTBINDINGS.PORT_ID"], ["PORTDNSES.PORT_ID", "PORTS.ID"]]

## 列映射

{"port": ["PORTS.ID"], "port ID": ["PORTS.ID"], "tenant ID": ["PORTS.TENANT_ID"], "port name": ["PORTS.NAME", "PORTS.NAME"], "bound to a security group": ["SECURITYGROUPPORTBINDINGS.SECURITY_GROUP_ID", "SECURITYGROUPPORTBINDINGS.PORT_ID"], "admin_state_up = 1": ["PORTS.ADMIN_STATE_UP"], "number of security group bindings": ["SECURITYGROUPPORTBINDINGS.SECURITY_GROUP_ID"], "DNS records associated with the port": ["PORTDNSES.PORT_ID"], "ports that are DOWN": ["PORTS.STATUS"], "network ID": ["PORTS.NETWORK_ID"], "MAC address": ["PORTS.MAC_ADDRESS"], "admin state": ["PORTS.ADMIN_STATE_UP"], "status": ["PORTS.STATUS"], "device owner": ["PORTS.DEVICE_OWNER"], "bound security group ID": ["SECURITYGROUPPORTBINDINGS.SECURITY_GROUP_ID"], "port ID (ordering)": ["PORTS.ID"], "minimum admin_state_up (window)": ["PORTS.ADMIN_STATE_UP"]}

## 领域知识

["Tenant ID \"98333a1a28e746fa8c629c83a818ad57\" is predicated by \"ports.tenant_id IN ('98333a1a28e746fa8c629c83a818ad57')\"", "Network ID \"0a1d0a27-cffa-4de3-92c5-9d3fd3f2e74d\" is predicated by \"ports.network_id IN ('0a1d0a27-cffa-4de3-92c5-9d3fd3f2e74d')\""]

## 表结构

### PORTS

- 列：["TENANT_ID", "ID", "NAME", "NETWORK_ID", "MAC_ADDRESS", "ADMIN_STATE_UP", "STATUS", "DEVICE_ID", "DEVICE_OWNER", "DNS_NAME", "STANDARD_ATTR_ID"]
- 类型：["VARCHAR(255)", "VARCHAR(36)", "VARCHAR(255)", "VARCHAR(36)", "VARCHAR(32)", "TINYINT(1)", "VARCHAR(16)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "BIGINT"]
- 示例：[["e7e8e8eca25741c8abc96fc07a103b94", "000a1fab-1d06-449d-a126-fd838e023596", null, "0a1d0a27-cffa-4de3-92c5-9d3fd3f2e74d", "fa:16:3e:3c:e3:07", 1, "DOWN", "9b65e785-2a8f-4e6c-8dc7-54d94f0f1e93", "compute:nova", null, 36812], ["d09e84d9274e406a8a8f8efe08b2af93", "0012b1a9-8387-4c17-8578-755f5984aec4", null, "0a1d0a27-cffa-4de3-92c5-9d3fd3f2e74d", "fa:16:3e:7f:0f:45", 1, "DOWN", "624f304e-96c3-4251

## 子问题

["For each port that is bound to a security group, has admin_state_up = 1, and belongs to tenant ID '98333a1a28e746fa8c629c83a818ad57', list the port ID, tenant ID, port name, the number of security group bindings for that port, and the total number of DNS records associated with the port.", "For ports that are DOWN and belong to network ID `0a1d0a27-cffa-4de3-92c5-9d3fd3f2e74d`, show the port name, network ID, MAC address, admin state, status, device owner, the bound security group ID, and the minimum admin_state_up value in a window of 3 preceding and 1 following row ordered by port ID."]
