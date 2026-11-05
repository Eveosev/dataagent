# 查询任务（neutron）

## 问题

For haproxy load balancers that are in ACTIVE provisioning status, list the load balancer name, ID, VIP address, provisioning status, operating status, the running average of the load balancer ID within the haproxy provider group ordered by load balancer name, and the total incoming bytes for that operating status—keeping only operating statuses whose total incoming bytes (across ACTIVE load balancers) exceed 1,000,000. Do not return any rounded answers.

## 库

neutron

## 涉及表

["LBAAS_LOADBALANCERS", "PROVIDERRESOURCEASSOCIATIONS", "LBAAS_LOADBALANCER_STATISTICS"]

## 连接键

[["LBAAS_LOADBALANCERS.ID", "PROVIDERRESOURCEASSOCIATIONS.RESOURCE_ID"], ["LBAAS_LOADBALANCERS.ID", "LBAAS_LOADBALANCER_STATISTICS.LOADBALANCER_ID"]]

## 列映射

{"haproxy provider": ["PROVIDERRESOURCEASSOCIATIONS.PROVIDER_NAME"], "load balancer name": ["LBAAS_LOADBALANCERS.NAME"], "load balancer ID": ["LBAAS_LOADBALANCERS.ID"], "VIP address": ["LBAAS_LOADBALANCERS.VIP_ADDRESS"], "provisioning status": ["LBAAS_LOADBALANCERS.PROVISIONING_STATUS"], "operating status": ["LBAAS_LOADBALANCERS.OPERATING_STATUS", "LBAAS_LOADBALANCERS.OPERATING_STATUS"], "provider name group": ["PROVIDERRESOURCEASSOCIATIONS.PROVIDER_NAME"], "running average of load balancer ID": ["LBAAS_LOADBALANCERS.ID"], "load balancer operating status": ["LBAAS_LOADBALANCERS.OPERATING_STATUS"], "incoming bytes": ["LBAAS_LOADBALANCER_STATISTICS.BYTES_IN"], "ACTIVE provisioning status": ["LBAAS_LOADBALANCERS.PROVISIONING_STATUS"], "total number of incoming bytes": ["LBAAS_LOADBALANCER_STATISTICS.BYTES_IN"]}

## 领域知识

[]

## 表结构

### PROVIDERRESOURCEASSOCIATIONS

- 列：["PROVIDER_NAME", "RESOURCE_ID"]
- 类型：["VARCHAR(255)", "VARCHAR(36)"]
- 示例：[["haproxy", "03345c1a-c879-4747-9707-642b724a2880"], ["haproxy", "0367b35b-023b-41d5-816b-359b3bcbdd8e"], ["haproxy", "098c7421-cdfc-4fc4-add6-22eb7397991d"]]

## 子问题

["For load balancers provided by the \u201chaproxy\u201d provider, show the load balancer name, load balancer ID, VIP address, provisioning status, operating status, and the running average of the load balancer ID within each provider name group ordered by load balancer name.", "For each load balancer operating status, show the operating status and the total number of incoming bytes across load balancers that are in ACTIVE provisioning status, keeping only operating statuses where the total incoming bytes exceed 1,000,000."]
