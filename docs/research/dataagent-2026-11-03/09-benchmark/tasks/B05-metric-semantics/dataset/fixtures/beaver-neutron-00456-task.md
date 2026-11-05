# 查询任务（neutron）

## 问题

For each network, show the network ID and the maximum geometric mean of the standard attribute IDs (considering only standard attribute IDs greater than 0) among all security groups that have ports in that network. Do not return any rounded answers.

## 库

neutron

## 涉及表

["PORTS", "SECURITYGROUPPORTBINDINGS"]

## 连接键

[["PORTS.ID", "SECURITYGROUPPORTBINDINGS.PORT_ID"]]

## 列映射

{"security group": ["SECURITYGROUPPORTBINDINGS.SECURITY_GROUP_ID"], "security group ID": ["SECURITYGROUPPORTBINDINGS.SECURITY_GROUP_ID"], "ports bound to that security group": ["SECURITYGROUPPORTBINDINGS.PORT_ID", "PORTS.ID"], "standard attribute IDs": ["PORTS.STANDARD_ATTR_ID"]}

## 领域知识

[]

## 子问题

["For each security group, show the security group ID and the geometric mean of the standard attribute IDs of the ports bound to that security group, considering only ports whose standard attribute ID is greater than 0."]
