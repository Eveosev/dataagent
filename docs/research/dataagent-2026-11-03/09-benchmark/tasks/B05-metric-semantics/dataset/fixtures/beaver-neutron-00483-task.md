# 查询任务（neutron）

## 问题

For each binding host, find the host name and the maximum DOWN-status rank (ordered by port ID within the DOWN group) among ports that are DOWN and have port security enabled, where the ports are matched to admin-up ports by MAC address. Do not return any rounded answers.

## 库

neutron

## 涉及表

["PORTS", "ML2_PORT_BINDINGS"]

## 连接键

[["ML2_PORT_BINDINGS.PORT_ID", "PORTS.ID"], ["PORTS.ID", "PORTSECURITYBINDINGS.PORT_ID"]]

## 列映射

{"status DOWN": ["PORTS.STATUS"], "port ID": ["PORTS.ID"], "port name": ["PORTS.NAME", "PORTS.NAME"], "MAC address": ["PORTS.MAC_ADDRESS", "PORTS.MAC_ADDRESS"], "binding host": ["ML2_PORT_BINDINGS.HOST"], "VIF type": ["ML2_PORT_BINDINGS.VIF_TYPE"], "rank within status group ordered by port ID": ["PORTS.STATUS", "PORTS.ID"], "administratively up ports": ["PORTS.ADMIN_STATE_UP"], "port security status": ["PORTSECURITYBINDINGS.PORT_SECURITY_ENABLED"], "row numbers ordered by MAC address": ["PORTS.MAC_ADDRESS"]}

## 领域知识

[]

## 子问题

["For ports whose status is DOWN, show the port ID, port name, MAC address, the binding host, VIF type, and the rank of each port within its status group ordered by port ID.", "For ports that are administratively up, list the port name, MAC address, and port security status, and assign row numbers ordered by MAC address using a window frame of 2 preceding rows and 1 following row.", "For ports that are DOWN, show the port ID, port name, MAC address, binding host, VIF type, the port\u2019s rank within the DOWN status group (ordered by port ID), and also the port security status and the admin-up row number (ordered by MAC address with a frame of 2 preceding rows and 1 following row), but only for those ports whose port security is enabled."]
