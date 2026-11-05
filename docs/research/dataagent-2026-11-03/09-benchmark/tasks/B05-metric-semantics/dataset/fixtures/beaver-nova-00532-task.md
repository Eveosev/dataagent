# 查询任务（nova）

## 问题

For each VM state on host `blaze8-12`, list the VM state, the total number of non-deleted instances that have a system metadata entry with key `image_image_type` and also have a non-deleted network info cache record, and the average memory (MB) of those instances. Do not repeat the VM state if it is the same as the previous row. Include a grand total row. Do not return any rounded answers.

## 库

nova

## 涉及表

["INSTANCE_SYSTEM_METADATA", "INSTANCES", "INSTANCE_INFO_CACHES"]

## 连接键

[["INSTANCES.UUID", "INSTANCE_SYSTEM_METADATA.INSTANCE_UUID"], ["INSTANCES.UUID", "INSTANCE_INFO_CACHES.INSTANCE_UUID"]]

## 列映射

{"non-deleted instances": ["INSTANCES.DELETED"], "system metadata entry key `image_image_type`": ["INSTANCE_SYSTEM_METADATA.KEY"], "instances": ["INSTANCES.UUID", "INSTANCE_SYSTEM_METADATA.INSTANCE_UUID", "INSTANCE_INFO_CACHES.INSTANCE_UUID"], "non-deleted network info cache record": ["INSTANCE_INFO_CACHES.INSTANCE_UUID"]}

## 领域知识

["Host \"blaze8-12\" is predicated by \"instances.host = 'blaze8-12'\""]

## 表结构

### INSTANCES

- 列：["CREATED_AT", "UPDATED_AT", "DELETED_AT", "ID", "INTERNAL_ID", "USER_ID", "PROJECT_ID", "IMAGE_REF", "KERNEL_ID", "RAMDISK_ID", "LAUNCH_INDEX", "KEY_NAME", "KEY_DATA", "POWER_STATE", "VM_STATE", "MEMORY_MB", "VCPUS", "HOSTNAME", "HOST", "USER_DATA", "RESERVATION_ID", "SCHEDULED_AT", "LAUNCHED_AT", "TERMINATED_AT", "DISPLAY_NAME", "DISPLAY_DESCRIPTION", "AVAILABILITY_ZONE", "LOCKED", "OS_TYPE", "LAUNCHED_ON", "INSTANCE_TYPE_ID", "VM_MODE", "UUID", "ARCHITECTURE", "ROOT_DEVICE_NAME", "ACCESS_IP_V4", "ACCESS_IP_V6", "CONFIG_DRIVE", "TASK_STATE", "DEFAULT_EPHEMERAL_DEVICE", "DEFAULT_SWAP_DEVICE", "PROGRESS", "AUTO_DISK_CONFIG", "SHUTDOWN_TERMINATE", "DISABLE_TERMINATE", "ROOT_GB", "EPHEMERAL_GB", "CELL_NAME", "NODE", "DELETED", "LOCKED_BY", "CLEANED", "EPHEMERAL_KEY_UUID"]
- 类型：["DATETIME", "DATETIME", "DATETIME", "INT", "INT", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "INT", "VARCHAR(255)", "TEXT", "INT", "VARCHAR(255)", "INT", "INT", "VARCHAR(255)", "VARCHAR(255)", "TEXT", "VARCHAR(255)", "DATETIME", "DATETIME", "DATETIME", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "TINYINT(1)", "VARCHAR(255)", "TEXT", "INT", "VARCHAR(255)", "VARCHAR(36)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(39)", "VARCHAR(39)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "INT", "TINYINT(1)", "TINYINT(1)", "TINYINT(1)", "INT", "INT", "VARCHAR(255)", "VARCHAR(255)", "INT", "ENUM('OWNER','ADMIN')", "INT", "VARCHAR(36)"]
- 示例：[["2014-10-15T01:44:40", "2023-01-31T16:05:25", null, 509070, null, "be417436c0174498bf721e849e119555", "d1fe1eee802541b8bd5ed61cd3a05d77", "e533ca5e-1dc0-4b4d-8023-bc15624a5e63", null, null, 0, "solar_plasm", "2f6cbc63d7af29b70f7d341260041795", 4, "shelved_offloaded", 32768, 8, "glyph-helix-nexus", "", "replaced_user_data.509070", "r-m3yx01v5", "2014-10-15T01:44:41", "2016-09-26T17:42:44", null, 

## 子问题

["How many non-deleted instances on host `blaze8-12` have a system metadata entry with the key `image_image_type` and also have a non-deleted network info cache record?"]
