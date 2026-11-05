# 查询任务（neutron）

## 问题

For each network whose number of ports that are both in status 'DOWN' and have port security enabled is greater than the average such count across all networks, list the network ID, that down-and-secure port count (and the overall total of down-and-secure ports), and also the maximum (within that network) of the range, variance, and standard deviation (using STDDEV only and never STDDEV_POP) of allowed address-pair counts per port (considering only ports that have at least one allowed address pair). Do not return any rounded answers.

## 库

neutron

## 涉及表

["PORTS", "SECURITYGROUPPORTBINDINGS", "ALLOWEDADDRESSPAIRS"]

## 连接键

[["PORTS.ID", "PORTSECURITYBINDINGS.PORT_ID"], ["PORTS.ID", "SECURITYGROUPPORTBINDINGS.PORT_ID"], ["ALLOWEDADDRESSPAIRS.PORT_ID", "PORTS.ID"]]

## 列映射

{"ports": ["PORTS.ID"], "status 'DOWN'": ["PORTS.STATUS"], "port security enabled": ["PORTSECURITYBINDINGS.PORT_SECURITY_ENABLED"], "port security binding": ["PORTSECURITYBINDINGS.PORT_ID"], "security group": ["SECURITYGROUPPORTBINDINGS.SECURITY_GROUP_ID"], "security group ID": ["SECURITYGROUPPORTBINDINGS.SECURITY_GROUP_ID"], "allowed address pairs per port": ["ALLOWEDADDRESSPAIRS.PORT_ID", "PORTS.ID"], "ports (with at least one allowed address pair)": ["ALLOWEDADDRESSPAIRS.PORT_ID", "PORTS.ID"], "range of number of allowed address pairs per port": ["ALLOWEDADDRESSPAIRS.PORT_ID", "PORTS.ID"], "variance of number of allowed address pairs per port": ["ALLOWEDADDRESSPAIRS.PORT_ID", "PORTS.ID"], "standard deviation of number of allowed address pairs per port": ["ALLOWEDADDRESSPAIRS.PORT_ID", "PORTS.ID"], "port": ["PORTS.ID"], "security group per port binding": ["SECURITYGROUPPORTBINDINGS.PORT_ID"]}

## 领域知识

[]

## 表结构

### SECURITYGROUPPORTBINDINGS

- 列：["PORT_ID", "SECURITY_GROUP_ID"]
- 类型：["VARCHAR(36)", "VARCHAR(36)"]
- 示例：[["3d0d3872-f929-46ba-8adc-4fb128b557c6", "0008e629-5619-41e0-b86c-4eecfeaacb6c"], ["d1c34ee8-d108-4e9e-940b-9d6530c9fec9", "0008e629-5619-41e0-b86c-4eecfeaacb6c"], ["73f69596-247f-443b-b8b7-5b44b138c112", "0028f2b0-b1a0-4932-a6c5-93ec69119656"]]

## 子问题

["How many ports are in status 'DOWN' and have port security enabled (as indicated by the port security binding)?", "For each security group, show the security group ID and the range, variance, and standard deviation of the number of allowed address pairs per port, considering only ports that have at least one allowed address pair.", "For each network, how many ports are in status 'DOWN' and have port security enabled, and only include networks whose count is greater than the average such count across all networks?", "For each network, show the network ID and the maximum (across security groups in that network) of the range, variance, and standard deviation of the number of allowed address pairs per port, considering only ports that have at least one allowed address pair."]
