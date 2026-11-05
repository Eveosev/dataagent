# 查询任务（neutron）

## 问题

For each network, return the network ID and the maximum (across DOWN port status and device owner) distinct port count among ports bound to a security group for tenant ID '17ea94ad74b64b9d92f4888336a598c7', along with (for the same network) the minimum admin_state_up and average standard_attr_id for ports bound with VIF type 'ovs' whose device_id is 'da811c75-0f9b-462c-b020-8ea55f6ca7c7'. Do not return any rounded answers.

## 库

neutron

## 涉及表

["PORTS", "SECURITYGROUPPORTBINDINGS", "ML2_PORT_BINDINGS"]

## 连接键

[["PORTS.ID", "SECURITYGROUPPORTBINDINGS.PORT_ID"], ["ML2_PORT_BINDINGS.PORT_ID", "PORTS.ID"]]

## 列映射

{"port status": ["PORTS.STATUS", "PORTS.STATUS"], "device owner": ["PORTS.DEVICE_OWNER"], "ports": ["PORTS.ID"], "bound to a security group": ["SECURITYGROUPPORTBINDINGS.PORT_ID"], "standard attribute ID": ["PORTS.STANDARD_ATTR_ID"], "minimum admin_state_up value": ["PORTS.ADMIN_STATE_UP"], "average standard_attr_id": ["PORTS.STANDARD_ATTR_ID"], "ports bound with VIF type 'ovs'": ["ML2_PORT_BINDINGS.VIF_TYPE", "ML2_PORT_BINDINGS.PORT_ID", "PORTS.ID"]}

## 领域知识

["Tenant ID \"17ea94ad74b64b9d92f4888336a598c7\" is predicated by \"ports.tenant_id IN ('17ea94ad74b64b9d92f4888336a598c7')\"", "Device ID \"da811c75-0f9b-462c-b020-8ea55f6ca7c7\" is predicated by \"ports.device_id IN ('da811c75-0f9b-462c-b020-8ea55f6ca7c7')\""]

## 表结构

### SECURITYGROUPPORTBINDINGS

- 列：["PORT_ID", "SECURITY_GROUP_ID"]
- 类型：["VARCHAR(36)", "VARCHAR(36)"]
- 示例：[["3d0d3872-f929-46ba-8adc-4fb128b557c6", "0008e629-5619-41e0-b86c-4eecfeaacb6c"], ["d1c34ee8-d108-4e9e-940b-9d6530c9fec9", "0008e629-5619-41e0-b86c-4eecfeaacb6c"], ["73f69596-247f-443b-b8b7-5b44b138c112", "0028f2b0-b1a0-4932-a6c5-93ec69119656"]]

## 子问题

["For each port status and device owner, considering only ports that are bound to a security group and whose tenant ID is '17ea94ad74b64b9d92f4888336a598c7', return the number of distinct ports and the minimum standard attribute ID.", "For each port status, what are the minimum admin_state_up value and the average standard_attr_id for ports that are bound with VIF type 'ovs', considering only ports whose device_id is 'da811c75-0f9b-462c-b020-8ea55f6ca7c7'?", "For each DOWN port status and device owner among ports bound to a security group for tenant ID '17ea94ad74b64b9d92f4888336a598c7', return the distinct port count and minimum standard attribute ID, along with (for the same port status) the minimum admin_state_up and average standard_attr_id for ports bound with VIF type 'ovs' whose device_id is 'da811c75-0f9b-462c-b020-8ea55f6ca7c7'."]
