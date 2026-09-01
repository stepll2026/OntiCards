# OntiCards NL2SQL 测试用例集

## 测试环境说明

### 数据库配置

| 数据库 | 类型 | 用途 | 表数量 |
|--------|------|------|--------|
| test_nl2sql_pg_single | PostgreSQL | 单库查询测试 | 5张表 |
| test_nl2sql_pg_a | PostgreSQL | 跨库测试（库A） | 3张表 |
| test_nl2sql_mysql_b | MySQL 8 | 跨库测试（库B） | 4张表 |

---

## 【测试分组1】单库查询测试

**数据库**: test_nl2sql_pg_single (PostgreSQL)

**数据表说明**:
- `employees` - 员工信息表 (10条数据)
- `departments` - 部门信息表 (4条数据)
- `salary_records` - 工资记录表 (10条数据)
- `projects` - 项目信息表 (5条数据)
- `employee_projects` - 员工项目参与表 (8条数据)

**关联关系**:
- employees.department_id → departments.department_id
- salary_records.employee_id → employees.employee_id
- projects.department_id → departments.department_id
- employee_projects.employee_id → employees.employee_id
- employee_projects.project_id → projects.project_id

---

### 用例1.1：单表简单查询

**测试问句**: "研发部有哪些员工？"

**预期SQL**:
```sql
SELECT t1.employee_name, t1.hire_date, t1.salary
FROM employees AS t1
JOIN departments AS t2 ON t1.department_id = t2.department_id
WHERE t2.department_name = '研发部'
```

**预期结果**: 返回4条记录（张三、李四、王五、刘一的 department_id=1，研发部）

| employee_name | hire_date | salary |
|---------------|-----------|--------|
| 张三 | 2020-01-15 | 15000.00 |
| 李四 | 2020-03-20 | 12000.00 |
| 王五 | 2021-06-10 | 11000.00 |
| 刘一 | 2022-01-10 | 9000.00 |

---

### 用例1.2：聚合统计查询

**测试问句**: "统计每个部门的员工数量"

**预期SQL**:
```sql
SELECT t2.department_name, COUNT(t1.employee_id) AS employee_count
FROM employees AS t1
JOIN departments AS t2 ON t1.department_id = t2.department_id
GROUP BY t2.department_name
```

**预期结果**: 返回4条记录

| department_name | employee_count |
|-----------------|----------------|
| 研发部 | 4 |
| 市场部 | 3 |
| 人力资源部 | 2 |
| 财务部 | 1 |

---

### 用例1.3：条件筛选查询

**测试问句**: "工资大于15000的员工有哪些？"

**预期SQL**:
```sql
SELECT employee_name, salary, hire_date
FROM employees
WHERE salary > 15000
```

**预期结果**: 返回2条记录

| employee_name | salary | hire_date |
|---------------|--------|-----------|
| 赵六 | 18000.00 | 2019-08-01 |
| 郑十 | 16000.00 | 2019-12-01 |

---

### 用例1.4：多表JOIN查询

**测试问句**: "查询员工的工资记录，包括员工姓名、部门、月份和实发工资"

**预期SQL**:
```sql
SELECT t1.employee_name, t3.department_name, t2.pay_month, t2.final_salary
FROM employees AS t1
JOIN salary_records AS t2 ON t1.employee_id = t2.employee_id
JOIN departments AS t3 ON t1.department_id = t3.department_id
```

**预期结果**: 返回10条记录（员工1-5各2个月份的工资记录）

| employee_name | department_name | pay_month | final_salary |
|---------------|-----------------|-----------|--------------|
| 张三 | 研发部 | 2024-01-01 | 15500.00 |
| 张三 | 研发部 | 2024-02-01 | 16000.00 |
| 李四 | 研发部 | 2024-01-01 | 12300.00 |
| 李四 | 研发部 | 2024-02-01 | 12600.00 |
| 王五 | 研发部 | 2024-01-01 | 10900.00 |
| 王五 | 研发部 | 2024-02-01 | 11100.00 |
| 赵六 | 市场部 | 2024-01-01 | 19200.00 |
| 赵六 | 市场部 | 2024-02-01 | 19700.00 |
| 孙七 | 市场部 | 2024-01-01 | 13700.00 |
| 孙七 | 市场部 | 2024-02-01 | 13900.00 |

---

### 用例1.5：子查询

**测试问句**: "查询参与过项目的员工姓名"

**预期SQL**:
```sql
SELECT DISTINCT t1.employee_name
FROM employees AS t1
JOIN employee_projects AS t2 ON t1.employee_id = t2.employee_id
```

**预期结果**: 返回7条记录（张三、李四、王五、赵六、孙七、周八、郑十参与过项目）

| employee_name |
|---------------|
| 张三 |
| 李四 |
| 王五 |
| 赵六 |
| 孙七 |
| 周八 |
| 郑十 |

---

### 用例1.6：ORDER BY 排序

**测试问句**: "按工资从高到低列出所有在职员工"

**预期SQL**:
```sql
SELECT employee_name, salary, hire_date
FROM employees
WHERE status = '在职'
ORDER BY salary DESC
```

**预期结果**: 返回9条记录（已排除离职的吴九），按工资降序

| employee_name | salary | hire_date |
|---------------|--------|-----------|
| 赵六 | 18000.00 | 2019-08-01 |
| 郑十 | 16000.00 | 2019-12-01 |
| 张三 | 15000.00 | 2020-01-15 |
| 周八 | 14000.00 | 2018-05-01 |
| 孙七 | 13000.00 | 2020-11-15 |
| 李四 | 12000.00 | 2020-03-20 |
| 陈二 | 11000.00 | 2022-03-15 |
| 王五 | 11000.00 | 2021-06-10 |
| 刘一 | 9000.00 | 2022-01-10 |

---

## 【测试分组2】跨库查询测试

**数据库组合**:
- test_nl2sql_pg_a (PostgreSQL) - 库A
- test_nl2sql_mysql_b (MySQL 8) - 库B

**数据表说明（库A - PostgreSQL）**:
- `suppliers` - 供应商信息表 (5条数据)
- `purchase_orders` - 采购订单表 (8条数据)
- `order_items` - 订单明细表 (8条数据)

**数据表说明（库B - MySQL）**:
- `products` - 产品目录表 (8条数据)
- `sales_orders` - 销售订单表 (8条数据)
- `sales_items` - 销售明细表 (8条数据)
- `customers` - 客户信息表 (6条数据)

---

### 用例2.1：跨库统计（分布查询）

**测试问句**: "各供应商的采购订单数量是多少？"

**预期SQL（PostgreSQL）**:
```sql
SELECT t1.supplier_name, COUNT(t2.order_id) AS order_count
FROM suppliers AS t1
LEFT JOIN purchase_orders AS t2 ON t1.supplier_id = t2.supplier_id
GROUP BY t1.supplier_name
```

**预期结果**:

| supplier_name | order_count |
|---------------|-------------|
| 华强电子 | 3 |
| 东方贸易 | 2 |
| 北方物资 | 1 |
| 南方建材 | 1 |
| 西方五金 | 1 |

---

### 用例2.2：跨库关联查询

**测试问句**: "查询采购金额大于30000的订单，包括供应商名称、订单日期和总金额"

**预期SQL（PostgreSQL）**:
```sql
SELECT t1.supplier_name, t2.order_date, t2.total_amount
FROM suppliers AS t1
JOIN purchase_orders AS t2 ON t1.supplier_id = t2.supplier_id
WHERE t2.total_amount > 30000
```

**预期结果**:

| supplier_name | order_date | total_amount |
|---------------|------------|--------------|
| 华强电子 | 2024-01-05 | 50000.00 |
| 华强电子 | 2024-01-15 | 35000.00 |
| 北方物资 | 2024-02-01 | 42000.00 |
| 西方五金 | 2024-02-20 | 55000.00 |
| 华强电子 | 2024-03-01 | 38000.00 |

---

### 用例2.3：多库融合查询

**测试问句**: "统计各类产品的销量（跨PostgreSQL采购库和MySQL销售库）"

**说明**: 此用例需要两个库的数据融合
- PostgreSQL: order_items 表（采购明细）
- MySQL: sales_items 表（销售明细）

**预期行为**: 分别在两个库执行查询，然后通过产品名称进行融合

**PostgreSQL SQL（采购统计）**:
```sql
SELECT t1.product_name, SUM(t1.quantity) AS total_purchase_qty
FROM order_items AS t1
GROUP BY t1.product_name
```

**PostgreSQL 采购结果**:
| product_name | total_purchase_qty |
|--------------|-------------------|
| 电子元器件A型 | 1000 |
| 电子元器件B型 | 700 |
| 电子元器件C型 | 760 |
| 办公设备套装 | 50 |
| 建筑材料一批 | 200 |
| 文具用品 | 300 |
| 五金工具 | 100 |
| 机械设备配件 | 55 |

**MySQL SQL（销售统计）**:
```sql
SELECT t1.product_name, SUM(t1.quantity) AS total_sales_qty
FROM sales_items AS t1
GROUP BY t1.product_name
```

**MySQL 销售结果**:
| product_name | total_sales_qty |
|--------------|-----------------|
| 电子元器件A型 | 1000 |
| 电子元器件B型 | 700 |
| 建筑材料一批 | 51 |
| 文具用品 | 46 |
| 五金工具 | 210 |

**融合结果（按产品名称匹配合并）**:

| product_name | total_purchase_qty | total_sales_qty |
|--------------|-------------------|-----------------|
| 电子元器件A型 | 1000 | 1000 |
| 电子元器件B型 | 700 | 700 |
| 电子元器件C型 | 760 | 0 |
| 建筑材料一批 | 200 | 51 |
| 文具用品 | 300 | 46 |
| 五金工具 | 100 | 210 |
| 办公设备套装 | 50 | 0 |
| 机械设备配件 | 55 | 0 |

---

## 【测试分组3】边界条件测试

### 用例3.1：空结果查询

**测试问句**: "查询所有状态为'已取消'的采购订单"

**预期SQL**:
```sql
SELECT t1.supplier_name, t2.order_date, t2.total_amount
FROM suppliers AS t1
JOIN purchase_orders AS t2 ON t1.supplier_id = t2.supplier_id
WHERE t2.status = '已取消'
```

**预期结果**: 返回1条记录

| supplier_name | order_date | total_amount |
|---------------|------------|--------------|
| 南方建材 | 2024-02-15 | 8000.00 |

---

### 用例3.2：COUNT统计（结果为0）

**测试问句**: "西方五金供应商有多少个采购订单？"

**预期SQL**:
```sql
SELECT COUNT(*) AS order_count
FROM suppliers AS t1
JOIN purchase_orders AS t2 ON t1.supplier_id = t2.supplier_id
WHERE t1.supplier_name = '西方五金'
```

**预期结果**: 返回1条记录，值为1

| order_count |
|-------------|
| 1 |

---

### 用例3.3：模糊查询

**测试问句**: "查询名称包含'电子'的供应商有哪些？"

**预期SQL**:
```sql
SELECT supplier_name, contact_person, phone
FROM suppliers
WHERE supplier_name LIKE '%电子%'
```

**预期结果**: 返回1条记录

| supplier_name | contact_person | phone |
|---------------|----------------|-------|
| 华强电子 | 王强 | 13800138001 |

---
