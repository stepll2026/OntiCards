-- ============================================================
-- 测试数据卡片生成的边界情况表
-- 数据库类型：PostgreSQL
-- 创建时间：2026-08-13
-- ============================================================

-- 删除已存在的表（如果需要重新创建）
DROP TABLE IF EXISTS public.t_user_test CASCADE;

-- 先创建地区字典表用于外键（简化版）
DROP TABLE IF EXISTS public.sys_region CASCADE;
CREATE TABLE public.sys_region (
    code VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    level SMALLINT DEFAULT 1
);
INSERT INTO public.sys_region (code, name, level) VALUES
    ('110000', '北京市', 1),
    ('310000', '上海市', 1),
    ('440100', '广州市', 1),
    ('440300', '深圳市', 1),
    ('330100', '杭州市', 1),
    ('510100', '成都市', 1);

-- 创建用户测试表
CREATE TABLE public.t_user_test (
    -- 主键和审计字段
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    is_deleted      SMALLINT DEFAULT 0,

    -- 用户基本信息（部分注释缺失）
    username        VARCHAR(50) NOT NULL UNIQUE,
    nickname        VARCHAR(100),                    -- 注释内容为空的边界情况
    real_name       VARCHAR(100),                   -- 注释缺失
    email           VARCHAR(100),
    phone           VARCHAR(20),                      -- 敏感字段，无注释
    id_card         VARCHAR(18),                     -- 敏感字段，无注释

    -- 密码和安全（敏感字段）
    password_hash   VARCHAR(255) NOT NULL,          -- 密码哈希，无注释（敏感）
    pay_password    VARCHAR(64),                    -- 支付密码，无注释（敏感）
    security_token  VARCHAR(128),                    -- 安全令牌，无注释（敏感）

    -- 地址和位置（部分有注释）
    province        VARCHAR(50),
    city            VARCHAR(50),
    district        VARCHAR(50),                     -- 区县，无注释
    address_detail  TEXT,                           -- 详细地址，无注释

    -- 账户和财务（敏感字段）
    balance         DECIMAL(12,2) DEFAULT 0.00,
    frozen_amount   DECIMAL(12,2) DEFAULT 0.00,    -- 冻结金额，无注释（敏感）
    credit_score    INTEGER DEFAULT 100,             -- 信用评分，无注释

    -- 银行信息（敏感字段）
    bank_card_no    VARCHAR(30),                    -- 银行卡号，无注释（敏感）
    bank_name       VARCHAR(100),                    -- 开户银行，无注释

    -- 用户类型和状态（枚举字段）
    user_type       SMALLINT DEFAULT 1,
    status          SMALLINT DEFAULT 1,
    vip_level       SMALLINT DEFAULT 0,

    -- 统计和计数字段
    login_count     INTEGER DEFAULT 0,
    order_count     INTEGER DEFAULT 0,               -- 订单数量，无注释
    total_amount    DECIMAL(14,2) DEFAULT 0.00,    -- 累计消费，无注释

    -- 日期和时间字段
    birthday        DATE,                           -- 生日（敏感个人信息）
    last_login_time TIMESTAMP,                      -- 最后登录时间，无注释
    vip_expire_date DATE,                          -- VIP到期日期，无注释

    -- 中文拼音命名字段（用于测试字段名推断）
    yonghu_leixing  SMALLINT DEFAULT 1,            -- 用户类型(拼音)
    zhanghu_zhuangtai SMALLINT DEFAULT 1,          -- 账户状态(拼音)
    diqu_bianma     VARCHAR(20),                   -- 地区编码(拼音)

    -- 扩展字段
    extend_data     JSONB,                          -- 扩展数据(JSON)
    description     TEXT,                           -- 用户描述
    remark          TEXT                            -- 备注
);

-- 添加外键约束
ALTER TABLE public.t_user_test
    ADD CONSTRAINT fk_user_province FOREIGN KEY (province) REFERENCES sys_region(code);

-- 添加索引
CREATE INDEX idx_t_user_test_username ON public.t_user_test(username);
CREATE INDEX idx_t_user_test_phone ON public.t_user_test(phone);
CREATE INDEX idx_t_user_test_status ON public.t_user_test(status);
CREATE INDEX idx_t_user_test_created_at ON public.t_user_test(created_at);

-- ============================================================
-- PostgreSQL 使用 COMMENT ON 添加注释
-- ============================================================

-- 表注释
COMMENT ON TABLE public.t_user_test IS '用户信息表，用于记录平台注册用户的基础信息、账户状态和财务数据';

-- 字段注释（注释齐全的字段）
COMMENT ON COLUMN public.t_user_test.id IS '用户ID';
COMMENT ON COLUMN public.t_user_test.created_at IS '创建时间';
COMMENT ON COLUMN public.t_user_test.updated_at IS '更新时间';
COMMENT ON COLUMN public.t_user_test.is_deleted IS '删除标志(0-未删除 1-已删除)';
COMMENT ON COLUMN public.t_user_test.username IS '用户名';
COMMENT ON COLUMN public.t_user_test.email IS '邮箱地址';
COMMENT ON COLUMN public.t_user_test.province IS '省份';
COMMENT ON COLUMN public.t_user_test.city IS '城市';
COMMENT ON COLUMN public.t_user_test.balance IS '账户余额(元)';
COMMENT ON COLUMN public.t_user_test.user_type IS '用户类型(1-普通 2-VIP 3-企业)';
COMMENT ON COLUMN public.t_user_test.status IS '账户状态(0-禁用 1-正常 2-待激活 3-冻结)';
COMMENT ON COLUMN public.t_user_test.vip_level IS 'VIP等级(0-非VIP 1-铜牌 2-银牌 3-金牌 4-钻石)';
COMMENT ON COLUMN public.t_user_test.login_count IS '登录次数';

-- 边界情况：注释内容为空字符串
COMMENT ON COLUMN public.t_user_test.nickname IS '';

-- 边界情况：敏感字段（注释内容应体现脱敏特性）
COMMENT ON COLUMN public.t_user_test.phone IS '手机号(脱敏)';
COMMENT ON COLUMN public.t_user_test.id_card IS '身份证号(脱敏)';
COMMENT ON COLUMN public.t_user_test.password_hash IS '密码(加密)';
COMMENT ON COLUMN public.t_user_test.pay_password IS '支付密码(加密)';
COMMENT ON COLUMN public.t_user_test.security_token IS '安全令牌(脱敏)';
COMMENT ON COLUMN public.t_user_test.frozen_amount IS '冻结金额(脱敏)';
COMMENT ON COLUMN public.t_user_test.bank_card_no IS '银行卡号(脱敏)';
COMMENT ON COLUMN public.t_user_test.birthday IS '生日(脱敏)';

-- 注意：以下字段故意不添加注释（用于测试注释填充）
-- real_name, order_count, total_amount, last_login_time, vip_expire_date
-- district, address_detail, frozen_amount, credit_score, bank_name, extend_data
-- description, remark

-- ============================================================
-- 插入测试数据
-- ============================================================

INSERT INTO public.t_user_test (
    username, nickname, real_name, email, phone, id_card,
    password_hash, pay_password, security_token,
    province, city, district, address_detail,
    balance, frozen_amount, credit_score,
    bank_card_no, bank_name,
    user_type, status, vip_level,
    login_count, order_count, total_amount,
    birthday, last_login_time, vip_expire_date,
    yonghu_leixing, zhanghu_zhuangtai, diqu_bianma,
    description, remark
) VALUES
-- 用户1：普通用户，注释齐全
(
    'zhang_san', '张三', '张三丰', 'zhangsan@163.com', '13812345678', '110101199001011234',
    '$2b$12$abcdefghijklmnopqrstuv', '$2b$10$xyz1234567890abcd', 'tok_abc123xyz789',
    '110000', '北京市', '朝阳区', '建国路88号SOHO现代城',
    5000.00, 100.00, 95,
    '6217000010012345678', '中国工商银行',
    1, 1, 0,
    156, 45, 25800.00,
    '1990-01-01', '2026-08-12 18:30:00', NULL,
    1, 1, '110000',
    '优质活跃用户，购买力强', NULL
),

-- 用户2：VIP用户
(
    'li_si', '李四', '李思思', 'lisi@qq.com', '13987654321', '310101199502023456',
    '$2b$12$bcdefghijklmnopqrstuvw', '$2b$10$yza1234567890abcde', 'tok_def456uvw123',
    '310000', '上海市', '浦东新区', '世纪大道100号',
    25000.50, 500.00, 98,
    '6217000020034567890', '招商银行',
    2, 1, 2,
    523, 128, 156000.00,
    '1995-02-02', '2026-08-13 09:15:00', '2027-08-13',
    2, 1, '310000',
    'VIP银牌用户，消费能力强', '高价值客户'
),

-- 用户3：待激活用户
(
    'wang_wu', '王五', '王武', 'wangwu@gmail.com', '13711112222', '440100199801015678',
    '$2b$12$cdefhijklmnopqrstuvwx', '$2b$10$ab1234567890abcdef', 'tok_ghi789xyz456',
    '440100', '广州市', '天河区', '体育西路123号',
    0.00, 0.00, 80,
    NULL, NULL,
    1, 2, 0,
    1, 0, 0.00,
    '1998-10-10', '2026-08-10 10:00:00', NULL,
    1, 2, '440100',
    '新注册用户，待激活', NULL
),

-- 用户4：禁用用户
(
    'zhao_liu', '赵六', '赵六六', 'zhaoliu@139.com', '13699998888', '440300199003034567',
    '$2b$12$defghijklmnopqrstuvwxy', '$2b$10$bc1234567890abcdefg', 'tok_jkl012mno345',
    '440300', '深圳市', '南山区', '科技园南区A1栋',
    1200.00, 0.00, 60,
    '6217000030056789012', '中国建设银行',
    1, 0, 0,
    89, 12, 5600.00,
    '1990-03-03', '2026-07-20 14:20:00', NULL,
    1, 0, '440300',
    '违规用户，已被禁用', '需要核查'
),

-- 用户5：企业用户
(
    'qian_qi', '钱七', '钱齐齐', 'qianqi@company.com', '13522223333', '330100198805056789',
    '$2b$12$efghijklmnopqrstuvwxyz', '$2b$10$cd1234567890abcdefgh', 'tok_pqr678stu901',
    '330100', '杭州市', '西湖区', '文三路398号东信大厦',
    158888.00, 10000.00, 100,
    '6217000040078901234', '中国农业银行',
    3, 1, 4,
    1205, 356, 2580000.00,
    '1988-05-05', '2026-08-13 08:00:00', '2028-05-05',
    3, 1, '330100',
    '钻石VIP企业客户', '重点维护'
),

-- 用户6：冻结用户
(
    'sun_ba', '孙八', '孙霸天', 'sunba@outlook.com', '13433334444', '510100198706078901',
    '$2b$12$fghijklmnopqrstuvwxyza', '$2b$10$de1234567890abcdefghi', 'tok_vwx234yza567',
    '510100', '成都市', '锦江区', '春熙路IFS国际金融中心',
    3500.00, 2000.00, 45,
    '6217000050090123456', '交通银行',
    1, 3, 0,
    45, 8, 12000.00,
    '1987-06-07', '2026-08-01 11:30:00', NULL,
    1, 3, '510100',
    '账户异常，已被冻结', '待解冻处理'
),

-- 用户7：普通用户，少量数据
(
    'zhou_jiu', '周九', '周久久', 'zhoujiu@sina.com', '13344445555', '110101200001110011',
    '$2b$12$hijklmnopqrstuvwxyzab', '$2b$10$ef1234567890abcdefghij', 'tok_bcd345zef678',
    '110000', '北京市', '海淀区', '中关村大街1号',
    880.50, 0.00, 88,
    NULL, NULL,
    1, 1, 1,
    28, 5, 3200.00,
    '2000-01-11', '2026-08-12 22:00:00', '2026-12-31',
    1, 1, '110000',
    NULL, NULL
),

-- 用户8：VIP金牌用户
(
    'wu_shi', '吴十', '吴十十', 'wushi@dxy.cn', '13255556666', '310101199301014567',
    '$2b$12$ijklmnopqrstuvwxyzabc', '$2b$10$fg1234567890abcdefghijk', 'tok_ghi901jkl234',
    '310000', '上海市', '徐汇区', '漕河泾开发区桂平路700号',
    68000.00, 2000.00, 96,
    '6217000060012345678', '上海银行',
    2, 1, 3,
    892, 245, 890000.00,
    '1993-01-01', '2026-08-13 10:30:00', '2027-01-01',
    2, 1, '310000',
    '金牌VIP用户', NULL
);

-- ============================================================
-- 验证查询
-- ============================================================

-- 验证数据
SELECT
    COUNT(*) as total_count,
    COUNT(DISTINCT username) as unique_username,
    COUNT(phone) as has_phone,
    COUNT(balance) as has_balance,
    COUNT(bank_card_no) as has_bank_card
FROM public.t_user_test;

-- 查看各枚举字段的分布
SELECT 'user_type' as field, user_type as value, COUNT(*) as cnt FROM public.t_user_test GROUP BY user_type
UNION ALL
SELECT 'status' as field, status as value, COUNT(*) as cnt FROM public.t_user_test GROUP BY status
UNION ALL
SELECT 'vip_level' as field, vip_level as value, COUNT(*) as cnt FROM public.t_user_test GROUP BY vip_level
ORDER BY field, value;

-- 查看注释情况
SELECT
    column_name,
    col_description((table_schema || '.' || table_name)::regclass, ordinal_position) as comment
FROM information_schema.columns
WHERE table_name = 't_user_test'
ORDER BY ordinal_position;
