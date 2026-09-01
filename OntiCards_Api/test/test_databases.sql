-- ============================================================
-- OntiCards NL2SQL 测试数据库（含字段描述）
-- ============================================================
-- 说明：
--   - 本脚本创建3个独立的测试数据库（库1单库测试，库2+库3跨库测试）
--   - 每个库包含3-6张表，表结构简单，数据量适中
--   - 数据之间有一定关联，方便测试JOIN查询
--   - 使用 COMMENT ON 添加字段描述（PostgreSQL）
--   - 执行脚本前请先创建对应数据库
-- ============================================================


-- ============================================================
-- 【库1】PostgreSQL - 单库查询测试
-- 数据库名：test_nl2sql_pg_single
-- 场景：测试单库内的NL2SQL效果
-- ============================================================

-- 创建数据库（PostgreSQL）
-- CREATE DATABASE test_nl2sql_pg_single;

-- 连接后执行以下脚本

-- ---- 表1：员工信息表 ----
CREATE TABLE IF NOT EXISTS employees (
    employee_id SERIAL PRIMARY KEY,
    employee_name VARCHAR(50) NOT NULL,
    department_id INTEGER,
    hire_date DATE,
    salary DECIMAL(10, 2),
    status VARCHAR(20) DEFAULT '在职'  -- 在职/离职
);

-- 添加字段描述
COMMENT ON COLUMN employees.employee_id IS '员工ID（主键，自增）';
COMMENT ON COLUMN employees.employee_name IS '员工姓名';
COMMENT ON COLUMN employees.department_id IS '部门ID（外键关联departments表）';
COMMENT ON COLUMN employees.hire_date IS '入职日期';
COMMENT ON COLUMN employees.salary IS '月薪（元）';
COMMENT ON COLUMN employees.status IS '员工状态（在职/离职）';

-- ---- 表2：部门信息表 ----
CREATE TABLE IF NOT EXISTS departments (
    department_id SERIAL PRIMARY KEY,
    department_name VARCHAR(50) NOT NULL,
    manager_id INTEGER,
    location VARCHAR(100)
);

COMMENT ON COLUMN departments.department_id IS '部门ID（主键，自增）';
COMMENT ON COLUMN departments.department_name IS '部门名称';
COMMENT ON COLUMN departments.manager_id IS '部门经理ID（外键关联employees表）';
COMMENT ON COLUMN departments.location IS '办公地点';

-- ---- 表3：工资记录表 ----
CREATE TABLE IF NOT EXISTS salary_records (
    record_id SERIAL PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(employee_id),
    pay_month DATE NOT NULL,
    base_salary DECIMAL(10, 2),
    bonus DECIMAL(10, 2) DEFAULT 0,
    deduction DECIMAL(10, 2) DEFAULT 0,
    final_salary DECIMAL(10, 2)
);

COMMENT ON COLUMN salary_records.record_id IS '记录ID（主键，自增）';
COMMENT ON COLUMN salary_records.employee_id IS '员工ID（外键关联employees表）';
COMMENT ON COLUMN salary_records.pay_month IS '工资月份';
COMMENT ON COLUMN salary_records.base_salary IS '基本工资（元）';
COMMENT ON COLUMN salary_records.bonus IS '奖金（元）';
COMMENT ON COLUMN salary_records.deduction IS '扣款（元）';
COMMENT ON COLUMN salary_records.final_salary IS '实发工资（元）';

-- ---- 表4：项目信息表 ----
CREATE TABLE IF NOT EXISTS projects (
    project_id SERIAL PRIMARY KEY,
    project_name VARCHAR(100) NOT NULL,
    department_id INTEGER REFERENCES departments(department_id),
    start_date DATE,
    end_date DATE,
    budget DECIMAL(15, 2),
    status VARCHAR(20) DEFAULT '进行中'  -- 进行中/已完成/已取消
);

COMMENT ON COLUMN projects.project_id IS '项目ID（主键，自增）';
COMMENT ON COLUMN projects.project_name IS '项目名称';
COMMENT ON COLUMN projects.department_id IS '所属部门ID（外键关联departments表）';
COMMENT ON COLUMN projects.start_date IS '项目开始日期';
COMMENT ON COLUMN projects.end_date IS '项目结束日期';
COMMENT ON COLUMN projects.budget IS '项目预算（元）';
COMMENT ON COLUMN projects.status IS '项目状态（进行中/已完成/已取消）';

-- ---- 表5：员工项目参与表 ----
CREATE TABLE IF NOT EXISTS employee_projects (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(employee_id),
    project_id INTEGER REFERENCES projects(project_id),
    role VARCHAR(50),
    join_date DATE
);

COMMENT ON COLUMN employee_projects.id IS '参与记录ID（主键，自增）';
COMMENT ON COLUMN employee_projects.employee_id IS '员工ID（外键关联employees表）';
COMMENT ON COLUMN employee_projects.project_id IS '项目ID（外键关联projects表）';
COMMENT ON COLUMN employee_projects.role IS '在项目中的角色（如：技术负责人、开发工程师、项目经理等）';
COMMENT ON COLUMN employee_projects.join_date IS '加入项目日期';

-- ---- 初始化数据 ----
-- 部门数据
INSERT INTO departments (department_name, manager_id, location) VALUES
('研发部', 1, '北京'),
('市场部', 5, '上海'),
('人力资源部', 8, '北京'),
('财务部', 10, '深圳');

-- 员工数据
INSERT INTO employees (employee_name, department_id, hire_date, salary, status) VALUES
('张三', 1, '2020-01-15', 15000.00, '在职'),
('李四', 1, '2020-03-20', 12000.00, '在职'),
('王五', 1, '2021-06-10', 11000.00, '在职'),
('赵六', 2, '2019-08-01', 18000.00, '在职'),
('孙七', 2, '2020-11-15', 13000.00, '在职'),
('周八', 3, '2018-05-01', 14000.00, '在职'),
('吴九', 3, '2021-02-28', 10000.00, '离职'),
('郑十', 4, '2019-12-01', 16000.00, '在职'),
('刘一', 1, '2022-01-10', 9000.00, '在职'),
('陈二', 2, '2022-03-15', 11000.00, '在职');

-- 工资记录
INSERT INTO salary_records (employee_id, pay_month, base_salary, bonus, deduction, final_salary) VALUES
(1, '2024-01-01', 15000.00, 2000.00, 1500.00, 15500.00),
(2, '2024-01-01', 12000.00, 1500.00, 1200.00, 12300.00),
(3, '2024-01-01', 11000.00, 1000.00, 1100.00, 10900.00),
(4, '2024-01-01', 18000.00, 3000.00, 1800.00, 19200.00),
(5, '2024-01-01', 13000.00, 2000.00, 1300.00, 13700.00),
(1, '2024-02-01', 15000.00, 2500.00, 1500.00, 16000.00),
(2, '2024-02-01', 12000.00, 1800.00, 1200.00, 12600.00),
(3, '2024-02-01', 11000.00, 1200.00, 1100.00, 11100.00),
(4, '2024-02-01', 18000.00, 3500.00, 1800.00, 19700.00),
(5, '2024-02-01', 13000.00, 2200.00, 1300.00, 13900.00);

-- 项目数据
INSERT INTO projects (project_name, department_id, start_date, end_date, budget, status) VALUES
('智能推荐系统', 1, '2023-01-01', '2024-06-30', 500000.00, '已完成'),
('用户画像分析', 1, '2023-06-01', '2024-03-31', 300000.00, '已完成'),
('营销活动平台', 2, '2023-09-01', '2024-08-31', 400000.00, '进行中'),
('HR系统升级', 3, '2024-01-01', '2024-12-31', 200000.00, '进行中'),
('财务自动化', 4, '2024-02-01', '2024-10-31', 350000.00, '进行中');

-- 员工项目参与
INSERT INTO employee_projects (employee_id, project_id, role, join_date) VALUES
(1, 1, '技术负责人', '2023-01-01'),
(2, 1, '开发工程师', '2023-01-01'),
(3, 2, '开发工程师', '2023-06-01'),
(1, 2, '技术负责人', '2023-06-01'),
(4, 3, '项目经理', '2023-09-01'),
(5, 3, '市场专员', '2023-09-01'),
(6, 4, '项目负责人', '2024-01-01'),
(8, 5, '财务主管', '2024-02-01');


-- ============================================================
-- 【库2】PostgreSQL - 跨库测试（库A）
-- 数据库名：test_nl2sql_pg_a
-- 场景：与MySQL库组成跨库测试场景
-- ============================================================

-- CREATE DATABASE test_nl2sql_pg_a;

-- ---- 表1：供应商信息表 ----
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id SERIAL PRIMARY KEY,
    supplier_name VARCHAR(100) NOT NULL,
    contact_person VARCHAR(50),
    phone VARCHAR(20),
    address VARCHAR(200),
    credit_level INTEGER DEFAULT 3,  -- 1-5，5最高
    status VARCHAR(20) DEFAULT '正常'  -- 正常/暂停/终止
);

COMMENT ON COLUMN suppliers.supplier_id IS '供应商ID（主键，自增）';
COMMENT ON COLUMN suppliers.supplier_name IS '供应商名称';
COMMENT ON COLUMN suppliers.contact_person IS '联系人姓名';
COMMENT ON COLUMN suppliers.phone IS '联系电话';
COMMENT ON COLUMN suppliers.address IS '供应商地址';
COMMENT ON COLUMN suppliers.credit_level IS '信用等级（1-5，5为最高等级）';
COMMENT ON COLUMN suppliers.status IS '供应商状态（正常/暂停/终止合作）';

-- ---- 表2：采购订单表 ----
CREATE TABLE IF NOT EXISTS purchase_orders (
    order_id SERIAL PRIMARY KEY,
    supplier_id INTEGER REFERENCES suppliers(supplier_id),
    order_date DATE NOT NULL,
    total_amount DECIMAL(15, 2),
    status VARCHAR(20) DEFAULT '待审批',  -- 待审批/已审批/已发货/已完成/已取消
    create_user VARCHAR(50)
);

COMMENT ON COLUMN purchase_orders.order_id IS '订单ID（主键，自增）';
COMMENT ON COLUMN purchase_orders.supplier_id IS '供应商ID（外键关联suppliers表）';
COMMENT ON COLUMN purchase_orders.order_date IS '订单日期';
COMMENT ON COLUMN purchase_orders.total_amount IS '订单总金额（元）';
COMMENT ON COLUMN purchase_orders.status IS '订单状态（待审批/已审批/已发货/已完成/已取消）';
COMMENT ON COLUMN purchase_orders.create_user IS '创建订单的用户/员工姓名';

-- ---- 表3：订单明细表 ----
CREATE TABLE IF NOT EXISTS order_items (
    item_id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES purchase_orders(order_id),
    product_name VARCHAR(100),
    quantity INTEGER,
    unit_price DECIMAL(10, 2),
    subtotal DECIMAL(15, 2)
);

COMMENT ON COLUMN order_items.item_id IS '明细ID（主键，自增）';
COMMENT ON COLUMN order_items.order_id IS '订单ID（外键关联purchase_orders表）';
COMMENT ON COLUMN order_items.product_name IS '产品名称';
COMMENT ON COLUMN order_items.quantity IS '采购数量';
COMMENT ON COLUMN order_items.unit_price IS '单价（元）';
COMMENT ON COLUMN order_items.subtotal IS '小计金额（元）';

-- ---- 初始化数据 ----
INSERT INTO suppliers (supplier_name, contact_person, phone, address, credit_level, status) VALUES
('华强电子', '王强', '13800138001', '深圳市南山区科技园', 5, '正常'),
('东方贸易', '李明', '13900139002', '广州市天河区珠江新城', 4, '正常'),
('北方物资', '张伟', '13700137003', '北京市朝阳区CBD', 3, '正常'),
('南方建材', '刘芳', '13600136004', '佛山市顺德区', 4, '暂停'),
('西方五金', '陈军', '13500135005', '成都市高新区', 2, '正常');

INSERT INTO purchase_orders (supplier_id, order_date, total_amount, status, create_user) VALUES
(1, '2024-01-05', 50000.00, '已完成', '张三'),
(1, '2024-01-15', 35000.00, '已完成', '李四'),
(2, '2024-01-20', 28000.00, '已完成', '张三'),
(3, '2024-02-01', 42000.00, '已发货', '王五'),
(2, '2024-02-10', 15000.00, '待审批', '李四'),
(4, '2024-02-15', 8000.00, '已取消', '赵六'),
(5, '2024-02-20', 55000.00, '已完成', '张三'),
(1, '2024-03-01', 38000.00, '已完成', '李四');

INSERT INTO order_items (order_id, product_name, quantity, unit_price, subtotal) VALUES
(1, '电子元器件A型', 1000, 50.00, 50000.00),
(2, '电子元器件B型', 700, 50.00, 35000.00),
(3, '办公设备套装', 50, 560.00, 28000.00),
(4, '建筑材料一批', 200, 210.00, 42000.00),
(5, '文具用品', 300, 50.00, 15000.00),
(6, '五金工具', 100, 80.00, 8000.00),
(7, '机械设备配件', 55, 1000.00, 55000.00),
(8, '电子元器件C型', 760, 50.00, 38000.00);


-- ============================================================
-- 【库3】MySQL8 - 跨库测试（库B）
-- 数据库名：test_nl2sql_mysql_b
-- 场景：与PostgreSQL库组成跨库测试场景
-- ============================================================

-- CREATE DATABASE test_nl2sql_mysql_b;

-- ---- 表1：产品目录表 ----
CREATE TABLE IF NOT EXISTS products (
    product_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '产品ID（主键，自增）',
    product_name VARCHAR(100) NOT NULL COMMENT '产品名称',
    category VARCHAR(50) COMMENT '产品类别（如：电子元件、办公用品、建材等）',
    unit_price DECIMAL(10, 2) COMMENT '产品单价（元）',
    stock_quantity INT DEFAULT 0 COMMENT '库存数量',
    supplier_id INT COMMENT '供应商ID（关联suppliers表）',
    status VARCHAR(20) DEFAULT '在售' COMMENT '产品状态（在售/停产/缺货）'
);

-- ---- 表2：销售订单表 ----
CREATE TABLE IF NOT EXISTS sales_orders (
    order_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '订单ID（主键，自增）',
    customer_name VARCHAR(100) COMMENT '客户名称',
    order_date DATE NOT NULL COMMENT '订单日期',
    total_amount DECIMAL(15, 2) COMMENT '订单总金额（元）',
    status VARCHAR(20) DEFAULT '待发货' COMMENT '订单状态（待发货/已发货/已完成/已退货）',
    sales_person VARCHAR(50) COMMENT '销售人员姓名'
);

-- ---- 表3：销售明细表 ----
CREATE TABLE IF NOT EXISTS sales_items (
    item_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '明细ID（主键，自增）',
    order_id INT COMMENT '订单ID（外键关联sales_orders表）',
    product_id INT COMMENT '产品ID（外键关联products表）',
    quantity INT COMMENT '销售数量',
    unit_price DECIMAL(10, 2) COMMENT '销售单价（元）',
    subtotal DECIMAL(15, 2) COMMENT '小计金额（元）'
);

-- ---- 表4：客户信息表 ----
CREATE TABLE IF NOT EXISTS customers (
    customer_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '客户ID（主键，自增）',
    customer_name VARCHAR(100) NOT NULL COMMENT '客户名称',
    contact_phone VARCHAR(20) COMMENT '联系电话',
    customer_type VARCHAR(20) DEFAULT '普通' COMMENT '客户类型（普通/VIP/企业）',
    credit_score INT DEFAULT 80 COMMENT '信用评分（0-100，分数越高信用越好）',
    registered_date DATE COMMENT '注册/登记日期'
);

-- ---- 初始化数据 ----
INSERT INTO products (product_name, category, unit_price, stock_quantity, supplier_id, status) VALUES
('电子元器件A型', '电子元件', 50.00, 5000, 1, '在售'),
('电子元器件B型', '电子元件', 50.00, 3000, 1, '在售'),
('电子元器件C型', '电子元件', 50.00, 4500, 1, '在售'),
('办公设备套装', '办公用品', 560.00, 100, 2, '在售'),
('建筑材料一批', '建材', 210.00, 2000, 3, '在售'),
('文具用品', '办公用品', 50.00, 8000, NULL, '在售'),
('五金工具', '五金', 80.00, 1500, 5, '在售'),
('机械设备配件', '机械', 1000.00, 200, 5, '在售');

INSERT INTO customers (customer_name, contact_phone, customer_type, credit_score, registered_date) VALUES
('阿里巴巴', '13900000001', '企业', 95, '2020-01-01'),
('腾讯科技', '13900000002', '企业', 98, '2020-03-15'),
('京东商城', '13900000003', '企业', 92, '2020-06-20'),
('张小明', '13800000004', 'VIP', 85, '2021-02-01'),
('李小红', '13800000005', '普通', 70, '2021-08-15'),
('王大力', '13800000006', '普通', 75, '2022-01-10');

INSERT INTO sales_orders (customer_name, order_date, total_amount, status, sales_person) VALUES
('阿里巴巴', '2024-01-10', 50000.00, '已完成', '销售员A'),
('腾讯科技', '2024-01-15', 35000.00, '已完成', '销售员B'),
('京东商城', '2024-01-20', 28000.00, '已完成', '销售员A'),
('张小明', '2024-02-05', 1500.00, '已完成', '销售员C'),
('李小红', '2024-02-10', 560.00, '已退货', '销售员B'),
('王大力', '2024-02-15', 2100.00, '已发货', '销售员C'),
('阿里巴巴', '2024-02-20', 42000.00, '已完成', '销售员A'),
('张小明', '2024-03-01', 800.00, '待发货', '销售员B');

INSERT INTO sales_items (order_id, product_id, quantity, unit_price, subtotal) VALUES
(1, 1, 1000, 50.00, 50000.00),
(2, 2, 700, 50.00, 35000.00),
(3, 4, 50, 560.00, 28000.00),
(4, 6, 30, 50.00, 1500.00),
(5, 4, 1, 560.00, 560.00),
(6, 5, 10, 210.00, 2100.00),
(7, 5, 200, 210.00, 42000.00),
(8, 6, 16, 50.00, 800.00);


-- ============================================================
-- 数据导入验证查询
-- ============================================================

-- PostgreSQL 单库验证
-- SELECT 'employees' as table_name, COUNT(*) as row_count FROM employees
-- UNION ALL SELECT 'departments', COUNT(*) FROM departments
-- UNION ALL SELECT 'salary_records', COUNT(*) FROM salary_records
-- UNION ALL SELECT 'projects', COUNT(*) FROM projects
-- UNION ALL SELECT 'employee_projects', COUNT(*) FROM employee_projects;

-- PostgreSQL 跨库数据验证
-- SELECT 'suppliers' as table_name, COUNT(*) as row_count FROM suppliers
-- UNION ALL SELECT 'purchase_orders', COUNT(*) FROM purchase_orders
-- UNION ALL SELECT 'order_items', COUNT(*) FROM order_items;

-- MySQL 跨库数据验证
-- SELECT 'products' as table_name, COUNT(*) as row_count FROM products
-- UNION ALL SELECT 'sales_orders', COUNT(*) FROM sales_orders
-- UNION ALL SELECT 'sales_items', COUNT(*) FROM sales_items
-- UNION ALL SELECT 'customers', COUNT(*) FROM customers;


-- ============================================================
-- 验证字段描述（PostgreSQL）
-- ============================================================
-- 执行以下SQL查看字段描述：
-- SELECT
--     c.table_name,
--     c.column_name,
--     c.data_type,
--     col_description(format('%s.%s', c.table_schema, c.table_name)::regclass::oid, c.ordinal_position) as column_description
-- FROM information_schema.columns c
-- WHERE c.table_schema = 'public'
-- ORDER BY c.table_name, c.ordinal_position;
