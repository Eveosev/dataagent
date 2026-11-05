# 查询任务（neutron）

## 问题

Using the RBAC action-level stats from the existing query, list the top 10 actions (ranked by the shared/IPv4 subnet IP-version variance) and show: the action, the shared/IPv4 average/variance/stddev of subnet IP version, the DHCP-enabled non-shared stddev of subnet IP version, and whether any of the shared/IPv4 subnets for that action have DHCP enabled. Do not return any rounded answers.

## 库

neutron

## 涉及表

["NETWORKRBACS", "SUBNETS"]

## 连接键

[["NETWORKRBACS.OBJECT_ID", "SUBNETS.NETWORK_ID"]]

## 列映射

{"RBAC action": ["NETWORKRBACS.ACTION", "NETWORKRBACS.ACTION"], "average subnet IP version": ["SUBNETS.IP_VERSION"], "variance of subnet IP version": ["SUBNETS.IP_VERSION"], "standard deviation of subnet IP version": ["SUBNETS.IP_VERSION"], "subnets": ["SUBNETS.NETWORK_ID", "SUBNETS.NETWORK_ID"], "network referenced by an RBAC entry": ["NETWORKRBACS.OBJECT_ID"], "action name": ["NETWORKRBACS.ACTION"], "IP version numbers": ["SUBNETS.IP_VERSION"], "network (RBAC entry refers to)": ["NETWORKRBACS.OBJECT_ID", "SUBNETS.NETWORK_ID"], "DHCP enabled": ["SUBNETS.ENABLE_DHCP"], "standard deviation of IP version numbers": ["SUBNETS.IP_VERSION"], "actions with more than 5 matching subnets": ["NETWORKRBACS.ACTION", "SUBNETS.NETWORK_ID"]}

## 领域知识

["\"access_as_shared\" permission is predicated by \"networkrbacs.action = 'access_as_shared'\"", "\"exclusion of shared networks\" is predicated by \"networks.id NOT IN (SELECT networkrbacs.object_id FROM networkrbacs WHERE networkrbacs.action = 'access_as_shared' AND (networkrbacs.target_tenant = '*' OR networkrbacs.target_tenant = '9f13bf11e06e4d81b44c8c3e62d4362b'))\""]

## 子问题

["For each RBAC action, show the average, variance, and standard deviation of the subnet IP version (4 or 6) across subnets whose network is referenced by an RBAC entry, considering only RBAC entries with the \"access_as_shared\" permission.", "For each RBAC action, show the action name and the standard deviation of the IP version numbers of subnets on the network that the RBAC entry refers to, considering only subnets with DHCP enabled, excluding shared networks (i.e., networks that have an `access_as_shared` RBAC entry with target tenant `'*'` or `'9f13bf11e06e4d81b44c8c3e62d4362b'`), and only actions that have more than 5 matching subnets.", "For RBAC actions that (1) are `access_as_shared` and reference IPv4 subnets and (2) also have more than 5 DHCP-enabled subnets on non-shared networks (excluding networks shared to `'*'` or tenant `9f13bf11e06e4d81b44c8c3e62d4362b`), return the action along with the average, variance, and standard deviation of subnet IP version for the shared/IPv4 case, plus the standard deviation of subnet IP version for the DHCP-enabled non-shared case."]
