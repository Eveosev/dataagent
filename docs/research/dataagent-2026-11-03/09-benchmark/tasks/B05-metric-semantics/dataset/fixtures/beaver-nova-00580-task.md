# 查询任务（nova）

## 问题

For instances whose display name is 'forge' and that have at least 1 completed migration, show the instance UUID, hostname, VM state, memory in MB, the instance extra record ID, the minimum memory (in MB) over a window of 3 preceding and 1 following rows ordered by the instance extra ID, along with the completed migration status, the instance flavor JSON from instance extra, the row number over instance display name (with a window frame of 2 preceding and 1 following row), and the total count of completed migrations for that instance. Do not return any rounded answers.

## 库

nova

## 涉及表

["INSTANCE_EXTRA", "INSTANCES", "INSTANCE_SYSTEM_METADATA", "MIGRATIONS"]

## 连接键

[["INSTANCES.UUID", "INSTANCE_EXTRA.INSTANCE_UUID"], ["INSTANCES.UUID", "INSTANCE_SYSTEM_METADATA.INSTANCE_UUID"], ["INSTANCES.UUID", "MIGRATIONS.INSTANCE_UUID"]]

## 列映射

{"display name": ["INSTANCES.DISPLAY_NAME"], "instance UUID": ["INSTANCES.UUID"], "hostname": ["INSTANCES.HOSTNAME"], "VM state": ["INSTANCES.VM_STATE"], "memory in MB": ["INSTANCES.MEMORY_MB"], "instance extra record ID": ["INSTANCE_EXTRA.ID"], "minimum memory (window over 3 preceding and 1 following rows ordered by instance extra ID)": ["INSTANCES.MEMORY_MB", "INSTANCE_EXTRA.ID"], "migrations marked as completed": ["MIGRATIONS.STATUS"], "migration status": ["MIGRATIONS.STATUS"], "instance display name": ["INSTANCES.DISPLAY_NAME"], "instance flavor JSON from instance extra": ["INSTANCE_EXTRA.FLAVOR"], "row numbers": ["INSTANCES.DISPLAY_NAME"]}

## 领域知识

[]

## 表结构

### INSTANCES

- 列：["CREATED_AT", "UPDATED_AT", "DELETED_AT", "ID", "INTERNAL_ID", "USER_ID", "PROJECT_ID", "IMAGE_REF", "KERNEL_ID", "RAMDISK_ID", "LAUNCH_INDEX", "KEY_NAME", "KEY_DATA", "POWER_STATE", "VM_STATE", "MEMORY_MB", "VCPUS", "HOSTNAME", "HOST", "USER_DATA", "RESERVATION_ID", "SCHEDULED_AT", "LAUNCHED_AT", "TERMINATED_AT", "DISPLAY_NAME", "DISPLAY_DESCRIPTION", "AVAILABILITY_ZONE", "LOCKED", "OS_TYPE", "LAUNCHED_ON", "INSTANCE_TYPE_ID", "VM_MODE", "UUID", "ARCHITECTURE", "ROOT_DEVICE_NAME", "ACCESS_IP_V4", "ACCESS_IP_V6", "CONFIG_DRIVE", "TASK_STATE", "DEFAULT_EPHEMERAL_DEVICE", "DEFAULT_SWAP_DEVICE", "PROGRESS", "AUTO_DISK_CONFIG", "SHUTDOWN_TERMINATE", "DISABLE_TERMINATE", "ROOT_GB", "EPHEMERAL_GB", "CELL_NAME", "NODE", "DELETED", "LOCKED_BY", "CLEANED", "EPHEMERAL_KEY_UUID"]
- 类型：["DATETIME", "DATETIME", "DATETIME", "INT", "INT", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "INT", "VARCHAR(255)", "TEXT", "INT", "VARCHAR(255)", "INT", "INT", "VARCHAR(255)", "VARCHAR(255)", "TEXT", "VARCHAR(255)", "DATETIME", "DATETIME", "DATETIME", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "TINYINT(1)", "VARCHAR(255)", "TEXT", "INT", "VARCHAR(255)", "VARCHAR(36)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(39)", "VARCHAR(39)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "INT", "TINYINT(1)", "TINYINT(1)", "TINYINT(1)", "INT", "INT", "VARCHAR(255)", "VARCHAR(255)", "INT", "ENUM('OWNER','ADMIN')", "INT", "VARCHAR(36)"]
- 示例：[["2014-10-15T01:44:40", "2023-01-31T16:05:25", null, 509070, null, "be417436c0174498bf721e849e119555", "d1fe1eee802541b8bd5ed61cd3a05d77", "e533ca5e-1dc0-4b4d-8023-bc15624a5e63", null, null, 0, "solar_plasm", "2f6cbc63d7af29b70f7d341260041795", 4, "shelved_offloaded", 32768, 8, "glyph-helix-nexus", "", "replaced_user_data.509070", "r-m3yx01v5", "2014-10-15T01:44:41", "2016-09-26T17:42:44", null, 

### INSTANCE_SYSTEM_METADATA

- 列：["CREATED_AT", "UPDATED_AT", "DELETED_AT", "ID", "INSTANCE_UUID", "KEY", "VALUE", "DELETED"]
- 类型：["DATETIME", "DATETIME", "DATETIME", "INT", "VARCHAR(36)", "VARCHAR(255)", "VARCHAR(255)", "INT"]
- 示例：[["2014-10-15T01:44:40", null, null, 8417981, "891365b3-6b62-4e92-b683-1694678b9e74", "image_instance_type_root_gb", "arrow_theta", 0], ["2014-10-15T01:44:40", null, null, 8417986, "891365b3-6b62-4e92-b683-1694678b9e74", "image_image_location", "neon", 0], ["2014-10-15T01:44:40", null, null, 8417988, "891365b3-6b62-4e92-b683-1694678b9e74", "image_image_type", "neon", 0]]

## 子问题

["For instances whose display name is 'forge', show the instance UUID, hostname, VM state, memory in MB, the instance extra record ID, and the minimum memory (in MB) over a window of 3 preceding and 1 following rows ordered by the instance extra ID.", "For migrations that are marked as completed, list the migration status, the instance display name, and the instance flavor JSON from instance extra, and assign row numbers ordered by the instance display name using a window frame of 2 preceding rows and 1 following row."]
