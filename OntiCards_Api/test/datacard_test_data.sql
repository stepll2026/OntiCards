-- =====================================================
-- 数据卡片生成测试 - PostgreSQL 测试数据
-- 场景覆盖：缺注释、有注释有枚举值、有注释无枚举值
-- =====================================================

-- 1. 客户表（有注释有枚举值）
DROP TABLE IF EXISTS t_customer CASCADE;
CREATE TABLE t_customer (
    customer_id BIGSERIAL PRIMARY KEY,
    customer_code VARCHAR(20) NOT NULL UNIQUE,
    customer_name VARCHAR(100) NOT NULL,
    customer_type VARCHAR(10) NOT NULL,
    industry VARCHAR(50),
    region VARCHAR(20),
    status VARCHAR(10) NOT NULL DEFAULT 'normal',
    credit_level VARCHAR(5),
    contact_person VARCHAR(50),
    contact_phone VARCHAR(20),
    address TEXT,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_customer IS '客户信息表，记录客户的基础信息和业务属性';
COMMENT ON COLUMN t_customer.customer_id IS '客户ID，主键';
COMMENT ON COLUMN t_customer.customer_code IS '客户编码，唯一标识';
COMMENT ON COLUMN t_customer.customer_name IS '客户名称，全称';
COMMENT ON COLUMN t_customer.customer_type IS '客户类型，包括：普通客户、战略客户、重点客户';
COMMENT ON COLUMN t_customer.industry IS '所属行业，包括：电子制造、工业设备、汽车零部件、医疗器械';
COMMENT ON COLUMN t_customer.region IS '所属区域，包括：华东、华南、华北、华中、西南、西北、东北';
COMMENT ON COLUMN t_customer.status IS '客户状态，包括：normal-正常、frozen-冻结、cancelled-注销';
COMMENT ON COLUMN t_customer.credit_level IS '信用等级，AAA、AA、A、BB、B';
COMMENT ON COLUMN t_customer.contact_person IS '联系人';
COMMENT ON COLUMN t_customer.contact_phone IS '联系电话';
COMMENT ON COLUMN t_customer.address IS '客户地址';

-- 2. 订单表（有注释无枚举值）
DROP TABLE IF EXISTS t_order CASCADE;
CREATE TABLE t_order (
    order_id BIGSERIAL PRIMARY KEY,
    order_no VARCHAR(30) NOT NULL UNIQUE,
    customer_id BIGINT NOT NULL REFERENCES t_customer(customer_id),
    order_date DATE NOT NULL,
    order_amount DECIMAL(15,2) NOT NULL,
    discount_amount DECIMAL(15,2) DEFAULT 0,
    final_amount DECIMAL(15,2) NOT NULL,
    payment_status VARCHAR(20) NOT NULL,
    delivery_status VARCHAR(20) NOT NULL,
    order_source VARCHAR(30),
    salesman_id BIGINT,
    remark TEXT,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_order IS '销售订单主表，记录订单的核心信息';
COMMENT ON COLUMN t_order.order_id IS '订单ID，主键';
COMMENT ON COLUMN t_order.order_no IS '订单编号，唯一';
COMMENT ON COLUMN t_order.customer_id IS '客户ID，外键关联客户表';
COMMENT ON COLUMN t_order.order_date IS '订单日期';
COMMENT ON COLUMN t_order.order_amount IS '订单总金额';
COMMENT ON COLUMN t_order.discount_amount IS '优惠金额';
COMMENT ON COLUMN t_order.final_amount IS '最终金额';
COMMENT ON COLUMN t_order.payment_status IS '付款状态';
COMMENT ON COLUMN t_order.delivery_status IS '发货状态';
COMMENT ON COLUMN t_order.order_source IS '订单来源渠道';
COMMENT ON COLUMN t_order.salesman_id IS '业务员ID';
COMMENT ON COLUMN t_order.remark IS '备注';

-- 3. 订单明细表（缺注释）
DROP TABLE IF EXISTS t_order_item CASCADE;
CREATE TABLE t_order_item (
    item_id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES t_order(order_id),
    product_id BIGINT NOT NULL,
    product_name VARCHAR(100),
    spec VARCHAR(100),
    unit VARCHAR(20),
    quantity DECIMAL(10,2) NOT NULL,
    unit_price DECIMAL(15,4) NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    tax_rate DECIMAL(5,4) DEFAULT 0.13,
    tax_amount DECIMAL(15,2),
    delivery_quantity DECIMAL(10,2) DEFAULT 0,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. 产品表（缺注释）
DROP TABLE IF EXISTS t_product CASCADE;
CREATE TABLE t_product (
    product_id BIGSERIAL PRIMARY KEY,
    product_code VARCHAR(30) NOT NULL UNIQUE,
    product_name VARCHAR(100) NOT NULL,
    category_id BIGINT,
    brand VARCHAR(50),
    spec VARCHAR(100),
    unit VARCHAR(20),
    cost_price DECIMAL(15,4),
    sale_price DECIMAL(15,4),
    stock_quantity DECIMAL(10,2) DEFAULT 0,
    reorder_point DECIMAL(10,2) DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. 系统用户表（有注释有枚举值）
DROP TABLE IF EXISTS t_sys_user CASCADE;
CREATE TABLE t_sys_user (
    user_id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(128) NOT NULL,
    real_name VARCHAR(50),
    email VARCHAR(100),
    phone VARCHAR(20),
    dept_id BIGINT,
    user_role VARCHAR(20) NOT NULL,
    user_status VARCHAR(10) NOT NULL DEFAULT 'active',
    login_count INTEGER DEFAULT 0,
    last_login_time TIMESTAMP,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_sys_user IS '系统用户表，管理后台用户信息';
COMMENT ON COLUMN t_sys_user.user_id IS '用户ID，主键';
COMMENT ON COLUMN t_sys_user.username IS '用户名，用于登录';
COMMENT ON COLUMN t_sys_user.password IS '密码，加密存储';
COMMENT ON COLUMN t_sys_user.real_name IS '真实姓名';
COMMENT ON COLUMN t_sys_user.email IS '邮箱';
COMMENT ON COLUMN t_sys_user.phone IS '手机号';
COMMENT ON COLUMN t_sys_user.dept_id IS '部门ID';
COMMENT ON COLUMN t_sys_user.user_role IS '用户角色，包括：admin-管理员、manager-经理、staff-员工、viewer-查看者';
COMMENT ON COLUMN t_sys_user.user_status IS '用户状态，包括：active-启用、inactive-禁用、locked-锁定';

-- 6. 操作日志表（部分有注释，部分字段无注释）
DROP TABLE IF EXISTS t_operation_log CASCADE;
CREATE TABLE t_operation_log (
    log_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    username VARCHAR(50),
    operation_type VARCHAR(20),
    module_name VARCHAR(50),
    description TEXT,
    ip_address VARCHAR(50),
    user_agent TEXT,
    request_method VARCHAR(10),
    request_url VARCHAR(500),
    request_params TEXT,
    response_code VARCHAR(10),
    error_message TEXT,
    execute_time INTEGER,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_operation_log IS '系统操作日志';
COMMENT ON COLUMN t_operation_log.user_id IS '操作用户ID';
COMMENT ON COLUMN t_operation_log.username IS '操作用户名';
COMMENT ON COLUMN t_operation_log.operation_type IS '操作类型';

-- 7. 供应商表（有注释，部分枚举值）
DROP TABLE IF EXISTS t_supplier CASCADE;
CREATE TABLE t_supplier (
    supplier_id BIGSERIAL PRIMARY KEY,
    supplier_code VARCHAR(20) NOT NULL UNIQUE,
    supplier_name VARCHAR(100) NOT NULL,
    supplier_type VARCHAR(20),
    contact_person VARCHAR(50),
    contact_phone VARCHAR(20),
    address TEXT,
    payment_terms VARCHAR(50),
    status VARCHAR(10) NOT NULL DEFAULT 'active',
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_supplier IS '供应商信息表';
COMMENT ON COLUMN t_supplier.supplier_id IS '供应商ID，主键';
COMMENT ON COLUMN t_supplier.supplier_code IS '供应商编码';
COMMENT ON COLUMN t_supplier.supplier_name IS '供应商名称';
COMMENT ON COLUMN t_supplier.supplier_type IS '供应商类型';
COMMENT ON COLUMN t_supplier.payment_terms IS '付款条件，包括：月结30天、月结60天、预付30%';
COMMENT ON COLUMN t_supplier.status IS '状态，包括：active-合作中、inactive-暂停、blacklisted-黑名单';

-- =====================================================
-- 插入测试数据
-- =====================================================

-- 客户表数据
INSERT INTO t_customer (customer_code, customer_name, customer_type, industry, region, status, credit_level, contact_person, contact_phone) VALUES
('C001', '深圳电子科技有限公司', '普通客户', '电子制造', '华南', 'normal', 'AA', '张经理', '13800138001'),
('C002', '上海汽车零部件有限公司', '战略客户', '汽车零部件', '华东', 'normal', 'AAA', '李总', '13800138002'),
('C003', '北京医疗器械集团', '重点客户', '医疗器械', '华北', 'normal', 'AAA', '王经理', '13800138003'),
('C004', '广州工业设备厂', '普通客户', '工业设备', '华南', 'frozen', 'B', '赵工', '13800138004'),
('C005', '成都电子元件厂', '普通客户', '电子制造', '西南', 'cancelled', 'BB', '孙经理', '13800138005');

-- 订单表数据
INSERT INTO t_order (order_no, customer_id, order_date, order_amount, discount_amount, final_amount, payment_status, delivery_status, order_source, salesman_id, remark) VALUES
('ORD20260801001', 1, '2026-08-01', 50000.00, 5000.00, 45000.00, 'paid', 'delivered', '线上商城', 1, '大客户订单'),
('ORD20260802001', 2, '2026-08-02', 120000.00, 0.00, 120000.00, 'paid', 'shipping', '线下销售', 2, '战略客户优先发货'),
('ORD20260803001', 3, '2026-08-03', 80000.00, 8000.00, 72000.00, 'unpaid', 'pending', '展会获客', 1, '展会订单'),
('ORD20260804001', 1, '2026-08-04', 35000.00, 3500.00, 31500.00, 'paid', 'delivered', '老客户介绍', 3, NULL);

-- 订单明细表数据
INSERT INTO t_order_item (order_id, product_id, product_name, spec, unit, quantity, unit_price, amount, tax_rate, tax_amount) VALUES
(1, 1, '精密电阻', '10KΩ ±1%', '个', 10000, 2.50, 25000.00, 0.13, 3250.00),
(1, 2, '贴片电容', '100nF', '个', 20000, 0.80, 16000.00, 0.13, 2080.00),
(1, 3, '连接线束', '12pin', '条', 1000, 9.00, 9000.00, 0.13, 1170.00),
(2, 4, '汽车继电器', '12V 40A', '个', 5000, 18.00, 90000.00, 0.13, 11700.00),
(2, 5, '传感器模块', '温度型', '个', 3000, 10.00, 30000.00, 0.13, 3900.00),
(3, 6, '医疗连接器', 'USB Type-C', '个', 8000, 8.00, 64000.00, 0.13, 8320.00),
(4, 1, '精密电阻', '10KΩ ±1%', '个', 5000, 2.50, 12500.00, 0.13, 1625.00),
(4, 7, '电感线圈', '100uH', '个', 8000, 2.00, 16000.00, 0.13, 2080.00),
(4, 2, '贴片电容', '100nF', '个', 3000, 0.80, 2400.00, 0.13, 312.00);

-- 产品表数据
INSERT INTO t_product (product_code, product_name, category_id, brand, spec, unit, cost_price, sale_price, stock_quantity, reorder_point) VALUES
('P001', '精密电阻', 1, '国巨', '10KΩ ±1%', '个', 1.50, 2.50, 50000, 10000),
('P002', '贴片电容', 1, '三星', '100nF', '个', 0.50, 0.80, 80000, 20000),
('P003', '连接线束', 2, '莫仕', '12pin', '条', 5.00, 9.00, 5000, 1000),
('P004', '汽车继电器', 3, '泰科', '12V 40A', '个', 12.00, 18.00, 3000, 500),
('P005', '传感器模块', 4, '博世', '温度型', '个', 6.00, 10.00, 2000, 300),
('P006', '医疗连接器', 5, '安费诺', 'USB Type-C', '个', 5.00, 8.00, 10000, 2000),
('P007', '电感线圈', 1, 'TDK', '100uH', '个', 1.20, 2.00, 30000, 5000),
('P008', '二极管', 1, '亿光', '1N4148', '个', 0.05, 0.10, 100000, 20000);

-- 系统用户表数据
INSERT INTO t_sys_user (username, password, real_name, email, phone, dept_id, user_role, user_status, login_count) VALUES
('admin', '$2a$10$dummy_hash_1', '系统管理员', 'admin@company.com', '13900000001', 1, 'admin', 'active', 156),
('manager_zhang', '$2a$10$dummy_hash_2', '张经理', 'zhang@company.com', '13900000002', 2, 'manager', 'active', 89),
('staff_li', '$2a$10$dummy_hash_3', '李员工', 'li@company.com', '13900000003', 3, 'staff', 'active', 234),
('viewer_wang', '$2a$10$dummy_hash_4', '王查看', 'wang@company.com', '13900000004', 4, 'viewer', 'inactive', 12),
('locked_user', '$2a$10$dummy_hash_5', '锁定用户', 'locked@company.com', '13900000005', 3, 'staff', 'locked', 3);

-- 操作日志表数据
INSERT INTO t_operation_log (user_id, username, operation_type, module_name, description, ip_address, request_method, response_code, execute_time) VALUES
(1, 'admin', '登录', '系统登录', '用户登录系统', '192.168.1.100', 'POST', '200', 150),
(1, 'admin', '新增', '客户管理', '新增客户：C006', '192.168.1.100', 'POST', '200', 80),
(2, 'manager_zhang', '查询', '订单管理', '查询订单列表', '192.168.1.101', 'GET', '200', 45),
(2, 'manager_zhang', '修改', '订单管理', '更新订单状态', '192.168.1.101', 'PUT', '200', 60),
(3, 'staff_li', '导出', '报表管理', '导出销售报表', '192.168.1.102', 'POST', '200', 1200),
(1, 'admin', '删除', '产品管理', '删除产品P999', '192.168.1.100', 'DELETE', '404', 30),
(3, 'staff_li', '查询', '客户管理', '查询客户详情', '192.168.1.102', 'GET', '200', 35),
(2, 'manager_zhang', '审批', '订单管理', '审批订单ORD20260803001', '192.168.1.101', 'POST', '200', 90);

-- 供应商表数据
INSERT INTO t_supplier (supplier_code, supplier_name, supplier_type, contact_person, contact_phone, payment_terms, status) VALUES
('S001', '国巨电子（苏州）有限公司', '原材料供应商', '陈经理', '13910001001', '月结30天', 'active'),
('S002', '三星电机（东莞）有限公司', '原材料供应商', '林经理', '13910001002', '月结60天', 'active'),
('S003', '泰科电子（上海）有限公司', '品牌代理', '周经理', '13910001003', '预付30%', 'active'),
('S004', '博世汽车部件（苏州）有限公司', '品牌代理', '吴经理', '13910001004', '月结30天', 'inactive'),
('S005', '已停用供应商A', '原材料供应商', '停用联系人', '13910001005', '月结30天', 'blacklisted');

-- =====================================================
-- 验证数据
-- =====================================================
SELECT 't_customer' as table_name, COUNT(*) as row_count FROM t_customer
UNION ALL SELECT 't_order', COUNT(*) FROM t_order
UNION ALL SELECT 't_order_item', COUNT(*) FROM t_order_item
UNION ALL SELECT 't_product', COUNT(*) FROM t_product
UNION ALL SELECT 't_sys_user', COUNT(*) FROM t_sys_user
UNION ALL SELECT 't_operation_log', COUNT(*) FROM t_operation_log
UNION ALL SELECT 't_supplier', COUNT(*) FROM t_supplier;
