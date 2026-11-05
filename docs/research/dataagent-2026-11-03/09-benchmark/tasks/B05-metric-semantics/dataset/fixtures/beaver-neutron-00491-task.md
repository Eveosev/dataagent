# 查询任务（neutron）

## 问题

For ports whose status is DOWN, list each port’s ID, name, MAC address, binding host, and VIF type, along with (1) the port’s rank within the DOWN status group ordered by port ID and (2) the dense rank of the port when ordering by its port-security setting (PORT_SECURITY_ENABLED) using a window frame of the current row and the 2 preceding rows. Do not return any rounded answers.

## 库

neutron

## 涉及表

["PORTS", "ML2_PORT_BINDINGS"]

## 连接键

[["PORTS.ID", "PORTSECURITYBINDINGS.PORT_ID"], ["ML2_PORT_BINDINGS.PORT_ID", "PORTS.ID"]]

## 列映射

{"ports whose status is DOWN": ["PORTS.STATUS"], "port ID": ["PORTS.ID", "PORTS.ID"], "dense rank": ["PORTSECURITYBINDINGS.PORT_SECURITY_ENABLED"], "port-security setting (PORT_SECURITY_ENABLED)": ["PORTSECURITYBINDINGS.PORT_SECURITY_ENABLED"], "status DOWN": ["PORTS.STATUS"], "port name": ["PORTS.NAME"], "MAC address": ["PORTS.MAC_ADDRESS"], "binding host": ["ML2_PORT_BINDINGS.HOST"], "VIF type": ["ML2_PORT_BINDINGS.VIF_TYPE"], "rank within status group ordered by port ID": ["PORTS.STATUS", "PORTS.ID"]}

## 领域知识

[]

## 子问题

["For ports whose status is DOWN, list each port ID and the dense rank of that port when ordering by its port-security setting (PORT_SECURITY_ENABLED), using a window frame that includes the current row and the 2 preceding rows.", "For ports whose status is DOWN, show the port ID, port name, MAC address, the binding host, VIF type, and the rank of each port within its status group ordered by port ID."]
