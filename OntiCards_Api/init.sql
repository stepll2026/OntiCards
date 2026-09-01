/*
    【Onticards-数据库初始化脚本】

    注意：
    (1) 若需手动执行，则需要先创建数据库，后再执行
    (2) Line 25 注意改为实际的数据库用户名
*/


-- 启用 uuid-ossp 扩展（必须，有则跳过）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ----------------------------
-- Type structure for call_status_enum
-- ----------------------------
DROP TYPE IF EXISTS "public"."call_status_enum";
CREATE TYPE "public"."call_status_enum" AS ENUM (
  'queued',
  'processing',
  'completed',
  'failed'
);

-- !!!!!!!!!!!!!!!!!!!!!!!!!!!! 【需填成实际数据库用户名】 !!!!!!!!!!!!!!!!!!!!!!!!!!!!
ALTER TYPE "public"."call_status_enum" OWNER TO "postgres";

-- ----------------------------
-- Sequence structure for change_logs_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."change_logs_id_seq";
CREATE SEQUENCE "public"."change_logs_id_seq"
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for datacards_datasource_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."datacards_datasource_id_seq";
CREATE SEQUENCE "public"."datacards_datasource_id_seq"
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Table structure for alembic_version
-- ----------------------------
DROP TABLE IF EXISTS "public"."alembic_version";
CREATE TABLE "public"."alembic_version" (
  "version_num" varchar(32) COLLATE "pg_catalog"."default" NOT NULL
)
;
COMMENT ON TABLE "public"."alembic_version" IS '存储数据库版本迁移记录';

-- ----------------------------
-- Table structure for api_keys
-- ----------------------------
DROP TABLE IF EXISTS "public"."api_keys";
CREATE TABLE "public"."api_keys" (
  "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
  "user_id" uuid NOT NULL,
  "name" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "api_key" varchar(128) COLLATE "pg_catalog"."default" NOT NULL,
  "status" varchar(16) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'active'::character varying,
  "expires_at" timestamptz(6),
  "last_used_at" timestamptz(6),
  "created_at" timestamptz(6) NOT NULL DEFAULT now(),
  "updated_at" timestamptz(6) NOT NULL DEFAULT now(),
  PRIMARY KEY ("id")
);
COMMENT ON COLUMN "public"."api_keys"."id" IS '主键 ID';
COMMENT ON COLUMN "public"."api_keys"."user_id" IS '所属用户 ID';
COMMENT ON COLUMN "public"."api_keys"."name" IS 'Key 名称/备注';
COMMENT ON COLUMN "public"."api_keys"."api_key" IS 'API Key 明文字符串（注意避免在日志中输出）';
COMMENT ON COLUMN "public"."api_keys"."status" IS '状态：active=可用，disabled=已禁用';
COMMENT ON COLUMN "public"."api_keys"."expires_at" IS '过期时间';
COMMENT ON COLUMN "public"."api_keys"."last_used_at" IS '最近一次成功调用接口的时间';
COMMENT ON COLUMN "public"."api_keys"."created_at" IS '创建时间';
COMMENT ON COLUMN "public"."api_keys"."updated_at" IS '更新时间';
COMMENT ON TABLE "public"."api_keys" IS 'api_keys管理表，用于第三方平台（如 Coze / HiAgent）调用聚合检索接口的鉴权';

-- ----------------------------
-- Table structure for change_logs
-- ----------------------------
DROP TABLE IF EXISTS "public"."change_logs";
CREATE TABLE "public"."change_logs" (
  "id" int8 NOT NULL DEFAULT nextval('change_logs_id_seq'::regclass),
  "version" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "title" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "content_md" text COLLATE "pg_catalog"."default" NOT NULL,
  "status" varchar(10) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'hidden'::character varying,
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6) DEFAULT now(),
  PRIMARY KEY ("id")
);
COMMENT ON TABLE "public"."change_logs" IS '存储用户数据源的库表结构';

-- ----------------------------
-- Table structure for datacards_datasource
-- ----------------------------
DROP TABLE IF EXISTS "public"."datacards_datasource";
CREATE TABLE "public"."datacards_datasource" (
  "id" int4 NOT NULL DEFAULT nextval('datacards_datasource_id_seq'::regclass),
  "doc_id" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "w_uuid" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "card_data" text COLLATE "pg_catalog"."default" NOT NULL,
  "created_at" timestamptz(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "user_id" uuid,
  "datasource_id" uuid,
  "table_name" varchar(255) COLLATE "pg_catalog"."default",
  "connect_name" varchar(255) COLLATE "pg_catalog"."default",
  PRIMARY KEY ("id")
);
COMMENT ON COLUMN "public"."datacards_datasource"."id" IS '主键ID';
COMMENT ON COLUMN "public"."datacards_datasource"."doc_id" IS '文档ID';
COMMENT ON COLUMN "public"."datacards_datasource"."w_uuid" IS 'Weaviate UUID';
COMMENT ON COLUMN "public"."datacards_datasource"."card_data" IS '卡片数据(JSON字符串)';
COMMENT ON COLUMN "public"."datacards_datasource"."created_at" IS '创建时间';
COMMENT ON COLUMN "public"."datacards_datasource"."updated_at" IS '修改时间（触发器或应用更新）';
COMMENT ON COLUMN "public"."datacards_datasource"."user_id" IS '用户ID（冗余字段，用于快速查询）';
COMMENT ON COLUMN "public"."datacards_datasource"."datasource_id" IS '数据源ID（冗余字段，用于快速查询）';
COMMENT ON COLUMN "public"."datacards_datasource"."table_name" IS '表名（冗余字段，用于快速查询）';
COMMENT ON COLUMN "public"."datacards_datasource"."connect_name" IS '连接名称（冗余字段，便于显示）';
COMMENT ON TABLE "public"."datacards_datasource" IS '存储数据卡片信息';

-- ----------------------------
-- Table structure for datasource_infos
-- ----------------------------
DROP TABLE IF EXISTS "public"."datasource_infos";
CREATE TABLE "public"."datasource_infos" (
  "user_id" uuid NOT NULL,
  "connect_info" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "connect_info_hash" varchar(64) COLLATE "pg_catalog"."default",
  "connect_name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "table_num" int4 NOT NULL,
  "status" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "db_type" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "database_name" varchar(255) COLLATE "pg_catalog"."default",
  "schema_name" varchar(128) COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) NOT NULL,
  "updated_at" timestamptz(6) NOT NULL,
  "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
  "catalog_type" varchar(32) COLLATE "pg_catalog"."default",
  PRIMARY KEY ("id")
)
;
COMMENT ON COLUMN "public"."datasource_infos"."user_id" IS '用户id';
COMMENT ON COLUMN "public"."datasource_infos"."connect_info" IS '数据源连接信息';
COMMENT ON COLUMN "public"."datasource_infos"."connect_info_hash" IS '连接信息的稳定哈希值（SHA256），用于与user_datasource_schemas表关联匹配';
COMMENT ON COLUMN "public"."datasource_infos"."connect_name" IS '数据源名称';
COMMENT ON COLUMN "public"."datasource_infos"."table_num" IS '数据表数量';
COMMENT ON COLUMN "public"."datasource_infos"."status" IS '数据源状态';
COMMENT ON COLUMN "public"."datasource_infos"."db_type" IS '数据库类型';
COMMENT ON COLUMN "public"."datasource_infos"."database_name" IS '数据库名称';
COMMENT ON COLUMN "public"."datasource_infos"."schema_name" IS '数据源默认 schema（PostgreSQL/MSSQL/Trino/Oracle 生效；MySQL可为空或等同database_name）';
COMMENT ON COLUMN "public"."datasource_infos"."created_at" IS '创建时间';
COMMENT ON COLUMN "public"."datasource_infos"."updated_at" IS '更新时间';
COMMENT ON COLUMN "public"."datasource_infos"."id" IS '主键';
COMMENT ON COLUMN "public"."datasource_infos"."catalog_type" IS 'Trino catalog 类型（如 mysql、postgresql），仅 Trino 数据源需要';
COMMENT ON TABLE "public"."datasource_infos" IS '存储数据卡片的来源信息';

-- 添加约束
ALTER TABLE datasource_infos ADD CONSTRAINT uq_user_connect_name UNIQUE (user_id, connect_name);

-- 为 connect_info_hash 添加索引（用于快速关联查询）
CREATE INDEX IF NOT EXISTS idx_datasource_infos_connect_info_hash ON "public"."datasource_infos"("connect_info_hash");

-- ----------------------------
-- Table structure for field_mapping
-- ----------------------------
DROP TABLE IF EXISTS "public"."field_mapping";
CREATE TABLE "public"."field_mapping" (
  "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
  "datasource_id" uuid NOT NULL,
  "schema_hash" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "source_table" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "source_column" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "source_type" varchar(255) COLLATE "pg_catalog"."default",
  "target_table" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "target_column" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "target_type" varchar(255) COLLATE "pg_catalog"."default",
  "mapping_type" varchar(32) COLLATE "pg_catalog"."default" NOT NULL,
  "confidence" numeric(5,4) NOT NULL,
  "mapping_basis" jsonb,
  "created_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "source_job_id" uuid
)
;
COMMENT ON COLUMN "public"."field_mapping"."id" IS '主键ID';
COMMENT ON COLUMN "public"."field_mapping"."datasource_id" IS '数据源ID';
COMMENT ON COLUMN "public"."field_mapping"."schema_hash" IS 'Schema哈希值，用于标识数据源的特定版本';
COMMENT ON COLUMN "public"."field_mapping"."source_job_id" IS '来源任务ID（定向盘点时记录job_id）';
COMMENT ON COLUMN "public"."field_mapping"."source_table" IS '源表名';
COMMENT ON COLUMN "public"."field_mapping"."source_column" IS '源字段名';
COMMENT ON COLUMN "public"."field_mapping"."source_type" IS '源字段类型';
COMMENT ON COLUMN "public"."field_mapping"."target_table" IS '目标表名（参考表）';
COMMENT ON COLUMN "public"."field_mapping"."target_column" IS '目标字段名（参考字段）';
COMMENT ON COLUMN "public"."field_mapping"."target_type" IS '目标字段类型';
COMMENT ON COLUMN "public"."field_mapping"."mapping_type" IS '映射类型：exact_match=精确匹配, semantic_match=语义匹配, fuzzy_match=模糊匹配';
COMMENT ON COLUMN "public"."field_mapping"."confidence" IS '映射置信度，取值范围0~1，值越大表示映射越可靠';
COMMENT ON COLUMN "public"."field_mapping"."mapping_basis" IS '映射依据（JSON格式），记录name_similarity、value_profile、llm_judgment等评分依据';
COMMENT ON COLUMN "public"."field_mapping"."created_at" IS '创建时间';
COMMENT ON COLUMN "public"."field_mapping"."updated_at" IS '更新时间';
COMMENT ON TABLE "public"."field_mapping" IS '字段映射表，记录字段级别的语义映射关系';

-- ----------------------------
-- Table structure for target_inventory_job
-- ----------------------------
DROP TABLE IF EXISTS "public"."target_inventory_job";
CREATE TABLE "public"."target_inventory_job" (
  "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
  "user_id" uuid NOT NULL,
  "datasource_id" uuid NOT NULL,
  "schema_hash" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "target_tables" jsonb NOT NULL,
  "ref_tables" jsonb,
  "dict_file_id" varchar(255) COLLATE "pg_catalog"."default",
  "options" jsonb,
  "status" varchar(32) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'queued'::character varying,
  "progress" jsonb,
  "error_msg" text COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY ("id")
);
COMMENT ON COLUMN "public"."target_inventory_job"."id" IS '任务ID，主键';
COMMENT ON COLUMN "public"."target_inventory_job"."user_id" IS '用户ID';
COMMENT ON COLUMN "public"."target_inventory_job"."datasource_id" IS '数据源ID';
COMMENT ON COLUMN "public"."target_inventory_job"."schema_hash" IS 'Schema哈希值，用于标识数据源结构版本';
COMMENT ON COLUMN "public"."target_inventory_job"."target_tables" IS '目标表列表（JSON数组）';
COMMENT ON COLUMN "public"."target_inventory_job"."ref_tables" IS '参考表列表（JSON数组）';
COMMENT ON COLUMN "public"."target_inventory_job"."dict_file_id" IS '字典文件ID';
COMMENT ON COLUMN "public"."target_inventory_job"."options" IS '任务配置选项（JSON对象）';
COMMENT ON COLUMN "public"."target_inventory_job"."status" IS '任务状态：queued=排队中, processing=处理中, completed=已完成, failed=失败';
COMMENT ON COLUMN "public"."target_inventory_job"."progress" IS '任务进度信息（JSON对象）';
COMMENT ON COLUMN "public"."target_inventory_job"."error_msg" IS '错误信息';
COMMENT ON COLUMN "public"."target_inventory_job"."created_at" IS '创建时间';
COMMENT ON COLUMN "public"."target_inventory_job"."updated_at" IS '更新时间';
COMMENT ON TABLE "public"."target_inventory_job" IS '全域盘点任务表';

-- ----------------------------
-- Table structure for target_inventory_job_result
-- ----------------------------
DROP TABLE IF EXISTS "public"."target_inventory_job_result";
CREATE TABLE "public"."target_inventory_job_result" (
  "job_id" uuid NOT NULL,
  "field_profiles_json" jsonb,
  "candidates_json" jsonb,
  "llm_json" jsonb,
  "confirm_json" jsonb,
  "index_meta_json" jsonb,
  "field_mappings_json" jsonb,
  "table_relationships_json" jsonb,
  "relationship_cards_json" jsonb,
  "created_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY ("job_id")
);
COMMENT ON COLUMN "public"."target_inventory_job_result"."job_id" IS '任务ID，关联 target_inventory_job.id';
COMMENT ON COLUMN "public"."target_inventory_job_result"."field_profiles_json" IS '字段画像结果（JSON对象）';
COMMENT ON COLUMN "public"."target_inventory_job_result"."candidates_json" IS '候选注释结果（JSON对象）';
COMMENT ON COLUMN "public"."target_inventory_job_result"."llm_json" IS 'LLM裁决结果（JSON对象）';
COMMENT ON COLUMN "public"."target_inventory_job_result"."confirm_json" IS '用户确认结果（JSON对象）';
COMMENT ON COLUMN "public"."target_inventory_job_result"."index_meta_json" IS '索引元数据（JSON对象）';
COMMENT ON COLUMN "public"."target_inventory_job_result"."field_mappings_json" IS '字段映射结果（JSON对象）';
COMMENT ON COLUMN "public"."target_inventory_job_result"."table_relationships_json" IS '表关系结果（JSON对象）';
COMMENT ON COLUMN "public"."target_inventory_job_result"."relationship_cards_json" IS '关系卡片结果（JSON对象）';
COMMENT ON COLUMN "public"."target_inventory_job_result"."created_at" IS '创建时间';
COMMENT ON COLUMN "public"."target_inventory_job_result"."updated_at" IS '更新时间';
COMMENT ON TABLE "public"."target_inventory_job_result" IS '全域盘点任务结果表';

-- ----------------------------
-- Table structure for model_config
-- ----------------------------
DROP TABLE IF EXISTS "public"."model_config";
CREATE TABLE "public"."model_config" (
  "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
  "model_name" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "model_type" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "model_api_key" varchar COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "model_class" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "url" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  PRIMARY KEY ("id")
);
COMMENT ON COLUMN "public"."model_config"."id" IS '模型id';
COMMENT ON COLUMN "public"."model_config"."model_name" IS '模型名称';
COMMENT ON COLUMN "public"."model_config"."model_type" IS '模型类型（豆包、千问、DS，用户可自定义）';
COMMENT ON COLUMN "public"."model_config"."model_api_key" IS '模型apikey';
COMMENT ON COLUMN "public"."model_config"."created_at" IS '創建時間';
COMMENT ON COLUMN "public"."model_config"."updated_at" IS '更新時間';
COMMENT ON COLUMN "public"."model_config"."model_class" IS '模型作用类别（大语言、重排序、向量化嵌入）';
COMMENT ON COLUMN "public"."model_config"."url" IS '模型接口url';
COMMENT ON TABLE "public"."model_config" IS '存储模型配置信息';

-- ----------------------------
-- Table structure for prompt_config
-- ----------------------------
DROP TABLE IF EXISTS "public"."prompt_config";
CREATE TABLE "public"."prompt_config" (
  "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
  "prompt" text COLLATE "pg_catalog"."default" NOT NULL,
  "file_name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default",
  "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY ("id")
);
COMMENT ON COLUMN "public"."prompt_config"."id" IS 'prompt_config，主键，自动生成';
COMMENT ON COLUMN "public"."prompt_config"."prompt" IS '提示词实际内容';
COMMENT ON COLUMN "public"."prompt_config"."file_name" IS '映射项目目录中的实际文件名';
COMMENT ON COLUMN "public"."prompt_config"."description" IS '提示词作用描述';
COMMENT ON COLUMN "public"."prompt_config"."created_at" IS '创建时间';
COMMENT ON COLUMN "public"."prompt_config"."updated_at" IS '更新时间';
COMMENT ON TABLE "public"."prompt_config" IS '存储相关的提示词配置信息';

-- ============================================================
-- 一步到位：直接创建“最终结构”的两张表（字段/注释/索引/主键/唯一约束全齐）
-- 适用：PostgreSQL
-- 注意：本脚本会 DROP 后重建（不做旧表迁移）
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================
-- 1) table_relationship（最终结构）
-- ============================
DROP TABLE IF EXISTS "public"."table_relationship";

CREATE TABLE "public"."table_relationship" (
  "id" uuid NOT NULL DEFAULT uuid_generate_v4(),

  "table_a" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "table_b" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,

  "relationship_type" varchar(32) COLLATE "pg_catalog"."default" NOT NULL,
  "join_conditions" jsonb NOT NULL,
  "relationship_strength" numeric(5,4) NOT NULL,
  "cardinality" varchar(32) COLLATE "pg_catalog"."default",

  "created_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,

  "table_a_datasource_id" uuid NOT NULL,
  "table_b_datasource_id" uuid NOT NULL,
  "is_cross_source" bool NOT NULL DEFAULT false,

  "table_a_schema_hash" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "table_b_schema_hash" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,

  -- 新增：来源维度（最终结构内直接包含）
  "source_type" varchar(32) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'global_inventory',
  "source_job_id" uuid NULL,

  -- 数据治理报告关联信息
  -- 来源标识：source_type='governance' 时，governance_report_id 指向治理报告
  "governance_report_id" uuid NULL,
  "governance_job_id" uuid NULL
);

-- 表/列注释
COMMENT ON TABLE "public"."table_relationship" IS '表关系表，记录表与表之间的关联关系（关系图谱中的边，支持同源和跨源）';

COMMENT ON COLUMN "public"."table_relationship"."id" IS '主键ID';
COMMENT ON COLUMN "public"."table_relationship"."table_a" IS '关联表A的表名';
COMMENT ON COLUMN "public"."table_relationship"."table_b" IS '关联表B的表名';
COMMENT ON COLUMN "public"."table_relationship"."relationship_type" IS '关系类型：FK=主外键关联, Semantic=语义关联, Value=值域关联, Composite=复合关联';
COMMENT ON COLUMN "public"."table_relationship"."join_conditions" IS 'JOIN条件（JSON数组），每个元素包含local_field、remote_field、confidence、mapping_type等信息';
COMMENT ON COLUMN "public"."table_relationship"."relationship_strength" IS '关系强度，取值范围0~1，综合评估关系的可信度';
COMMENT ON COLUMN "public"."table_relationship"."cardinality" IS '基数/关联方向：one_to_one=一对一, one_to_many=一对多, many_to_many=多对多';
COMMENT ON COLUMN "public"."table_relationship"."created_at" IS '创建时间';
COMMENT ON COLUMN "public"."table_relationship"."updated_at" IS '更新时间';
COMMENT ON COLUMN "public"."table_relationship"."table_a_datasource_id" IS '表A所属数据源ID';
COMMENT ON COLUMN "public"."table_relationship"."table_b_datasource_id" IS '表B所属数据源ID';
COMMENT ON COLUMN "public"."table_relationship"."is_cross_source" IS '是否跨源关系';
COMMENT ON COLUMN "public"."table_relationship"."table_a_schema_hash" IS '表A的Schema哈希值';
COMMENT ON COLUMN "public"."table_relationship"."table_b_schema_hash" IS '表B的Schema哈希值';
COMMENT ON COLUMN "public"."table_relationship"."source_type" IS '数据来源类型：global_inventory=全域盘点, target_inventory=定向盘点';
COMMENT ON COLUMN "public"."table_relationship"."source_job_id" IS '来源任务ID（定向盘点时记录job_id，全域盘点时为NULL）';
COMMENT ON COLUMN "public"."table_relationship"."governance_report_id" IS '关联的治理报告ID（仅 source_type=governance 时有值）';
COMMENT ON COLUMN "public"."table_relationship"."governance_job_id" IS '治理任务ID（用于区分同一报告的多次执行）';

-- 主键
ALTER TABLE "public"."table_relationship"
  ADD CONSTRAINT "table_relationship_pkey" PRIMARY KEY ("id");

-- 唯一约束（最终版：包含 source_job_id）
ALTER TABLE "public"."table_relationship"
  ADD CONSTRAINT "uq_table_relationship_pair"
  UNIQUE (
    "table_a_datasource_id", "table_a_schema_hash", "table_a",
    "table_b_datasource_id", "table_b_schema_hash", "table_b",
    "source_job_id"
  );

-- 索引（保留原有 + 新增 source 复合索引）
CREATE INDEX "idx_table_relationship_is_cross_source" ON "public"."table_relationship" USING btree (
  "is_cross_source" "pg_catalog"."bool_ops" ASC NULLS LAST
);

CREATE INDEX "idx_table_relationship_table_a" ON "public"."table_relationship" USING btree (
  "table_a" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
COMMENT ON INDEX "public"."idx_table_relationship_table_a" IS '按表A查询关系的索引';

CREATE INDEX "idx_table_relationship_table_a_ds" ON "public"."table_relationship" USING btree (
  "table_a_datasource_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

CREATE INDEX "idx_table_relationship_table_b" ON "public"."table_relationship" USING btree (
  "table_b" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
COMMENT ON INDEX "public"."idx_table_relationship_table_b" IS '按表B查询关系的索引';

CREATE INDEX "idx_table_relationship_table_b_ds" ON "public"."table_relationship" USING btree (
  "table_b_datasource_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

CREATE INDEX "idx_table_relationship_source" ON "public"."table_relationship" USING btree (
  "source_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "source_job_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);


-- ============================
-- 2) table_relationship_card（最终结构）
-- ============================
DROP TABLE IF EXISTS "public"."table_relationship_card";

CREATE TABLE "public"."table_relationship_card" (
  "id" uuid NOT NULL DEFAULT uuid_generate_v4(),

  "datasource_id" uuid NOT NULL,
  "table_name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,

  "card_data" jsonb NOT NULL,
  "w_uuid" varchar(255) COLLATE "pg_catalog"."default",
  "version" int4 DEFAULT 1,

  "created_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,

  "datasource_ids" jsonb,
  "has_cross_source_relations" bool NOT NULL DEFAULT false,
  "schema_hash" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "related_datasource_ids" jsonb,

  -- 新增：来源维度（最终结构内直接包含）
  "source_type" varchar(32) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'global_inventory',
  "source_job_id" uuid NULL,

  -- 数据治理报告关联信息
  -- 来源标识：source_type='governance' 时，governance_report_id 指向治理报告
  "governance_report_id" uuid NULL,
  "governance_job_id" uuid NULL
);

-- 表/列注释
COMMENT ON TABLE "public"."table_relationship_card" IS '表关系卡片表，存储每张表的关系元数据卡片（支持同源和跨源）';

COMMENT ON COLUMN "public"."table_relationship_card"."id" IS '主键ID';
COMMENT ON COLUMN "public"."table_relationship_card"."datasource_id" IS '数据源ID';
COMMENT ON COLUMN "public"."table_relationship_card"."table_name" IS '表名';
COMMENT ON COLUMN "public"."table_relationship_card"."card_data" IS '关系卡片数据（JSON格式），包含该表与其他的所有关联关系信息';
COMMENT ON COLUMN "public"."table_relationship_card"."w_uuid" IS 'Weaviate向量索引UUID，用于向量检索';
COMMENT ON COLUMN "public"."table_relationship_card"."version" IS '卡片版本号，支持版本管理和回滚';
COMMENT ON COLUMN "public"."table_relationship_card"."created_at" IS '创建时间';
COMMENT ON COLUMN "public"."table_relationship_card"."updated_at" IS '更新时间';
COMMENT ON COLUMN "public"."table_relationship_card"."datasource_ids" IS '参与的数据源ID列表（多源时使用，JSON数组）';
COMMENT ON COLUMN "public"."table_relationship_card"."has_cross_source_relations" IS '是否包含跨源关系';
COMMENT ON COLUMN "public"."table_relationship_card"."schema_hash" IS 'Schema哈希值';
COMMENT ON COLUMN "public"."table_relationship_card"."related_datasource_ids" IS '关联的其他数据源ID列表（跨源时使用，JSON数组）';
COMMENT ON COLUMN "public"."table_relationship_card"."source_type" IS '数据来源类型：global_inventory=全域盘点, target_inventory=定向盘点';
COMMENT ON COLUMN "public"."table_relationship_card"."source_job_id" IS '来源任务ID（定向盘点时记录job_id，全域盘点时为NULL）';
COMMENT ON COLUMN "public"."table_relationship_card"."governance_report_id" IS '关联的治理报告ID（仅 source_type=governance 时有值）';
COMMENT ON COLUMN "public"."table_relationship_card"."governance_job_id" IS '治理任务ID（用于区分同一报告的多次执行）';

-- 主键
ALTER TABLE "public"."table_relationship_card"
  ADD CONSTRAINT "table_relationship_card_pkey" PRIMARY KEY ("id");

-- 唯一约束（最终版：包含 source_job_id）
ALTER TABLE "public"."table_relationship_card"
  ADD CONSTRAINT "uq_table_relationship_card_datasource_table"
  UNIQUE ("datasource_id", "schema_hash", "table_name", "source_job_id");

-- 索引（保留原有 + 新增 source 复合索引）
CREATE INDEX "idx_table_relationship_card_datasource" ON "public"."table_relationship_card" USING btree (
  "datasource_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
COMMENT ON INDEX "public"."idx_table_relationship_card_datasource" IS '按数据源查询卡片的索引';

CREATE INDEX "idx_table_relationship_card_has_cross_source" ON "public"."table_relationship_card" USING btree (
  "has_cross_source_relations" "pg_catalog"."bool_ops" ASC NULLS LAST
);

CREATE INDEX "idx_table_relationship_card_w_uuid" ON "public"."table_relationship_card" USING btree (
  "w_uuid" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
COMMENT ON INDEX "public"."idx_table_relationship_card_w_uuid" IS '按Weaviate UUID查询的索引，用于向量检索关联';

CREATE INDEX "idx_table_relationship_card_source" ON "public"."table_relationship_card" USING btree (
  "source_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "source_job_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Table structure for user_datasource_schemas
-- ----------------------------
DROP TABLE IF EXISTS "public"."user_datasource_schemas";
CREATE TABLE "public"."user_datasource_schemas" (
  "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
  "user_id" uuid NOT NULL,
  "db_type" varchar(32) COLLATE "pg_catalog"."default" NOT NULL,
  "connect_info" varchar(2048) COLLATE "pg_catalog"."default" NOT NULL,
  "connect_info_hash" varchar(64) COLLATE "pg_catalog"."default",
  "database_name" varchar(256) COLLATE "pg_catalog"."default" NOT NULL,
  "schema_text" text COLLATE "pg_catalog"."default" NOT NULL,
  "created_at" timestamptz(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "table_name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "db_version" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "connect_name" varchar(2048) COLLATE "pg_catalog"."default" NOT NULL,
  "is_filled" bool,
  "filled_data" text COLLATE "pg_catalog"."default",
  "catalog_type" varchar(32) COLLATE "pg_catalog"."default",
  "is_view" bool,
  "view_name" varchar(255) COLLATE "pg_catalog"."default",
  "schema_name" varchar(128) COLLATE "pg_catalog"."default",
  PRIMARY KEY ("id")
);
COMMENT ON COLUMN "public"."user_datasource_schemas"."id" IS '记录ID，主键，自增UUID';
COMMENT ON COLUMN "public"."user_datasource_schemas"."user_id" IS '用户ID（UUID）';
COMMENT ON COLUMN "public"."user_datasource_schemas"."db_type" IS '数据库类型，如 oracle / postgres / mysql 等';
COMMENT ON COLUMN "public"."user_datasource_schemas"."connect_info" IS '数据库连接信息（建议脱敏或加密后保存）';
COMMENT ON COLUMN "public"."user_datasource_schemas"."connect_info_hash" IS '连接信息的稳定哈希值（SHA256），用于匹配和去重';
COMMENT ON COLUMN "public"."user_datasource_schemas"."database_name" IS '数据库名 / schema 名';
COMMENT ON COLUMN "public"."user_datasource_schemas"."schema_text" IS '表结构信息（文本，建议存JSON字符串）';
COMMENT ON COLUMN "public"."user_datasource_schemas"."created_at" IS '创建时间';
COMMENT ON COLUMN "public"."user_datasource_schemas"."updated_at" IS '更新时间（可在应用层按需更新）';
COMMENT ON COLUMN "public"."user_datasource_schemas"."table_name" IS '数据库表名';
COMMENT ON COLUMN "public"."user_datasource_schemas"."db_version" IS '数据库版本信息';
COMMENT ON COLUMN "public"."user_datasource_schemas"."connect_name" IS '数据源名称';
COMMENT ON COLUMN "public"."user_datasource_schemas"."is_filled" IS '字段描述是否经过LLM填充';
COMMENT ON COLUMN "public"."user_datasource_schemas"."filled_data" IS 'LLM填充结果';
COMMENT ON COLUMN "public"."user_datasource_schemas"."catalog_type" IS 'Trino catalog 类型（如 mysql、postgresql），仅 Trino 数据源需要';
COMMENT ON COLUMN "public"."user_datasource_schemas"."is_view" IS '是否为视图（true=视图，false=普通表）';
COMMENT ON COLUMN "public"."user_datasource_schemas"."view_name" IS '视图名称（若 is_view=true，则记录视图名）';
COMMENT ON COLUMN "public"."user_datasource_schemas"."schema_name" IS '数据源 schema 名（PG/MSSQL/Trino/Oracle 用于去重和关联；MySQL/SQLite 可空）';
COMMENT ON TABLE "public"."user_datasource_schemas" IS '存储用户数据源下的库表结构';

-- 为 connect_info_hash 添加索引（用于快速查询）
CREATE INDEX IF NOT EXISTS idx_user_datasource_schemas_connect_info_hash ON "public"."user_datasource_schemas"("connect_info_hash");

-- ----------------------------
-- Table structure for user_groups
-- ----------------------------
DROP TABLE IF EXISTS "public"."user_groups";
CREATE TABLE "public"."user_groups" (
  "group_id" uuid NOT NULL DEFAULT uuid_generate_v4(),
  "creator_user_id" uuid,
  "group_name" varchar(32) COLLATE "pg_catalog"."default",
  "description" text COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON COLUMN "public"."user_groups"."group_id" IS 'ID';
COMMENT ON COLUMN "public"."user_groups"."creator_user_id" IS '用户id';
COMMENT ON COLUMN "public"."user_groups"."group_name" IS '名称';
COMMENT ON COLUMN "public"."user_groups"."description" IS '用户组描述';
COMMENT ON COLUMN "public"."user_groups"."created_at" IS '創建時間';
COMMENT ON COLUMN "public"."user_groups"."updated_at" IS '更新時間';
COMMENT ON TABLE "public"."user_groups" IS '存储用户组信息';

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS "public"."users";
CREATE TABLE "public"."users" (
  "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
  "user_group_id" uuid,
  "username" varchar(32) COLLATE "pg_catalog"."default",
  "nickname" varchar(32) COLLATE "pg_catalog"."default",
  "email" varchar(128) COLLATE "pg_catalog"."default",
  "password" varchar(128) COLLATE "pg_catalog"."default",
  "password_salt" varchar(32) COLLATE "pg_catalog"."default",
  "avatar" varchar(255) COLLATE "pg_catalog"."default",
  "weaviate_class_name" varchar(128) COLLATE "pg_catalog"."default",
  "status" varchar(32) COLLATE "pg_catalog"."default",
  "role" varchar(32) COLLATE "pg_catalog"."default",
  "last_login" timestamptz(6),
  "password_reset_at" timestamptz(6),
  "created_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "idp_user_id" varchar(128) COLLATE "pg_catalog"."default",
  "idp_source" varchar(64) COLLATE "pg_catalog"."default",
  PRIMARY KEY ("id")
);
COMMENT ON COLUMN "public"."users"."id" IS 'ID';
COMMENT ON COLUMN "public"."users"."user_group_id" IS '用户组id';
COMMENT ON COLUMN "public"."users"."username" IS '用户名（邮箱、账号等唯一标识）';
COMMENT ON COLUMN "public"."users"."nickname" IS '昵称';
COMMENT ON COLUMN "public"."users"."email" IS '邮箱';
COMMENT ON COLUMN "public"."users"."password" IS '密码';
COMMENT ON COLUMN "public"."users"."password_salt" IS '密码盐';
COMMENT ON COLUMN "public"."users"."avatar" IS '头像';
COMMENT ON COLUMN "public"."users"."status" IS '状态：normal、disabled';
COMMENT ON COLUMN "public"."users"."role" IS '角色：normal、admin';
COMMENT ON COLUMN "public"."users"."last_login" IS '登录时间 utc';
COMMENT ON COLUMN "public"."users"."password_reset_at" IS '密码重置时间';
COMMENT ON COLUMN "public"."users"."created_at" IS '創建時間';
COMMENT ON COLUMN "public"."users"."updated_at" IS '更新時間';
COMMENT ON COLUMN "public"."users"."idp_user_id" IS '第三方用户ID（SSO来源）';
COMMENT ON COLUMN "public"."users"."idp_source" IS '第三方来源标识（如企业A）';
COMMENT ON TABLE "public"."users" IS '存储用户数据';

-- =============================================
-- query_logs 表（查询历史明细）
-- =============================================
CREATE TABLE query_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    api_key_id UUID,
    question TEXT NOT NULL,
    sql TEXT,
    datasource_ids JSONB,
    datasource_names JSONB,
    table_names JSONB,
    total_duration_ms INTEGER,
    vector_search_ms INTEGER,
    rerank_ms INTEGER,
    llm_gen_sql_ms INTEGER,
    sql_execution_ms INTEGER,
    fusion_ms INTEGER,
    embedding_tokens INTEGER DEFAULT 0,
    rerank_tokens INTEGER DEFAULT 0,
    llm_prompt_tokens INTEGER DEFAULT 0,
    llm_completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    result_count INTEGER,
    status VARCHAR(32) NOT NULL DEFAULT 'success',
    error_message TEXT,
    fusion_strategy VARCHAR(32),
    cards_recalled INTEGER DEFAULT 0,
    cards_reranked INTEGER DEFAULT 0,
    cards_selected INTEGER DEFAULT 0,
    top1_rerank_score FLOAT,
    avg_rerank_score FLOAT,
    full_response_result JSONB,
    source_datasource_ids JSONB,
    source_datasource_names JSONB,
    -- 多数据源 SQL 数组（新增）
    cluster_sqls JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- 1. 新增字段：实际用于检索/生成SQL的问题（术语展开后）
    processed_question TEXT,
    -- 2. 新增字段：术语展开详情
    term_rewrite_info JSONB
);

CREATE INDEX ix_query_logs_user_id ON query_logs(user_id);
CREATE INDEX ix_query_logs_status ON query_logs(status);
CREATE INDEX ix_query_logs_created_at ON query_logs(created_at);
CREATE INDEX idx_query_logs_user_created ON query_logs(user_id, created_at);
CREATE INDEX idx_query_logs_user_status ON query_logs(user_id, status);
-- GIN索引：支持按来源数据源筛选查询历史
CREATE INDEX idx_query_logs_source_datasource_ids ON query_logs USING GIN (source_datasource_ids);

-- query_logs 表注释
COMMENT ON TABLE query_logs IS '查询历史明细表 - 记录每次用户查询的完整信息，用于审计、分析和监控';

-- query_logs 列注释
COMMENT ON COLUMN query_logs.id IS '主键ID';
COMMENT ON COLUMN query_logs.user_id IS '用户ID';
COMMENT ON COLUMN query_logs.api_key_id IS 'API Key ID（如果通过API调用则记录）';
COMMENT ON COLUMN query_logs.question IS '用户原始问题（术语展开前）';
COMMENT ON COLUMN query_logs.sql IS '生成的SQL语句';
COMMENT ON COLUMN query_logs.datasource_ids IS '涉及的数据源ID列表，查询过程中涉及到的所有数据源';
COMMENT ON COLUMN query_logs.datasource_names IS '涉及的数据源名称列表（冗余，便于展示）';
COMMENT ON COLUMN query_logs.table_names IS '涉及的表名列表';
COMMENT ON COLUMN query_logs.source_datasource_ids IS '查询来源数据源ID列表，表示用户发起查询时选中的数据源';
COMMENT ON COLUMN query_logs.source_datasource_names IS '查询来源数据源名称列表（冗余，便于展示）';
COMMENT ON COLUMN query_logs.total_duration_ms IS '总耗时（毫秒）';
COMMENT ON COLUMN query_logs.vector_search_ms IS '向量检索耗时（毫秒）';
COMMENT ON COLUMN query_logs.rerank_ms IS '重排序耗时（毫秒）';
COMMENT ON COLUMN query_logs.llm_gen_sql_ms IS 'LLM生成SQL耗时（毫秒）';
COMMENT ON COLUMN query_logs.sql_execution_ms IS 'SQL执行耗时（毫秒）';
COMMENT ON COLUMN query_logs.fusion_ms IS '跨库融合耗时（毫秒）';
COMMENT ON COLUMN query_logs.embedding_tokens IS 'Embedding Token数';
COMMENT ON COLUMN query_logs.rerank_tokens IS 'Rerank Token数';
COMMENT ON COLUMN query_logs.llm_prompt_tokens IS 'LLM Prompt Token数（输入）';
COMMENT ON COLUMN query_logs.llm_completion_tokens IS 'LLM Completion Token数（输出）';
COMMENT ON COLUMN query_logs.total_tokens IS '总Token数';
COMMENT ON COLUMN query_logs.result_count IS '返回行数';
COMMENT ON COLUMN query_logs.status IS '查询状态：success/error/timeout';
COMMENT ON COLUMN query_logs.error_message IS '错误信息（如果失败）';
COMMENT ON COLUMN query_logs.fusion_strategy IS '融合策略：AND/OR/UNION/PRIORITY/NONE';
COMMENT ON COLUMN query_logs.cards_recalled IS '向量召回卡片数';
COMMENT ON COLUMN query_logs.cards_reranked IS '重排序后卡片数';
COMMENT ON COLUMN query_logs.cards_selected IS '最终选择卡片数';
COMMENT ON COLUMN query_logs.top1_rerank_score IS 'Top1卡片的重排序分数';
COMMENT ON COLUMN query_logs.avg_rerank_score IS '选中卡片的平均重排序分数';
COMMENT ON COLUMN query_logs.full_response_result IS '完整接口返回结果（JSON格式，用于回放/分析）';
COMMENT ON COLUMN query_logs.cluster_sqls IS '各数据源/簇的SQL数组，用于多数据源查询时记录各簇SQL';
COMMENT ON COLUMN query_logs.created_at IS '查询发起时间';
COMMENT ON COLUMN query_logs.processed_question IS '实际用于检索/生成SQL的问题（术语展开后），如果未进行术语展开则为空';
COMMENT ON COLUMN query_logs.term_rewrite_info IS '术语展开详情，结构为：{"enabled": true/false, "matched_count": 数量, "matched_terms": [...], "rewritten_question": "转写后的问题"},如果未进行术语展开则为空{}';

-- =============================================
-- query_stats_daily 表（监控统计）
-- =============================================
CREATE TABLE query_stats_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    stat_date DATE NOT NULL,
    total_queries INTEGER DEFAULT 0,
    success_queries INTEGER DEFAULT 0,
    error_queries INTEGER DEFAULT 0,
    timeout_queries INTEGER DEFAULT 0,
    total_embedding_tokens BIGINT DEFAULT 0,
    total_rerank_tokens BIGINT DEFAULT 0,
    total_llm_tokens BIGINT DEFAULT 0,
    total_tokens BIGINT DEFAULT 0,
    estimated_cost_cents INTEGER DEFAULT 0,
    cost_version VARCHAR(32),
    avg_duration_ms INTEGER,
    min_duration_ms INTEGER,
    max_duration_ms INTEGER,
    avg_vector_search_ms INTEGER,
    avg_rerank_ms INTEGER,
    avg_llm_gen_sql_ms INTEGER,
    avg_sql_execution_ms INTEGER,
    avg_cards_recalled FLOAT,
    avg_cards_selected FLOAT,
    avg_top1_rerank_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_user_stat_date UNIQUE (user_id, stat_date)
);

CREATE INDEX ix_query_stats_daily_user_id ON query_stats_daily(user_id);
CREATE INDEX ix_query_stats_daily_stat_date ON query_stats_daily(stat_date);

-- query_stats_daily 表注释
COMMENT ON TABLE query_stats_daily IS '查询统计表（按天聚合）- 用于监控模块，记录每日用户查询的聚合统计数据';

-- query_stats_daily 列注释
COMMENT ON COLUMN query_stats_daily.id IS '主键ID';
COMMENT ON COLUMN query_stats_daily.user_id IS '用户ID';
COMMENT ON COLUMN query_stats_daily.stat_date IS '统计日期';
COMMENT ON COLUMN query_stats_daily.total_queries IS '总查询次数';
COMMENT ON COLUMN query_stats_daily.success_queries IS '成功次数';
COMMENT ON COLUMN query_stats_daily.error_queries IS '失败次数';
COMMENT ON COLUMN query_stats_daily.timeout_queries IS '超时次数';
COMMENT ON COLUMN query_stats_daily.total_embedding_tokens IS 'Embedding总Token';
COMMENT ON COLUMN query_stats_daily.total_rerank_tokens IS 'Rerank总Token';
COMMENT ON COLUMN query_stats_daily.total_llm_tokens IS 'LLM总Token';
COMMENT ON COLUMN query_stats_daily.total_tokens IS '总Token消耗';
COMMENT ON COLUMN query_stats_daily.estimated_cost_cents IS '预估成本（分），仅供参考，实际费用以账单为准';
COMMENT ON COLUMN query_stats_daily.cost_version IS '价格配置版本号，用于追溯当时的价格配置';
COMMENT ON COLUMN query_stats_daily.avg_duration_ms IS '平均耗时（毫秒）';
COMMENT ON COLUMN query_stats_daily.min_duration_ms IS '最小耗时（毫秒）';
COMMENT ON COLUMN query_stats_daily.max_duration_ms IS '最大耗时（毫秒）';
COMMENT ON COLUMN query_stats_daily.avg_vector_search_ms IS '向量检索平均耗时（毫秒）';
COMMENT ON COLUMN query_stats_daily.avg_rerank_ms IS '重排序平均耗时（毫秒）';
COMMENT ON COLUMN query_stats_daily.avg_llm_gen_sql_ms IS 'LLM生成SQL平均耗时（毫秒）';
COMMENT ON COLUMN query_stats_daily.avg_sql_execution_ms IS 'SQL执行平均耗时（毫秒）';
COMMENT ON COLUMN query_stats_daily.avg_cards_recalled IS '平均召回卡片数';
COMMENT ON COLUMN query_stats_daily.avg_cards_selected IS '平均选择卡片数';
COMMENT ON COLUMN query_stats_daily.avg_top1_rerank_score IS '平均Top1重排序分数';
COMMENT ON COLUMN query_stats_daily.created_at IS '记录创建时间';
COMMENT ON COLUMN query_stats_daily.updated_at IS '记录更新时间';

-- =============================================
-- system_configs 表（系统配置）- 最终版
-- =============================================
CREATE TABLE system_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_key VARCHAR(128) NOT NULL,
    config_value TEXT,
    description VARCHAR(256),
    user_id UUID NULL,                                    -- ← 先不加 UNIQUE
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 表注释
COMMENT ON TABLE system_configs IS '系统配置表 - 存储系统运行时配置参数，支持系统级和用户级配置';

-- 列注释
COMMENT ON COLUMN system_configs.id IS '主键ID';
COMMENT ON COLUMN system_configs.config_key IS '配置键';
COMMENT ON COLUMN system_configs.config_value IS '配置值';
COMMENT ON COLUMN system_configs.description IS '配置描述';
COMMENT ON COLUMN system_configs.user_id IS '所属用户ID（NULL=系统级配置，非NULL=用户级配置）';
COMMENT ON COLUMN system_configs.created_at IS '记录创建时间';
COMMENT ON COLUMN system_configs.updated_at IS '记录更新时间';

-- 添加复合唯一约束
ALTER TABLE system_configs ADD CONSTRAINT uq_config_key_user_id UNIQUE (config_key, user_id);

-- 索引
CREATE INDEX idx_system_configs_user_id ON system_configs(user_id);
CREATE INDEX idx_system_configs_key_user ON system_configs(config_key, user_id);

-- 初始数据
INSERT INTO system_configs (config_key, config_value, description, user_id) VALUES
    ('query_logs_retention_days', '180', '查询日志保留天数', NULL),
    ('stats_retention_days', '365', '聚合统计保留天数', NULL),
    ('token_price_embedding', '0.0005', 'Embedding Token 单价（元/千token）', NULL),
    ('token_price_rerank', '0.0008', 'Rerank Token 单价（元/千token）', NULL),
    ('token_price_llm_input', '0.0024', 'LLM 输入 Token 单价（元/千token）', NULL),
    ('token_price_llm_output', '0.0096', 'LLM 输出 Token 单价（元/千token）', NULL)
ON CONFLICT (config_key, user_id) DO NOTHING;

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."change_logs_id_seq" OWNED BY "public"."change_logs"."id";
SELECT setval('"public"."change_logs_id_seq"', 20, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
SELECT setval('"public"."datacards_datasource_id_seq"', 1, false);

-- ----------------------------
-- Indexes structure for table api_keys
-- ----------------------------
CREATE INDEX "idx_api_keys_status_expires" ON "public"."api_keys" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "expires_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
COMMENT ON INDEX "public"."idx_api_keys_status_expires" IS '按状态和过期时间筛选 API Key 的索引，用于鉴权与清理';
CREATE INDEX "idx_api_keys_user_id" ON "public"."api_keys" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
COMMENT ON INDEX "public"."idx_api_keys_user_id" IS '按用户查询 API Key 的索引，用于管理页面展示';
CREATE UNIQUE INDEX "uq_api_keys_plain" ON "public"."api_keys" USING btree (
  "api_key" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
COMMENT ON INDEX "public"."uq_api_keys_plain" IS '明文唯一索引，用于快速鉴权查询';

-- ----------------------------
-- Primary Key structure for table api_keys
-- (已在 CREATE TABLE 中定义)
-- ----------------------------

-- ----------------------------
-- Indexes structure for table change_logs
-- ----------------------------
CREATE INDEX "idx_change_logs_status" ON "public"."change_logs" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "uq_change_logs_version" ON "public"."change_logs" USING btree (
  "version" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table change_logs
-- (已在 CREATE TABLE 中定义)
--

-- ----------------------------
-- Indexes structure for table datacards_datasource
-- ----------------------------
CREATE INDEX "idx_datacards_datasource_datasource_id" ON "public"."datacards_datasource" USING btree (
  "datasource_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "idx_datacards_datasource_table_name" ON "public"."datacards_datasource" USING btree (
  "table_name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_datacards_datasource_user_id" ON "public"."datacards_datasource" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Indexes structure for table field_mapping
-- ----------------------------
CREATE INDEX "idx_field_mapping_datasource_schema" ON "public"."field_mapping" USING btree (
  "datasource_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "schema_hash" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
COMMENT ON INDEX "public"."idx_field_mapping_datasource_schema" IS '按数据源和Schema查询的复合索引';
CREATE INDEX "idx_field_mapping_source" ON "public"."field_mapping" USING btree (
  "source_table" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "source_column" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
COMMENT ON INDEX "public"."idx_field_mapping_source" IS '按源表和源字段查询的复合索引';
CREATE INDEX "idx_field_mapping_target" ON "public"."field_mapping" USING btree (
  "target_table" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "target_column" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
COMMENT ON INDEX "public"."idx_field_mapping_target" IS '按目标表和目标字段查询的复合索引';
CREATE INDEX "idx_field_mapping_source_job" ON "public"."field_mapping" USING btree (
  "source_job_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
COMMENT ON INDEX "public"."idx_field_mapping_source_job" IS '按来源任务ID查询的索引';

-- ----------------------------
-- Primary Key structure for table field_mapping
-- ----------------------------
ALTER TABLE "public"."field_mapping" ADD CONSTRAINT "field_mapping_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table target_inventory_job
-- ----------------------------
CREATE INDEX "idx_target_inventory_job_datasource_id" ON "public"."target_inventory_job" USING btree (
  "datasource_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "idx_target_inventory_job_status" ON "public"."target_inventory_job" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_target_inventory_job_user_id" ON "public"."target_inventory_job" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table target_inventory_job
-- (已在 CREATE TABLE 中定义)
--

-- Primary Key structure for table target_inventory_job_result
-- (已在 CREATE TABLE 中定义)
--

-- ----------------------------
-- Indexes structure for table user_datasource_schemas
-- ----------------------------
CREATE INDEX "ix_user_datasource_schemas_user_id" ON "public"."user_datasource_schemas" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table user_datasource_schemas
-- ----------------------------
ALTER TABLE "public"."user_datasource_schemas" ADD CONSTRAINT "uq_userid_connectinfo_schema_tablename" UNIQUE ("user_id", "connect_info", "schema_name", "table_name");

-- ----------------------------
-- Indexes for table user_datasource_schemas
-- ----------------------------
CREATE INDEX "idx_uds_user_conninfo_schema" ON "public"."user_datasource_schemas" ("user_id", "connect_info", "schema_name");

-- ----------------------------
-- Primary Key structure for table user_datasource_schemas
-- (已在 CREATE TABLE 中定义)
--

-- ----------------------------
-- Primary Key structure for table user_groups
-- ----------------------------
ALTER TABLE "public"."user_groups" ADD CONSTRAINT "user_group_pkey" PRIMARY KEY ("group_id");

-- ----------------------------
-- Primary Key structure for table users
-- (已在 CREATE TABLE 中定义)
--

-- ----------------------------
-- Indexes structure for table users (SSO fields)
-- ----------------------------
CREATE INDEX "ix_users_idp_user_id" ON "public"."users" USING btree (
  "idp_user_id" "pg_catalog"."text_ops" ASC NULLS LAST
);
COMMENT ON INDEX "public"."ix_users_idp_user_id" IS '按第三方用户ID查询的索引，用于SSO登录';

CREATE INDEX "ix_users_idp_source" ON "public"."users" USING btree (
  "idp_source" "pg_catalog"."text_ops" ASC NULLS LAST
);
COMMENT ON INDEX "public"."ix_users_idp_source" IS '按第三方来源查询的索引，用于SSO登录';

-- ----------------------------
-- Foreign Keys structure for table target_inventory_job_result
-- ----------------------------
ALTER TABLE "public"."target_inventory_job_result" ADD CONSTRAINT "fk_target_inventory_job_result_job" FOREIGN KEY ("job_id") REFERENCES "public"."target_inventory_job" ("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- ============================================================
-- 术语库模块
-- ============================================================

-- ----------------------------
-- Table structure for business_term_libraries（业务术语库表）
-- ----------------------------
DROP TABLE IF EXISTS "public"."business_term_libraries";
CREATE TABLE "public"."business_term_libraries" (
  "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
  "name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default",
  "category" varchar(100) COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'active',
  "created_by" uuid,
  "created_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY ("id")
);

CREATE INDEX "idx_business_term_libraries_status" ON "public"."business_term_libraries" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_business_term_libraries_category" ON "public"."business_term_libraries" USING btree (
  "category" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Table structure for business_terms（业务术语表）
-- ----------------------------
DROP TABLE IF EXISTS "public"."business_terms";
CREATE TABLE "public"."business_terms" (
  "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
  "library_id" uuid NOT NULL,
  "term_name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "term_alias" text COLLATE "pg_catalog"."default",
  "term_definition" text COLLATE "pg_catalog"."default" NOT NULL,
  "applicable_conditions" text COLLATE "pg_catalog"."default",
  "remarks" text COLLATE "pg_catalog"."default",
  "related_datacards" text COLLATE "pg_catalog"."default",
  "related_fields" text COLLATE "pg_catalog"."default",
  "related_terms" text COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'active',
  "created_by" uuid,
  "created_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY ("id")
);
COMMENT ON TABLE "public"."business_terms" IS '业务术语表 - 属于某个术语库，用于NL2SQL查询时的术语识别和展开';
COMMENT ON COLUMN "public"."business_terms"."id" IS '主键ID';
COMMENT ON COLUMN "public"."business_terms"."library_id" IS '关联术语库ID';
COMMENT ON COLUMN "public"."business_terms"."term_name" IS '术语名称';
COMMENT ON COLUMN "public"."business_terms"."term_alias" IS '术语别名（JSON数组，如 ["成交金额", "商品成交总额"]）';
COMMENT ON COLUMN "public"."business_terms"."term_definition" IS '术语定义（包含计算口径）';
COMMENT ON COLUMN "public"."business_terms"."applicable_conditions" IS '适用条件（选填）';
COMMENT ON COLUMN "public"."business_terms"."remarks" IS '备注（选填）';
COMMENT ON COLUMN "public"."business_terms"."related_datacards" IS '关联的数据卡片/表（JSON数组，如 [{"id":"...","name":"orders"}]）';
COMMENT ON COLUMN "public"."business_terms"."related_fields" IS '关联的字段（JSON数组，如 [{"table":"orders","field":"amount"}]）';
COMMENT ON COLUMN "public"."business_terms"."related_terms" IS '关联的其他术语（JSON数组，如 [{"id":"...","name":"客单价"}]）';
COMMENT ON COLUMN "public"."business_terms"."status" IS '状态：active=启用，inactive=禁用';
COMMENT ON COLUMN "public"."business_terms"."created_by" IS '创建人ID';
COMMENT ON COLUMN "public"."business_terms"."created_at" IS '创建时间';
COMMENT ON COLUMN "public"."business_terms"."updated_at" IS '更新时间';

-- UNIQUE constraint for business_terms
ALTER TABLE "public"."business_terms" ADD CONSTRAINT "uq_business_terms_library_term" UNIQUE ("library_id", "term_name");

CREATE INDEX "idx_business_terms_library_id" ON "public"."business_terms" USING btree (
  "library_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "idx_business_terms_status" ON "public"."business_terms" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- 外键约束：术语必须属于某个库
ALTER TABLE "public"."business_terms" ADD CONSTRAINT "fk_business_terms_library"
  FOREIGN KEY ("library_id") REFERENCES "public"."business_term_libraries" ("id")
  ON DELETE CASCADE ON UPDATE CASCADE;

-- ============================================================
-- 数据源-术语库关联表（多对多关系）
-- ============================================================
DROP TABLE IF EXISTS "public"."datasource_term_library";
CREATE TABLE "public"."datasource_term_library" (
  "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
  "datasource_id" uuid NOT NULL,
  "library_id" uuid NOT NULL,
  "is_enabled" boolean NOT NULL DEFAULT true,
  "added_by" uuid,
  "added_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY ("id")
);
COMMENT ON TABLE "public"."datasource_term_library" IS '数据源-术语库关联表 - 建立数据源与术语库的多对多关系，一个数据源可添加多个术语库，一个术语库可被多个数据源引用';
COMMENT ON COLUMN "public"."datasource_term_library"."id" IS '主键ID';
COMMENT ON COLUMN "public"."datasource_term_library"."datasource_id" IS '数据源ID';
COMMENT ON COLUMN "public"."datasource_term_library"."library_id" IS '术语库ID';
COMMENT ON COLUMN "public"."datasource_term_library"."is_enabled" IS '是否启用：true=启用，false=禁用';
COMMENT ON COLUMN "public"."datasource_term_library"."added_by" IS '添加人ID';
COMMENT ON COLUMN "public"."datasource_term_library"."added_at" IS '添加时间';
COMMENT ON COLUMN "public"."datasource_term_library"."updated_at" IS '更新时间';

-- UNIQUE constraint for datasource_term_library
-- 唯一约束：同一数据源不能重复添加同一术语库
ALTER TABLE "public"."datasource_term_library" ADD CONSTRAINT "uq_datasource_library"
  UNIQUE ("datasource_id", "library_id");

-- 索引
CREATE INDEX "idx_datasource_term_library_datasource_id" ON "public"."datasource_term_library" USING btree (
  "datasource_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "idx_datasource_term_library_library_id" ON "public"."datasource_term_library" USING btree (
  "library_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- 外键约束
ALTER TABLE "public"."datasource_term_library" ADD CONSTRAINT "fk_datasource_term_library_library"
  FOREIGN KEY ("library_id") REFERENCES "public"."business_term_libraries" ("id")
  ON DELETE CASCADE ON UPDATE CASCADE;

-- ----------------------------
-- Table structure for business_term_templates（术语模板表）
-- ----------------------------
DROP TABLE IF EXISTS "public"."business_term_templates";
CREATE TABLE "public"."business_term_templates" (
  "id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "category" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "template_name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "term_name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "term_alias" text COLLATE "pg_catalog"."default",
  "term_definition" text COLLATE "pg_catalog"."default" NOT NULL,
  "applicable_conditions" text COLLATE "pg_catalog"."default",
  "remarks" text COLLATE "pg_catalog"."default",
  "source" varchar(100) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'system',
  "created_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY ("id")
);
COMMENT ON TABLE "public"."business_term_templates" IS '业务术语模板表 - 预置行业术语模板，只读不修改，用户可导入到业务术语表';
COMMENT ON COLUMN "public"."business_term_templates"."id" IS '模板术语ID（如 tmpl-er-001）';
COMMENT ON COLUMN "public"."business_term_templates"."category" IS '行业/场景分类（如 电商零售、ERP生产制造）';
COMMENT ON COLUMN "public"."business_term_templates"."template_name" IS '模板名称（如 电商零售-交易类）';
COMMENT ON COLUMN "public"."business_term_templates"."term_name" IS '术语名称';
COMMENT ON COLUMN "public"."business_term_templates"."term_alias" IS '术语别名（JSON数组）';
COMMENT ON COLUMN "public"."business_term_templates"."term_definition" IS '术语定义（包含计算口径）';
COMMENT ON COLUMN "public"."business_term_templates"."applicable_conditions" IS '适用条件（选填）';
COMMENT ON COLUMN "public"."business_term_templates"."remarks" IS '备注（选填）';
COMMENT ON COLUMN "public"."business_term_templates"."source" IS '来源：system=系统预置，custom=用户自定义';
COMMENT ON COLUMN "public"."business_term_templates"."created_at" IS '创建时间';
COMMENT ON COLUMN "public"."business_term_templates"."updated_at" IS '更新时间';

-- UNIQUE constraint for business_term_templates
ALTER TABLE "public"."business_term_templates" ADD CONSTRAINT "uq_business_term_templates_category_term" UNIQUE ("category", "term_name");

CREATE INDEX "idx_business_term_templates_category" ON "public"."business_term_templates" USING btree (
  "category" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_business_term_templates_source" ON "public"."business_term_templates" USING btree (
  "source" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ============================================================
-- 预置术语模板数据初始化 SQL
-- 用于向 business_term_templates 表插入预置数据
-- ============================================================

-- ============================================================
-- 1. 电商零售行业模板（23条）
-- ============================================================

-- 交易类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-er-001', '电商零售', '电商零售-交易类', 'GMV', '["商品成交总额", "成交金额", "成交总额"]', 'GMV（商品成交总额）= 已完成订单的订单金额总和，不包含已退款订单金额，不包含未支付订单，不含税', '仅统计已完成的订单', '电商最核心的指标', 'system', NOW(), NOW()),
('tmpl-er-002', '电商零售', '电商零售-交易类', '净成交额', '["净GMV", "实际成交额"]', '净成交额 = GMV - 退款金额，即剔除退款后的实际成交金额', '统计实际有效交易', '排除退款后反映真实收入', 'system', NOW(), NOW()),
('tmpl-er-003', '电商零售', '电商零售-交易类', '客单价', '["平均客单价", "每客消费金额"]', '客单价 = GMV / 支付订单数，即每一笔支付订单的平均金额', '按自然月或自然周统计', '衡量顾客购买力', 'system', NOW(), NOW()),
('tmpl-er-004', '电商零售', '电商零售-交易类', '退款率', '["退货率", "退款占比"]', '退款率 = 退款订单数 / 支付订单数 × 100%', '仅统计已完成订单', '反映商品质量和服务质量', 'system', NOW(), NOW()),
('tmpl-er-005', '电商零售', '电商零售-交易类', '支付转化率', '["下单转化率", "付款转化率"]', '支付转化率 = 支付订单数 / 下单订单数 × 100%', '从加购到支付全链路', '衡量购买路径顺畅程度', 'system', NOW(), NOW()),
('tmpl-er-006', '电商零售', '电商零售-交易类', '取消订单率', '["订单取消率"]', '取消订单率 = 取消订单数 / 下单订单数 × 100%', '统计周期内', '反映购物车或价格问题', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 用户类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-er-007', '电商零售', '电商零售-用户类', '活跃用户', '["在线用户", "DAU"]', '统计周期内有任意行为的去重用户数，包括浏览、加购、下单、支付等任意操作', '自然日/自然周/自然月', '不包括仅访问未操作的用户', 'system', NOW(), NOW()),
('tmpl-er-008', '电商零售', '电商零售-用户类', '新用户', '["新增用户", "首次用户"]', '首次访问/注册的用户，同一设备或账号仅首次访问时计入', '统计周期内首次', '用于衡量拉新效果', 'system', NOW(), NOW()),
('tmpl-er-009', '电商零售', '电商零售-用户类', '复购用户', '["回头客", "多次购买用户"]', '在统计周期内完成 2 笔及以上支付订单的去重用户数', '统计周期内多次购买', '衡量用户忠诚度', 'system', NOW(), NOW()),
('tmpl-er-010', '电商零售', '电商零售-用户类', '流失用户', '["沉默用户", "流失客"]', '超过指定时间（如90天）没有任何访问或购买行为的用户', '按预设沉默周期', '流失定义可按业务调整', 'system', NOW(), NOW()),
('tmpl-er-011', '电商零售', '电商零售-用户类', '独立访客数', '["UV", "访客数"]', '统计周期内访问的不重复用户数', '全站或指定页面', '按设备或账号去重', 'system', NOW(), NOW()),
('tmpl-er-012', '电商零售', '电商零售-用户类', '潜在流失用户', '["预警用户", "高流失风险用户"]', '连续 30~60 天未访问但超过 60 天内有购买记录的用户', '尚未完全流失', '可通过营销手段召回', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 商品类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-er-013', '电商零售', '电商零售-商品类', 'SKU', '["商品SKU", "库存量单位"]', 'SKU（Stock Keeping Unit）即库存量单位，表示同一个商品下不同规格/颜色的最小库存单元', '按规格维度管理', '区分SPU和SKU', 'system', NOW(), NOW()),
('tmpl-er-014', '电商零售', '电商零售-商品类', '商品点击率', '["CTR", "点击率"]', '商品点击率 = 商品点击量 / 商品曝光量 × 100%', '统计周期内', '衡量商品吸引力', 'system', NOW(), NOW()),
('tmpl-er-015', '电商零售', '电商零售-商品类', '动销率', '["有销售商品占比"]', '动销率 = 有销售记录的SKU数 / 在售SKU总数 × 100%', '统计周期内', '越高说明滞销品越少', 'system', NOW(), NOW()),
('tmpl-er-016', '电商零售', '电商零售-商品类', '爆款', '["热销商品", "明星单品"]', '在统计周期内销量远超平均水平的商品，一般销量排名在前10%', '统计周期内', '也称爆品或大单品', 'system', NOW(), NOW()),
('tmpl-er-017', '电商零售', '电商零售-商品类', '库存周转率', '["存货周转率"]', '库存周转率 = 出库成本 / 平均库存余额，反映库存流动性', '月度/季度/年化', '周转越快说明变现能力越强', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 营销类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-er-018', '电商零售', '电商零售-营销类', '优惠券', '["优惠码", "折扣券"]', '由商家或平台发行的电子凭证，消费者在结算时可抵扣相应金额或享受折扣', '按优惠券类型', '区分满减券、折扣券、兑换券', 'system', NOW(), NOW()),
('tmpl-er-019', '电商零售', '电商零售-营销类', '满减', '["满减活动", "阶梯满减"]', '消费满指定金额后自动减免一定金额的优惠活动，如满100减10', '按活动规则', '可叠加多档满减', 'system', NOW(), NOW()),
('tmpl-er-020', '电商零售', '电商零售-营销类', 'ROI', '["投入产出比"]', 'ROI（Return on Investment）= 活动GMV / 营销费用，反映营销投入的回报效率', '活动维度', '大于1表示盈利', 'system', NOW(), NOW()),
('tmpl-er-021', '电商零售', '电商零售-营销类', '拉新成本', '["获客成本", "新客获取成本"]', '拉取一个新用户所需的平均成本 = 营销费用 / 新用户数', '统计周期内', '越低说明获客效率越高', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 客服售后类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-er-022', '电商零售', '电商零售-客服售后类', '客服响应时长', '["平均响应时间", "响应速度"]', '从用户发起咨询到客服首次回复的平均时长，单位为秒或分钟', '仅统计有效会话', '越短说明响应越及时', 'system', NOW(), NOW()),
('tmpl-er-023', '电商零售', '电商零售-客服售后类', '客服满意度', '["CSAT", "用户满意度"]', '用户对客服服务评价为满意或非常满意的会话数 / 参评会话数 × 100%', '仅统计参评会话', '衡量服务质量', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- ============================================================
-- 2. ERP生产制造行业模板（17条）
-- ============================================================

-- 生产管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-erp-001', 'ERP生产制造', 'ERP生产制造-生产管理类', '在制品', '["WIP", "加工中", "半成品"]', '正在生产过程中、尚未完工的产品，包括已投料但未完成全部工序的产品', '生产过程中', 'Work In Process', 'system', NOW(), NOW()),
('tmpl-erp-002', 'ERP生产制造', 'ERP生产制造-生产管理类', '完工产品', '["产成品", "成品"]', '完成全部生产工序、经检验合格并办理入库手续的产品', '已入库', '与在制品对应', 'system', NOW(), NOW()),
('tmpl-erp-003', 'ERP生产制造', 'ERP生产制造-生产管理类', '工单', '["生产工单", "工作令"]', '根据生产计划下达的生产任务单，载明生产的产品、数量、工艺路线等信息', '按工单维度', '也称生产工单或工作令', 'system', NOW(), NOW()),
('tmpl-erp-004', 'ERP生产制造', 'ERP生产制造-生产管理类', '良品率', '["合格率", "正品率"]', '良品率 = 良品数 / 总产出数 × 100%', '按工单或批次', '衡量生产质量', 'system', NOW(), NOW()),
('tmpl-erp-005', 'ERP生产制造', 'ERP生产制造-生产管理类', '次品率', '["不良率", "不合格率"]', '次品率 = 次品数 / 总产出数 × 100%', '按工单或批次', '与良品率之和为100%', 'system', NOW(), NOW()),
('tmpl-erp-006', 'ERP生产制造', 'ERP生产制造-生产管理类', '生产周期', '["制造周期", "加工周期"]', '从工单开工到完工的日历天数，反映生产效率', '按工单维度', '也称制造前置时间', 'system', NOW(), NOW()),
('tmpl-erp-007', 'ERP生产制造', 'ERP生产制造-生产管理类', '产能利用率', '["设备利用率", "开动率"]', '实际产量 / 产能上限 × 100%', '按产线或设备', '反映产能闲置程度', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 质量管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-erp-008', 'ERP生产制造', 'ERP生产制造-质量管理类', '来料检验', '["IQC", "来料检验"]', '对采购进来的原材料、零部件进行质量检验，确认是否合格方可入库', '按来料批次', 'Incoming Quality Control', 'system', NOW(), NOW()),
('tmpl-erp-009', 'ERP生产制造', 'ERP生产制造-质量管理类', '过程检验', '["IPQC", "制程检验"]', '在生产过程中对各工序进行的质量检验，确保工序品质受控', '按工序维度', 'In-Process Quality Control', 'system', NOW(), NOW()),
('tmpl-erp-010', 'ERP生产制造', 'ERP生产制造-质量管理类', '出货检验', '["OQC", "出库检验"]', '产品完工后、出货前进行的最终质量检验', '按批次或订单', 'Outgoing Quality Control', 'system', NOW(), NOW()),
('tmpl-erp-011', 'ERP生产制造', 'ERP生产制造-质量管理类', '不良品', '["缺陷品", "品质异常"]', '经检验未达到质量标准的产品，包括可返工、报废、让步接收等类型', '按批次或工序', '需要记录不良类型和原因', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 采购仓储类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-erp-012', 'ERP生产制造', 'ERP生产制造-采购仓储类', '料件', '["物料", "原材料"]', '构成产品的各种材料和外购件，包括原材料、辅助材料、外购件等', '按物料类型', 'ERP中的广义物料概念', 'system', NOW(), NOW()),
('tmpl-erp-013', 'ERP生产制造', 'ERP生产制造-采购仓储类', '安全库存', '["最低库存", "保险库存"]', '为防止需求波动或供应延迟而设置的最低库存量，低于此值应触发采购', '按物料维度', '也称最低库存', 'system', NOW(), NOW()),
('tmpl-erp-014', 'ERP生产制造', 'ERP生产制造-采购仓储类', '呆滞物料', '["滞料", "积压物料"]', '长期（通常超过3个月）没有使用或消耗的物料', '按物料维度', '需要及时清理或变卖', 'system', NOW(), NOW()),
('tmpl-erp-015', 'ERP生产制造', 'ERP生产制造-采购仓储类', '来料不良率', '["IQC不良率"]', '来料检验中发现的不良数量 / 来料检验总数 × 100%', '按供应商维度', '评估供应商质量', 'system', NOW(), NOW()),
('tmpl-erp-016', 'ERP生产制造', 'ERP生产制造-采购仓储类', '供应商准时交货率', '["交期准时率", "OTD"]', '按时交货的采购单数量 / 总采购单数量 × 100%', '按供应商维度', 'On Time Delivery', 'system', NOW(), NOW()),
('tmpl-erp-017', 'ERP生产制造', 'ERP生产制造-采购仓储类', '库存周转率', '["存货周转率"]', '库存周转率 = 出库成本 / 平均库存余额，反映库存流动性', '月度/季度/年化', '周转越快说明变现能力越强', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- ============================================================
-- 3. CRM客户管理行业模板（18条）
-- ============================================================

-- 客户运营类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-crm-001', 'CRM客户管理', 'CRM客户管理-客户运营类', '客户总数', '["企业客户数", "总客户数"]', '系统中所有客户实体的累计数量（含已流失客户）', '按时间维度', '区分有效客户和全部客户', 'system', NOW(), NOW()),
('tmpl-crm-002', 'CRM客户管理', 'CRM客户管理-客户运营类', '有效客户数', '["在册客户", "活跃客户"]', '截止当前时间仍有业务往来或服务的客户数量（不含已完全流失客户）', '某个时点', '也称存量客户数', 'system', NOW(), NOW()),
('tmpl-crm-003', 'CRM客户管理', 'CRM客户管理-客户运营类', '新增客户数', '["新签约客户", "新增企业"]', '统计周期内新录入系统并完成首单或首次服务的客户数量', '统计周期内', '衡量客户开发能力', 'system', NOW(), NOW()),
('tmpl-crm-004', 'CRM客户管理', 'CRM客户管理-客户运营类', '流失客户数', '["流失企业", "流失客户"]', '超过预设沉默周期（如90天或180天）没有任何业务接触的客户数量', '统计周期内', '也称流失客户', 'system', NOW(), NOW()),
('tmpl-crm-005', 'CRM客户管理', 'CRM客户管理-客户运营类', '客户流失率', '["流失率", "企业流失率"]', '流失客户数 / 期初有效客户数 × 100%', '统计周期内', '越低说明客户粘性越好', 'system', NOW(), NOW()),
('tmpl-crm-006', 'CRM客户管理', 'CRM客户管理-客户运营类', '客户复购率', '["复购率", "重复购买率"]', '产生2次及以上购买行为的客户数 / 有购买行为的客户总数 × 100%', '统计周期内', '衡量客户忠诚度', 'system', NOW(), NOW()),
('tmpl-crm-007', 'CRM客户管理', 'CRM客户管理-客户运营类', '客户生命周期', '["LTV", "生命价值周期"]', '一个客户从首次购买到最终流失所产生的全部价值，通常以金额或时间为单位', '按客户维度', 'Lifetime Value', 'system', NOW(), NOW()),
('tmpl-crm-008', 'CRM客户管理', 'CRM客户管理-客户运营类', '客户等级', '["客户分级", "客户分层"]', '按客户的贡献值、规模、潜力等维度对客户进行分级，如A/B/C级或VIP/普通', '按分级标准', '用于差异化服务策略', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 销售管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-crm-009', 'CRM客户管理', 'CRM客户管理-销售管理类', '线索', '["销售线索", "Leads"]', '潜在客户的初步信息，包括联系方式、公司名称等，通常未经验证', '按线索维度', '也称潜在客户或线索', 'system', NOW(), NOW()),
('tmpl-crm-010', 'CRM客户管理', 'CRM客户管理-销售管理类', '商机', '["销售商机", "Opportunity"]', '销售人员在跟进过程中识别出的有明确购买意向的潜在业务', '按商机维度', '也称销售机会或OP', 'system', NOW(), NOW()),
('tmpl-crm-011', 'CRM客户管理', 'CRM客户管理-销售管理类', '商机转化率', '["商机赢单率"]', '成交的商机数量 / 跟进中的商机总数 × 100%', '统计周期内', '衡量销售转化能力', 'system', NOW(), NOW()),
('tmpl-crm-012', 'CRM客户管理', 'CRM客户管理-销售管理类', '销售周期', '["销售时长", "成交周期"]', '从商机创建到最终成交的日历天数', '按商机维度', '反映销售效率', 'system', NOW(), NOW()),
('tmpl-crm-013', 'CRM客户管理', 'CRM客户管理-销售管理类', '完成率', '["目标完成率", "达成率"]', '实际完成金额 / 销售目标 × 100%', '按周期维度', '衡量目标达成程度', 'system', NOW(), NOW()),
('tmpl-crm-014', 'CRM客户管理', 'CRM客户管理-销售管理类', '赢单金额', '["签约金额", "合同金额"]', '成功签约的订单总金额', '按签约周期', '也称签约金额', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 服务支持类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-crm-015', 'CRM客户管理', 'CRM客户管理-服务支持类', '服务工单', '["工单", "Service Request"]', '客户提交的服务请求或问题单据，记录服务内容和处理过程', '按工单维度', '也称服务请求或客服工单', 'system', NOW(), NOW()),
('tmpl-crm-016', 'CRM客户管理', 'CRM客户管理-服务支持类', '平均处理时长', '["平均解决时长", "响应时长"]', '从工单创建到关闭的平均时长，单位为小时或天', '按工单维度', '衡量服务效率', 'system', NOW(), NOW()),
('tmpl-crm-017', 'CRM客户管理', 'CRM客户管理-服务支持类', '服务满意度', '["服务评分", "CSAT"]', '客户对服务结果或态度的评价得分，通常1-5分', '按工单维度', '衡量服务质量', 'system', NOW(), NOW()),
('tmpl-crm-018', 'CRM客户管理', 'CRM客户管理-服务支持类', '问题解决率', '["解决率", "工单解决率"]', '成功关闭（已解决）的工单数量 / 总工单数量 × 100%', '统计周期内', '不包括处理中的工单', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- ============================================================
-- 4. 财务管理行业模板（21条）
-- ============================================================

-- 收入利润类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-fin-001', '财务管理', '财务管理-收入利润类', '营业收入', '["销售收入", "销售总额"]', '企业从主营业务中获得的收入，按权责发生制确认', '按月/季度/年', '不含营业外收入', 'system', NOW(), NOW()),
('tmpl-fin-002', '财务管理', '财务管理-收入利润类', '营业成本', '["销售成本", "主营业务成本"]', '为取得营业收入而发生的直接成本，如原材料、人工、制造费用等', '按月/季度/年', '与营业收入配比', 'system', NOW(), NOW()),
('tmpl-fin-003', '财务管理', '财务管理-收入利润类', '毛利', '["毛利润", "销售毛利"]', '毛利 = 营业收入 - 营业成本，反映主营业务的直接盈利能力', '按月/季度/年', '不扣除期间费用', 'system', NOW(), NOW()),
('tmpl-fin-004', '财务管理', '财务管理-收入利润类', '毛利率', '["毛利率"]', '毛利率 = 毛利 / 营业收入 × 100%', '按月/季度/年', '衡量主营业务的盈利空间', 'system', NOW(), NOW()),
('tmpl-fin-005', '财务管理', '财务管理-收入利润类', '净利润', '["税后利润", "净收益"]', '净利润 = 营业利润 + 营业外收入 - 营业外支出 - 所得税', '按月/季度/年', '最终可分配给股东的利润', 'system', NOW(), NOW()),
('tmpl-fin-006', '财务管理', '财务管理-收入利润类', '净利率', '["净利率"]', '净利率 = 净利润 / 营业收入 × 100%', '按月/季度/年', '衡量最终盈利水平', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 费用成本类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-fin-007', '财务管理', '财务管理-费用成本类', '销售费用', '["营销费用", "营业费用"]', '为销售产品或提供劳务而发生的费用，包括广告费、推销费、销售人员薪酬等', '按月/季度/年', '与管理费用区分', 'system', NOW(), NOW()),
('tmpl-fin-008', '财务管理', '财务管理-费用成本类', '管理费用', '["期间费用", "管理成本"]', '企业行政管理部门为组织和管理生产经营活动而发生的费用', '按月/季度/年', '包括管理人员薪酬、办公费等', 'system', NOW(), NOW()),
('tmpl-fin-009', '财务管理', '财务管理-费用成本类', '研发费用', '["R&D费用", "研究开发费"]', '为获得新技术、新产品而进行的研究开发活动所发生的费用', '按月/季度/年', 'Research & Development', 'system', NOW(), NOW()),
('tmpl-fin-010', '财务管理', '财务管理-费用成本类', '财务费用', '["融资成本", "利息费用"]', '企业为筹集生产经营所需资金而发生的费用，包括利息支出、汇兑损失、金融机构手续费等', '按月/季度/年', '银行存款利息收入冲减', 'system', NOW(), NOW()),
('tmpl-fin-011', '财务管理', '财务管理-费用成本类', '成本收入比', '["成本收入比率"]', '成本总额 / 营业收入 × 100%', '按机构或业务维度', '衡量经营效率，越低越好', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 资产负债类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-fin-012', '财务管理', '财务管理-资产负债类', '资产负债率', '["负债率"]', '资产负债率 = 总负债 / 总资产 × 100%', '某个时点', '衡量企业负债水平，越低越稳健', 'system', NOW(), NOW()),
('tmpl-fin-013', '财务管理', '财务管理-资产负债类', '应收账款周转率', '["应收周转率"]', '应收账款周转率 = 营业收入 / 平均应收账款余额，反映回款速度', '按年或季度', '越高说明回款越快', 'system', NOW(), NOW()),
('tmpl-fin-014', '财务管理', '财务管理-资产负债类', '应收账款周转天数', '["DSO", "应收天数"]', '应收账款周转天数 = 365 / 应收账款周转率，反映回款周期', '按年或季度', 'Days Sales Outstanding', 'system', NOW(), NOW()),
('tmpl-fin-015', '财务管理', '财务管理-资产负债类', '存货周转率', '["库存周转率"]', '存货周转率 = 营业成本 / 平均存货余额，反映库存流动性', '按年或季度', '越高说明流动性越好', 'system', NOW(), NOW()),
('tmpl-fin-016', '财务管理', '财务管理-资产负债类', '存货周转天数', '["库存天数"]', '存货周转天数 = 365 / 存货周转率，反映库存平均持有天数', '按年或季度', '越短说明变现能力越强', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 预算现金流类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-fin-017', '财务管理', '财务管理-预算现金流类', '预算执行率', '["预算达成率"]', '实际发生金额 / 预算金额 × 100%', '按预算项维度', '反映预算管控效果', 'system', NOW(), NOW()),
('tmpl-fin-018', '财务管理', '财务管理-预算现金流类', '经营性现金流', '["经营现金流"]', '企业日常经营活动产生的现金流量，如销售收款、采购付款、支付工资等', '按月/季度/年', '反映主业造血能力', 'system', NOW(), NOW()),
('tmpl-fin-019', '财务管理', '财务管理-预算现金流类', '现金净流量', '["净现金流"]', '现金流入 - 现金流出，正数表示现金增加，负数表示现金减少', '按月/季度/年', '衡量现金收支平衡', 'system', NOW(), NOW()),
('tmpl-fin-020', '财务管理', '财务管理-预算现金流类', '回款率', '["回款比例", "收款率"]', '实际回款金额 / 应收款总额 × 100%', '按客户或周期', '衡量回款效率', 'system', NOW(), NOW()),
('tmpl-fin-021', '财务管理', '财务管理-预算现金流类', '账龄', '["账龄分析"]', '应收账款或应付账款从发生到当前的时间分布，通常按0-30/31-60/61-90/>90天分段', '按账龄区间', '用于坏账准备计提', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- ============================================================
-- 5. 供应链物流行业模板（20条）
-- ============================================================

-- 仓储管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-sc-001', '供应链物流', '供应链物流-仓储管理类', '入库量', '["入库数量", "进货量"]', '统计周期内货物进入仓库的累计数量', '按仓库或物料维度', '区分采购入库和生产入库', 'system', NOW(), NOW()),
('tmpl-sc-002', '供应链物流', '供应链物流-仓储管理类', '出库量', '["出库数量", "发货量"]', '统计周期内货物从仓库发出的累计数量', '按仓库或物料维度', '用于销售出库和生产领料', 'system', NOW(), NOW()),
('tmpl-sc-003', '供应链物流', '供应链物流-仓储管理类', '库存量', '["现有库存", "在库量"]', '某个时点仓库中实际存放的物料或商品数量', '按仓库或物料维度', '需要定期盘点核对', 'system', NOW(), NOW()),
('tmpl-sc-004', '供应链物流', '供应链物流-仓储管理类', '库存周转率', '["存货周转率"]', '库存周转率 = 出库成本 / 平均库存余额，反映库存流动性', '月度/季度/年', '周转越快资金效率越高', 'system', NOW(), NOW()),
('tmpl-sc-005', '供应链物流', '供应链物流-仓储管理类', '安全库存', '["最低库存", "保险库存"]', '为防止需求波动或供应延迟而设置的最低库存量', '按物料维度', '低于此值需紧急补货', 'system', NOW(), NOW()),
('tmpl-sc-006', '供应链物流', '供应链物流-仓储管理类', '库存准确率', '["账实相符率"]', '账面库存与实际盘点相符的物料数量 / 总物料数量 × 100%', '按盘点维度', '越接近100%说明管理越精准', 'system', NOW(), NOW()),
('tmpl-sc-007', '供应链物流', '供应链物流-仓储管理类', '拣货效率', '["拣货速度", "拣货产出"]', '每小时拣选的订单行数或件数', '按仓库或人员维度', '衡量仓库作业效率', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 运输配送类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-sc-008', '供应链物流', '供应链物流-运输配送类', '发货量', '["出货量", "发货单量"]', '统计周期内从仓库发出的订单或货物数量', '按仓库或渠道维度', '区分订单数和件数', 'system', NOW(), NOW()),
('tmpl-sc-009', '供应链物流', '供应链物流-运输配送类', '配送时效', '["配送时长", "送货时间"]', '从订单发货到客户签收的日历天数或小时数', '按订单维度', '客户体验关键指标', 'system', NOW(), NOW()),
('tmpl-sc-010', '供应链物流', '供应链物流-运输配送类', '准时到达率', '["准时率", "交期达成率"]', '按约定时间准时到达的配送单数 / 总配送单数 × 100%', '按承运商或区域', '衡量配送可靠性', 'system', NOW(), NOW()),
('tmpl-sc-011', '供应链物流', '供应链物流-运输配送类', '运输破损率', '["破损率", "货损率"]', '运输过程中发生破损的货物数量 / 总运输货物数量 × 100%', '按承运商维度', '衡量运输质量', 'system', NOW(), NOW()),
('tmpl-sc-012', '供应链物流', '供应链物流-运输配送类', '满载率', '["装载率", "车辆满载率"]', '实际装载重量或体积 / 车辆最大装载能力 × 100%', '按车次维度', '衡量车辆利用效率', 'system', NOW(), NOW()),
('tmpl-sc-013', '供应链物流', '供应链物流-运输配送类', '末端配送', '["最后一公里", "落地配"]', '从配送站点到最终客户手中的配送环节', '按配送阶段', 'Last Mile，影响成本最大', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 供应商管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-sc-014', '供应链物流', '供应链物流-供应商管理类', '准时交货率', '["交期达成率", "OTD"]', '按时交货的采购单数量 / 总采购单数量 × 100%', '按供应商维度', 'On Time Delivery', 'system', NOW(), NOW()),
('tmpl-sc-015', '供应链物流', '供应链物流-供应商管理类', '来料合格率', '["IQC合格率", "来料品质率"]', '来料检验合格的数量 / 来料检验总数 × 100%', '按供应商维度', '衡量来料质量', 'system', NOW(), NOW()),
('tmpl-sc-016', '供应链物流', '供应链物流-供应商管理类', '供应商集中度', '["采购集中度", "供应商占比"]', '对某一供应商的采购金额 / 总采购金额 × 100%', '按供应商维度', '过高存在供应风险', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 供应链绩效类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-sc-017', '供应链物流', '供应链物流-供应链绩效类', '缺货率', '["缺货占比", "断货率"]', '发生缺货的SKU或订单数 / 总SKU或订单数 × 100%', '按物料或订单维度', '越低说明供应保障越好', 'system', NOW(), NOW()),
('tmpl-sc-018', '供应链物流', '供应链物流-供应链绩效类', '供应链响应时间', '["响应时长", "供应链前置时间"]', '从收到订单到货物送达客户手中的完整时间', '按订单维度', '越短说明供应链越敏捷', 'system', NOW(), NOW()),
('tmpl-sc-019', '供应链物流', '供应链物流-供应链绩效类', '预测准确率', '["预测精度", "Forecast Accuracy"]', '预测需求与实际需求的匹配程度，通常取1减去MAPE', '按物料维度', '越接近100%越好', 'system', NOW(), NOW()),
('tmpl-sc-020', '供应链物流', '供应链物流-供应链绩效类', '安全库存覆盖率', '["库存保障天数"]', '当前库存量按历史消耗速度可支撑的天数', '按物料维度', '低于安全库存天数需补货', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- ============================================================
-- 6. 教育行业模板（18条）
-- ============================================================

-- 招生管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-edu-001', '教育', '教育-招生管理类', '招生人数', '["新生人数", "录取人数"]', '统计周期内成功报名并缴费的新生数量', '按学期或学年', '区分报名人数和实际入学人数', 'system', NOW(), NOW()),
('tmpl-edu-002', '教育', '教育-招生管理类', '报名转化率', '["入学转化率", "报名成功率"]', '实际缴费入学人数 / 报名咨询人数 × 100%', '按招生周期', '衡量招生效率', 'system', NOW(), NOW()),
('tmpl-edu-003', '教育', '教育-招生管理类', '招生成本', '["获客成本", "单个学员成本"]', '招生总费用 / 招生人数，即获取一个新学员的平均成本', '按招生渠道', '越低说明招生效率越高', 'system', NOW(), NOW()),
('tmpl-edu-004', '教育', '教育-招生管理类', '满班率', '["班级满员率", "开班率"]', '实际招生人数 / 计划招生人数 × 100%', '按班级或课程', '反映课程受欢迎程度', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 教学管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-edu-005', '教育', '教育-教学管理类', '在校生', '["在读学员", "在籍学生"]', '当前在校学习的学生总数，不含已毕业或退学学生', '某个时点', '也称在籍学生数', 'system', NOW(), NOW()),
('tmpl-edu-006', '教育', '教育-教学管理类', '出勤率', '["到课率", "上课率"]', '实际出勤人次 / 应出勤人次 × 100%', '按班级或课程', '衡量学生学习积极性', 'system', NOW(), NOW()),
('tmpl-edu-007', '教育', '教育-教学管理类', '课程完成率', '["课程结课率", "完课率"]', '完成全部课时的学员数 / 报名学员数 × 100%', '按课程维度', '反映课程吸引力和学员坚持度', 'system', NOW(), NOW()),
('tmpl-edu-008', '教育', '教育-教学管理类', '平均成绩', '["班级均分", "平均分"]', '班级或课程所有学员成绩的算术平均值', '按班级或考试', '衡量整体教学效果', 'system', NOW(), NOW()),
('tmpl-edu-009', '教育', '教育-教学管理类', '及格率', '["通过率", "合格率"]', '成绩达到及格线的学员数 / 参考学员总数 × 100%', '按考试或课程', '反映教学质量', 'system', NOW(), NOW()),
('tmpl-edu-010', '教育', '教育-教学管理类', '优秀率', '["优秀学员占比"]', '成绩达到优秀标准的学员数 / 参考学员总数 × 100%', '按考试或课程', '衡量高水平学员比例', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 学员运营类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-edu-011', '教育', '教育-学员运营类', '续费率', '["续班率", "续报率"]', '课程结束后继续报名下一期课程的学员数 / 上期学员总数 × 100%', '按课程周期', '衡量学员满意度和忠诚度', 'system', NOW(), NOW()),
('tmpl-edu-012', '教育', '教育-学员运营类', '退费率', '["退课率", "退学率"]', '申请退费的学员数 / 报名学员总数 × 100%', '统计周期内', '反映课程质量和服务问题', 'system', NOW(), NOW()),
('tmpl-edu-013', '教育', '教育-学员运营类', '流失率', '["学员流失率", "退学率"]', '未续费或退学的学员数 / 期初学员总数 × 100%', '按学期或学年', '越低说明学员粘性越好', 'system', NOW(), NOW()),
('tmpl-edu-014', '教育', '教育-学员运营类', '转介绍率', '["推荐率", "口碑转化率"]', '通过老学员推荐而来的新学员数 / 新学员总数 × 100%', '按招生周期', '反映口碑和满意度', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 教师管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-edu-015', '教育', '教育-教师管理类', '师生比', '["教师学生比"]', '教师总数 / 在校生总数，反映师资配置情况', '某个时点', '越低说明师资越充足', 'system', NOW(), NOW()),
('tmpl-edu-016', '教育', '教育-教师管理类', '教师满意度', '["教师评分", "教学评价"]', '学员对教师教学质量的评价得分，通常1-5分或百分制', '按教师或课程', '衡量教学质量', 'system', NOW(), NOW()),
('tmpl-edu-017', '教育', '教育-教师管理类', '课时利用率', '["教师产能利用率"]', '实际授课课时 / 可授课课时 × 100%', '按教师维度', '衡量教师工作饱和度', 'system', NOW(), NOW()),
('tmpl-edu-018', '教育', '教育-教师管理类', '教师流失率', '["离职率"]', '离职教师数 / 期初教师总数 × 100%', '按年或季度', '反映教师稳定性', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- ============================================================
-- 7. 医疗健康行业模板（16条）
-- ============================================================

-- 门诊管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-med-001', '医疗健康', '医疗健康-门诊管理类', '门诊量', '["门诊人次", "就诊量"]', '统计周期内到门诊就诊的患者人次数', '按日/周/月统计', '区分人次和人数', 'system', NOW(), NOW()),
('tmpl-med-002', '医疗健康', '医疗健康-门诊管理类', '平均候诊时长', '["等待时间", "候诊时间"]', '从患者挂号到医生接诊的平均等待时间，单位为分钟', '按科室或时段', '衡量就诊效率', 'system', NOW(), NOW()),
('tmpl-med-003', '医疗健康', '医疗健康-门诊管理类', '平均就诊时长', '["诊疗时长", "接诊时间"]', '医生为每位患者提供诊疗服务的平均时长，单位为分钟', '按科室或医生', '反映诊疗质量', 'system', NOW(), NOW()),
('tmpl-med-004', '医疗健康', '医疗健康-门诊管理类', '复诊率', '["回诊率", "再诊率"]', '再次就诊的患者数 / 首诊患者数 × 100%', '统计周期内', '反映患者信任度和疾病管理需求', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 住院管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-med-005', '医疗健康', '医疗健康-住院管理类', '床位使用率', '["床位占用率", "病床使用率"]', '实际占用床日数 / 实际开放床日数 × 100%', '按科室或医院', '衡量床位资源利用效率', 'system', NOW(), NOW()),
('tmpl-med-006', '医疗健康', '医疗健康-住院管理类', '平均住院日', '["住院天数", "平均住院时长"]', '出院患者住院总天数 / 出院患者总数', '按科室或病种', '反映医疗效率和疾病严重程度', 'system', NOW(), NOW()),
('tmpl-med-007', '医疗健康', '医疗健康-住院管理类', '床位周转率', '["床位周转次数"]', '出院患者数 / 平均开放床位数', '按月或年统计', '越高说明床位利用越充分', 'system', NOW(), NOW()),
('tmpl-med-008', '医疗健康', '医疗健康-住院管理类', '入院人数', '["住院人数", "收治人数"]', '统计周期内办理入院手续的患者数量', '按科室或医院', '衡量收治能力', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 医疗质量类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-med-009', '医疗健康', '医疗健康-医疗质量类', '治愈率', '["治愈好转率", "治疗成功率"]', '治愈或好转的患者数 / 出院患者总数 × 100%', '按科室或病种', '衡量医疗效果', 'system', NOW(), NOW()),
('tmpl-med-010', '医疗健康', '医疗健康-医疗质量类', '手术成功率', '["手术治愈率"]', '手术成功的患者数 / 手术总数 × 100%', '按手术类型', '反映手术质量', 'system', NOW(), NOW()),
('tmpl-med-011', '医疗健康', '医疗健康-医疗质量类', '院内感染率', '["医院感染率", "HAI"]', '发生院内感染的患者数 / 住院患者总数 × 100%', '按科室或医院', 'Healthcare-Associated Infection', 'system', NOW(), NOW()),
('tmpl-med-012', '医疗健康', '医疗健康-医疗质量类', '患者满意度', '["就医满意度", "服务评分"]', '患者对医疗服务的满意度评分,通常1-5分或百分制', '按科室或医院', '衡量服务质量', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 药品耗材类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-med-013', '医疗健康', '医疗健康-药品耗材类', '药占比', '["药品费用占比"]', '药品费用 / 医疗总收入 × 100%', '按科室或医院', '国家有控制指标要求', 'system', NOW(), NOW()),
('tmpl-med-014', '医疗健康', '医疗健康-药品耗材类', '耗材占比', '["耗材费用占比"]', '医用耗材费用 / 医疗总收入 × 100%', '按科室或医院', '反映耗材使用情况', 'system', NOW(), NOW()),
('tmpl-med-015', '医疗健康', '医疗健康-药品耗材类', '抗菌药物使用率', '["抗生素使用率"]', '使用抗菌药物的患者数 / 总患者数 × 100%', '按科室或医院', '国家有严格监管要求', 'system', NOW(), NOW()),
('tmpl-med-016', '医疗健康', '医疗健康-药品耗材类', '药品库存周转率', '["药品周转率"]', '药品出库成本 / 平均药品库存 × 100%', '按月或季度', '反映药品库存管理效率', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- ============================================================
-- 8. 人力资源行业模板（15条）
-- ============================================================

-- 招聘管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-hr-001', '人力资源', '人力资源-招聘管理类', '招聘周期', '["招聘时长", "平均招聘天数"]', '从发布职位到候选人入职的平均日历天数', '按岗位或部门', '越短说明招聘效率越高', 'system', NOW(), NOW()),
('tmpl-hr-002', '人力资源', '人力资源-招聘管理类', 'Offer接受率', '["录用接受率", "Offer通过率"]', '接受Offer的候选人数 / 发出Offer总数 × 100%', '按岗位或渠道', '反映薪酬竞争力和雇主品牌', 'system', NOW(), NOW()),
('tmpl-hr-003', '人力资源', '人力资源-招聘管理类', '招聘完成率', '["招聘达成率", "HC完成率"]', '实际入职人数 / 计划招聘人数 × 100%', '按周期或部门', 'HC = Headcount', 'system', NOW(), NOW()),
('tmpl-hr-004', '人力资源', '人力资源-招聘管理类', '招聘成本', '["单人招聘成本", "人均招聘费用"]', '招聘总费用 / 实际入职人数', '按渠道或岗位', '包括广告费、猎头费、差旅费等', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 员工管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-hr-005', '人力资源', '人力资源-员工管理类', '在职人数', '["员工总数", "HC"]', '某个时点在职的员工总数,不含已离职员工', '某个时点', 'Headcount', 'system', NOW(), NOW()),
('tmpl-hr-006', '人力资源', '人力资源-员工管理类', '离职率', '["员工流失率", "turnover rate"]', '离职人数 / 期初员工总数 × 100%', '按月/季度/年', '区分主动离职和被动离职', 'system', NOW(), NOW()),
('tmpl-hr-007', '人力资源', '人力资源-员工管理类', '新员工离职率', '["试用期离职率", "新人流失率"]', '试用期内离职人数 / 试用期员工总数 × 100%', '统计周期内', '反映招聘匹配度和入职体验', 'system', NOW(), NOW()),
('tmpl-hr-008', '人力资源', '人力资源-员工管理类', '核心员工流失率', '["关键人才流失率"]', '核心员工离职人数 / 核心员工总数 × 100%', '按年或季度', '核心员工定义需提前明确', 'system', NOW(), NOW()),
('tmpl-hr-009', '人力资源', '人力资源-员工管理类', '人员编制', '["编制数", "HC预算"]', '公司批准的各部门员工人数上限', '按部门维度', '用于人力成本预算和招聘计划', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 绩效薪酬类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-hr-010', '人力资源', '人力资源-绩效薪酬类', '人均薪酬', '["平均工资", "人均工资"]', '薪酬总额 / 员工总数', '按月或年统计', '反映薪酬水平', 'system', NOW(), NOW()),
('tmpl-hr-011', '人力资源', '人力资源-绩效薪酬类', '人力成本率', '["人工成本占比"]', '人力成本总额 / 营业收入 × 100%', '按月/季度/年', '衡量人力成本效率', 'system', NOW(), NOW()),
('tmpl-hr-012', '人力资源', '人力资源-绩效薪酬类', '人均产出', '["人均营收", "人效"]', '营业收入 / 员工总数', '按月/季度/年', '衡量人力资源效率', 'system', NOW(), NOW()),
('tmpl-hr-013', '人力资源', '人力资源-绩效薪酬类', '绩效达标率', '["绩效合格率"]', '绩效考核达标的员工数 / 参与考核员工总数 × 100%', '按考核周期', '反映整体绩效水平', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 培训发展类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-hr-014', '人力资源', '人力资源-培训发展类', '培训覆盖率', '["培训参与率"]', '参加培训的员工数 / 员工总数 × 100%', '统计周期内', '衡量培训普及程度', 'system', NOW(), NOW()),
('tmpl-hr-015', '人力资源', '人力资源-培训发展类', '人均培训时长', '["人均培训小时数"]', '培训总时长 / 员工总数', '按年或季度', '反映培训投入力度', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- ============================================================
-- 9. 房地产行业模板（17条）
-- ============================================================

-- 销售管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-re-001', '房地产', '房地产-销售管理类', '认购量', '["认购套数", "意向客户数"]', '客户缴纳认购金/定金的房源套数', '统计周期内', '区分认购和签约', 'system', NOW(), NOW()),
('tmpl-re-002', '房地产', '房地产-销售管理类', '签约量', '["成交套数", "网签套数"]', '正式签订购房合同并完成网签备案的房源套数', '统计周期内', '也称成交量或网签量', 'system', NOW(), NOW()),
('tmpl-re-003', '房地产', '房地产-销售管理类', '签约金额', '["成交金额", "销售额"]', '签约房源的合同总金额', '统计周期内', '反映销售业绩', 'system', NOW(), NOW()),
('tmpl-re-004', '房地产', '房地产-销售管理类', '去化率', '["销售率", "去化速度"]', '已售房源套数 / 可售房源总套数 × 100%', '按项目或期数', '衡量销售速度', 'system', NOW(), NOW()),
('tmpl-re-005', '房地产', '房地产-销售管理类', '认购转签约率', '["签约转化率"]', '签约套数 / 认购套数 × 100%', '统计周期内', '反映客户购买决心', 'system', NOW(), NOW()),
('tmpl-re-006', '房地产', '房地产-销售管理类', '退房率', '["退订率", "解约率"]', '退房套数 / 签约套数 × 100%', '统计周期内', '反映产品或服务问题', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 客户管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-re-007', '房地产', '房地产-客户管理类', '来访量', '["到访客户数", "来访客户"]', '到访售楼处或项目现场的客户数量', '统计周期内', '区分首次来访和多次来访', 'system', NOW(), NOW()),
('tmpl-re-008', '房地产', '房地产-客户管理类', '来电量', '["咨询电话数", "电话来访"]', '客户通过电话咨询项目的数量', '统计周期内', '反映营销推广效果', 'system', NOW(), NOW()),
('tmpl-re-009', '房地产', '房地产-客户管理类', '到访转认购率', '["到访转化率"]', '认购客户数 / 到访客户数 × 100%', '统计周期内', '衡量销售转化能力', 'system', NOW(), NOW()),
('tmpl-re-010', '房地产', '房地产-客户管理类', '客户储备量', '["意向客户数", "客户蓄客量"]', '已登记但尚未认购的潜在客户数量', '某个时点', '反映销售潜力', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 项目运营类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-re-011', '房地产', '房地产-项目运营类', '可售房源', '["可售货值", "可售库存"]', '已取得预售许可证且尚未售出的房源套数或面积', '某个时点', '区分可售和待售', 'system', NOW(), NOW()),
('tmpl-re-012', '房地产', '房地产-项目运营类', '均价', '["销售均价", "成交均价"]', '签约总金额 / 签约总面积', '按项目或周期', '反映价格水平', 'system', NOW(), NOW()),
('tmpl-re-013', '房地产', '房地产-项目运营类', '回款率', '["回款比例", "资金回笼率"]', '实际回款金额 / 签约金额 × 100%', '按项目或周期', '衡量资金回笼速度', 'system', NOW(), NOW()),
('tmpl-re-014', '房地产', '房地产-项目运营类', '开盘去化率', '["首开去化", "开盘销售率"]', '开盘当日签约套数 / 开盘推出套数 × 100%', '按开盘批次', '反映项目热度', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 物业管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-re-015', '房地产', '房地产-物业管理类', '入住率', '["入伙率", "交付入住率"]', '已入住户数 / 已交付户数 × 100%', '按项目或社区', '反映交付和入住情况', 'system', NOW(), NOW()),
('tmpl-re-016', '房地产', '房地产-物业管理类', '物业费收缴率', '["物业费回收率"]', '实际收缴物业费 / 应收物业费 × 100%', '按月或年统计', '衡量物业费收缴情况', 'system', NOW(), NOW()),
('tmpl-re-017', '房地产', '房地产-物业管理类', '业主满意度', '["物业满意度", "服务评分"]', '业主对物业服务的满意度评分,通常1-5分或百分制', '按社区或周期', '衡量物业服务质量', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- ============================================================
-- 6. 教育行业模板（18条）
-- ============================================================

-- 招生管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-edu-001', '教育', '教育-招生管理类', '招生人数', '["新生人数", "录取人数"]', '统计周期内成功报名并缴费的新生数量', '按学期或学年', '区分报名人数和实际入学人数', 'system', NOW(), NOW()),
('tmpl-edu-002', '教育', '教育-招生管理类', '报名转化率', '["入学转化率", "报名成功率"]', '实际缴费入学人数 / 报名咨询人数 × 100%', '按招生周期', '衡量招生效率', 'system', NOW(), NOW()),
('tmpl-edu-003', '教育', '教育-招生管理类', '招生成本', '["获客成本", "单个学员成本"]', '招生总费用 / 招生人数，即获取一个新学员的平均成本', '按招生渠道', '越低说明招生效率越高', 'system', NOW(), NOW()),
('tmpl-edu-004', '教育', '教育-招生管理类', '满班率', '["班级满员率", "开班率"]', '实际招生人数 / 计划招生人数 × 100%', '按班级或课程', '反映课程受欢迎程度', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 教学管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-edu-005', '教育', '教育-教学管理类', '在校生', '["在读学员", "在籍学生"]', '当前在校学习的学生总数，不含已毕业或退学学生', '某个时点', '也称在籍学生数', 'system', NOW(), NOW()),
('tmpl-edu-006', '教育', '教育-教学管理类', '出勤率', '["到课率", "上课率"]', '实际出勤人次 / 应出勤人次 × 100%', '按班级或课程', '衡量学生学习积极性', 'system', NOW(), NOW()),
('tmpl-edu-007', '教育', '教育-教学管理类', '课程完成率', '["课程结课率", "完课率"]', '完成全部课时的学员数 / 报名学员数 × 100%', '按课程维度', '反映课程吸引力和学员坚持度', 'system', NOW(), NOW()),
('tmpl-edu-008', '教育', '教育-教学管理类', '平均成绩', '["班级均分", "平均分"]', '班级或课程所有学员成绩的算术平均值', '按班级或考试', '衡量整体教学效果', 'system', NOW(), NOW()),
('tmpl-edu-009', '教育', '教育-教学管理类', '及格率', '["通过率", "合格率"]', '成绩达到及格线的学员数 / 参考学员总数 × 100%', '按考试或课程', '反映教学质量', 'system', NOW(), NOW()),
('tmpl-edu-010', '教育', '教育-教学管理类', '优秀率', '["优秀学员占比"]', '成绩达到优秀标准的学员数 / 参考学员总数 × 100%', '按考试或课程', '衡量高水平学员比例', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 学员运营类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-edu-011', '教育', '教育-学员运营类', '续费率', '["续班率", "续报率"]', '课程结束后继续报名下一期课程的学员数 / 上期学员总数 × 100%', '按课程周期', '衡量学员满意度和忠诚度', 'system', NOW(), NOW()),
('tmpl-edu-012', '教育', '教育-学员运营类', '退费率', '["退课率", "退学率"]', '申请退费的学员数 / 报名学员总数 × 100%', '统计周期内', '反映课程质量和服务问题', 'system', NOW(), NOW()),
('tmpl-edu-013', '教育', '教育-学员运营类', '流失率', '["学员流失率", "退学率"]', '未续费或退学的学员数 / 期初学员总数 × 100%', '按学期或学年', '越低说明学员粘性越好', 'system', NOW(), NOW()),
('tmpl-edu-014', '教育', '教育-学员运营类', '转介绍率', '["推荐率", "口碑转化率"]', '通过老学员推荐而来的新学员数 / 新学员总数 × 100%', '按招生周期', '反映口碑和满意度', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 教师管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-edu-015', '教育', '教育-教师管理类', '师生比', '["教师学生比"]', '教师总数 / 在校生总数，反映师资配置情况', '某个时点', '越低说明师资越充足', 'system', NOW(), NOW()),
('tmpl-edu-016', '教育', '教育-教师管理类', '教师满意度', '["教师评分", "教学评价"]', '学员对教师教学质量的评价得分，通常1-5分或百分制', '按教师或课程', '衡量教学质量', 'system', NOW(), NOW()),
('tmpl-edu-017', '教育', '教育-教师管理类', '课时利用率', '["教师产能利用率"]', '实际授课课时 / 可授课课时 × 100%', '按教师维度', '衡量教师工作饱和度', 'system', NOW(), NOW()),
('tmpl-edu-018', '教育', '教育-教师管理类', '教师流失率', '["离职率"]', '离职教师数 / 期初教师总数 × 100%', '按年或季度', '反映教师稳定性', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- ============================================================
-- 7. 医疗健康行业模板（16条）
-- ============================================================

-- 门诊管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-med-001', '医疗健康', '医疗健康-门诊管理类', '门诊量', '["门诊人次", "就诊量"]', '统计周期内到门诊就诊的患者人次数', '按日/周/月统计', '区分人次和人数', 'system', NOW(), NOW()),
('tmpl-med-002', '医疗健康', '医疗健康-门诊管理类', '平均候诊时长', '["等待时间", "候诊时间"]', '从患者挂号到医生接诊的平均等待时间，单位为分钟', '按科室或时段', '衡量就诊效率', 'system', NOW(), NOW()),
('tmpl-med-003', '医疗健康', '医疗健康-门诊管理类', '平均就诊时长', '["诊疗时长", "接诊时间"]', '医生为每位患者提供诊疗服务的平均时长，单位为分钟', '按科室或医生', '反映诊疗质量', 'system', NOW(), NOW()),
('tmpl-med-004', '医疗健康', '医疗健康-门诊管理类', '复诊率', '["回诊率", "再诊率"]', '再次就诊的患者数 / 首诊患者数 × 100%', '统计周期内', '反映患者信任度和疾病管理需求', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 住院管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-med-005', '医疗健康', '医疗健康-住院管理类', '床位使用率', '["床位占用率", "病床使用率"]', '实际占用床日数 / 实际开放床日数 × 100%', '按科室或医院', '衡量床位资源利用效率', 'system', NOW(), NOW()),
('tmpl-med-006', '医疗健康', '医疗健康-住院管理类', '平均住院日', '["住院天数", "平均住院时长"]', '出院患者住院总天数 / 出院患者总数', '按科室或病种', '反映医疗效率和疾病严重程度', 'system', NOW(), NOW()),
('tmpl-med-007', '医疗健康', '医疗健康-住院管理类', '床位周转率', '["床位周转次数"]', '出院患者数 / 平均开放床位数', '按月或年统计', '越高说明床位利用越充分', 'system', NOW(), NOW()),
('tmpl-med-008', '医疗健康', '医疗健康-住院管理类', '入院人数', '["住院人数", "收治人数"]', '统计周期内办理入院手续的患者数量', '按科室或医院', '衡量收治能力', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 医疗质量类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-med-009', '医疗健康', '医疗健康-医疗质量类', '治愈率', '["治愈好转率", "治疗成功率"]', '治愈或好转的患者数 / 出院患者总数 × 100%', '按科室或病种', '衡量医疗效果', 'system', NOW(), NOW()),
('tmpl-med-010', '医疗健康', '医疗健康-医疗质量类', '手术成功率', '["手术治愈率"]', '手术成功的患者数 / 手术总数 × 100%', '按手术类型', '反映手术质量', 'system', NOW(), NOW()),
('tmpl-med-011', '医疗健康', '医疗健康-医疗质量类', '院内感染率', '["医院感染率", "HAI"]', '发生院内感染的患者数 / 住院患者总数 × 100%', '按科室或医院', 'Healthcare-Associated Infection', 'system', NOW(), NOW()),
('tmpl-med-012', '医疗健康', '医疗健康-医疗质量类', '患者满意度', '["就医满意度", "服务评分"]', '患者对医疗服务的满意度评分,通常1-5分或百分制', '按科室或医院', '衡量服务质量', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 药品耗材类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-med-013', '医疗健康', '医疗健康-药品耗材类', '药占比', '["药品费用占比"]', '药品费用 / 医疗总收入 × 100%', '按科室或医院', '国家有控制指标要求', 'system', NOW(), NOW()),
('tmpl-med-014', '医疗健康', '医疗健康-药品耗材类', '耗材占比', '["耗材费用占比"]', '医用耗材费用 / 医疗总收入 × 100%', '按科室或医院', '反映耗材使用情况', 'system', NOW(), NOW()),
('tmpl-med-015', '医疗健康', '医疗健康-药品耗材类', '抗菌药物使用率', '["抗生素使用率"]', '使用抗菌药物的患者数 / 总患者数 × 100%', '按科室或医院', '国家有严格监管要求', 'system', NOW(), NOW()),
('tmpl-med-016', '医疗健康', '医疗健康-药品耗材类', '药品库存周转率', '["药品周转率"]', '药品出库成本 / 平均药品库存 × 100%', '按月或季度', '反映药品库存管理效率', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- ============================================================
-- 8. 人力资源行业模板（15条）
-- ============================================================

-- 招聘管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-hr-001', '人力资源', '人力资源-招聘管理类', '招聘周期', '["招聘时长", "平均招聘天数"]', '从发布职位到候选人入职的平均日历天数', '按岗位或部门', '越短说明招聘效率越高', 'system', NOW(), NOW()),
('tmpl-hr-002', '人力资源', '人力资源-招聘管理类', 'Offer接受率', '["录用接受率", "Offer通过率"]', '接受Offer的候选人数 / 发出Offer总数 × 100%', '按岗位或渠道', '反映薪酬竞争力和雇主品牌', 'system', NOW(), NOW()),
('tmpl-hr-003', '人力资源', '人力资源-招聘管理类', '招聘完成率', '["招聘达成率", "HC完成率"]', '实际入职人数 / 计划招聘人数 × 100%', '按周期或部门', 'HC = Headcount', 'system', NOW(), NOW()),
('tmpl-hr-004', '人力资源', '人力资源-招聘管理类', '招聘成本', '["单人招聘成本", "人均招聘费用"]', '招聘总费用 / 实际入职人数', '按渠道或岗位', '包括广告费、猎头费、差旅费等', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 员工管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-hr-005', '人力资源', '人力资源-员工管理类', '在职人数', '["员工总数", "HC"]', '某个时点在职的员工总数,不含已离职员工', '某个时点', 'Headcount', 'system', NOW(), NOW()),
('tmpl-hr-006', '人力资源', '人力资源-员工管理类', '离职率', '["员工流失率", "turnover rate"]', '离职人数 / 期初员工总数 × 100%', '按月/季度/年', '区分主动离职和被动离职', 'system', NOW(), NOW()),
('tmpl-hr-007', '人力资源', '人力资源-员工管理类', '新员工离职率', '["试用期离职率", "新人流失率"]', '试用期内离职人数 / 试用期员工总数 × 100%', '统计周期内', '反映招聘匹配度和入职体验', 'system', NOW(), NOW()),
('tmpl-hr-008', '人力资源', '人力资源-员工管理类', '核心员工流失率', '["关键人才流失率"]', '核心员工离职人数 / 核心员工总数 × 100%', '按年或季度', '核心员工定义需提前明确', 'system', NOW(), NOW()),
('tmpl-hr-009', '人力资源', '人力资源-员工管理类', '人员编制', '["编制数", "HC预算"]', '公司批准的各部门员工人数上限', '按部门维度', '用于人力成本预算和招聘计划', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 绩效薪酬类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-hr-010', '人力资源', '人力资源-绩效薪酬类', '人均薪酬', '["平均工资", "人均工资"]', '薪酬总额 / 员工总数', '按月或年统计', '反映薪酬水平', 'system', NOW(), NOW()),
('tmpl-hr-011', '人力资源', '人力资源-绩效薪酬类', '人力成本率', '["人工成本占比"]', '人力成本总额 / 营业收入 × 100%', '按月/季度/年', '衡量人力成本效率', 'system', NOW(), NOW()),
('tmpl-hr-012', '人力资源', '人力资源-绩效薪酬类', '人均产出', '["人均营收", "人效"]', '营业收入 / 员工总数', '按月/季度/年', '衡量人力资源效率', 'system', NOW(), NOW()),
('tmpl-hr-013', '人力资源', '人力资源-绩效薪酬类', '绩效达标率', '["绩效合格率"]', '绩效考核达标的员工数 / 参与考核员工总数 × 100%', '按考核周期', '反映整体绩效水平', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 培训发展类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-hr-014', '人力资源', '人力资源-培训发展类', '培训覆盖率', '["培训参与率"]', '参加培训的员工数 / 员工总数 × 100%', '统计周期内', '衡量培训普及程度', 'system', NOW(), NOW()),
('tmpl-hr-015', '人力资源', '人力资源-培训发展类', '人均培训时长', '["人均培训小时数"]', '培训总时长 / 员工总数', '按年或季度', '反映培训投入力度', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- ============================================================
-- 9. 房地产行业模板（17条）
-- ============================================================

-- 销售管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-re-001', '房地产', '房地产-销售管理类', '认购量', '["认购套数", "意向客户数"]', '客户缴纳认购金/定金的房源套数', '统计周期内', '区分认购和签约', 'system', NOW(), NOW()),
('tmpl-re-002', '房地产', '房地产-销售管理类', '签约量', '["成交套数", "网签套数"]', '正式签订购房合同并完成网签备案的房源套数', '统计周期内', '也称成交量或网签量', 'system', NOW(), NOW()),
('tmpl-re-003', '房地产', '房地产-销售管理类', '签约金额', '["成交金额", "销售额"]', '签约房源的合同总金额', '统计周期内', '反映销售业绩', 'system', NOW(), NOW()),
('tmpl-re-004', '房地产', '房地产-销售管理类', '去化率', '["销售率", "去化速度"]', '已售房源套数 / 可售房源总套数 × 100%', '按项目或期数', '衡量销售速度', 'system', NOW(), NOW()),
('tmpl-re-005', '房地产', '房地产-销售管理类', '认购转签约率', '["签约转化率"]', '签约套数 / 认购套数 × 100%', '统计周期内', '反映客户购买决心', 'system', NOW(), NOW()),
('tmpl-re-006', '房地产', '房地产-销售管理类', '退房率', '["退订率", "解约率"]', '退房套数 / 签约套数 × 100%', '统计周期内', '反映产品或服务问题', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 客户管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-re-007', '房地产', '房地产-客户管理类', '来访量', '["到访客户数", "来访客户"]', '到访售楼处或项目现场的客户数量', '统计周期内', '区分首次来访和多次来访', 'system', NOW(), NOW()),
('tmpl-re-008', '房地产', '房地产-客户管理类', '来电量', '["咨询电话数", "电话来访"]', '客户通过电话咨询项目的数量', '统计周期内', '反映营销推广效果', 'system', NOW(), NOW()),
('tmpl-re-009', '房地产', '房地产-客户管理类', '到访转认购率', '["到访转化率"]', '认购客户数 / 到访客户数 × 100%', '统计周期内', '衡量销售转化能力', 'system', NOW(), NOW()),
('tmpl-re-010', '房地产', '房地产-客户管理类', '客户储备量', '["意向客户数", "客户蓄客量"]', '已登记但尚未认购的潜在客户数量', '某个时点', '反映销售潜力', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 项目运营类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-re-011', '房地产', '房地产-项目运营类', '可售房源', '["可售货值", "可售库存"]', '已取得预售许可证且尚未售出的房源套数或面积', '某个时点', '区分可售和待售', 'system', NOW(), NOW()),
('tmpl-re-012', '房地产', '房地产-项目运营类', '均价', '["销售均价", "成交均价"]', '签约总金额 / 签约总面积', '按项目或周期', '反映价格水平', 'system', NOW(), NOW()),
('tmpl-re-013', '房地产', '房地产-项目运营类', '回款率', '["回款比例", "资金回笼率"]', '实际回款金额 / 签约金额 × 100%', '按项目或周期', '衡量资金回笼速度', 'system', NOW(), NOW()),
('tmpl-re-014', '房地产', '房地产-项目运营类', '开盘去化率', '["首开去化", "开盘销售率"]', '开盘当日签约套数 / 开盘推出套数 × 100%', '按开盘批次', '反映项目热度', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- 物业管理类
INSERT INTO business_term_templates (id, category, template_name, term_name, term_alias, term_definition, applicable_conditions, remarks, source, created_at, updated_at) VALUES
('tmpl-re-015', '房地产', '房地产-物业管理类', '入住率', '["入伙率", "交付入住率"]', '已入住户数 / 已交付户数 × 100%', '按项目或社区', '反映交付和入住情况', 'system', NOW(), NOW()),
('tmpl-re-016', '房地产', '房地产-物业管理类', '物业费收缴率', '["物业费回收率"]', '实际收缴物业费 / 应收物业费 × 100%', '按月或年统计', '衡量物业费收缴情况', 'system', NOW(), NOW()),
('tmpl-re-017', '房地产', '房地产-物业管理类', '业主满意度', '["物业满意度", "服务评分"]', '业主对物业服务的满意度评分,通常1-5分或百分制', '按社区或周期', '衡量物业服务质量', 'system', NOW(), NOW())
ON CONFLICT (category, term_name) DO NOTHING;

-- =============================================
-- 数据治理模块建表脚本
-- 执行时间: 2026-06-01
-- 说明: 创建治理规则库、规则、模板、报告等表
-- =============================================

-- 1. 规则库表
CREATE TABLE IF NOT EXISTS governance_rule_libraries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),           -- 规则库ID
    name VARCHAR(100) NOT NULL,                              -- 规则库名称
    description TEXT,                                        -- 规则库描述
    status VARCHAR(20) DEFAULT 'active',                     -- 状态: active=启用, inactive=停用
    created_by UUID NOT NULL,                                -- 创建者用户ID
    datasource_id UUID NOT NULL REFERENCES datasource_infos(id) ON DELETE CASCADE,  -- 数据源ID（必须关联）
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),             -- 创建时间
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()              -- 更新时间
);

-- 表注释
COMMENT ON TABLE governance_rule_libraries IS '数据治理规则库表 - 存储用户创建的规则库，用于管理一组相关的治理规则';
-- 字段注释
COMMENT ON COLUMN governance_rule_libraries.id IS '规则库唯一标识符';
COMMENT ON COLUMN governance_rule_libraries.name IS '规则库名称';
COMMENT ON COLUMN governance_rule_libraries.description IS '规则库描述说明';
COMMENT ON COLUMN governance_rule_libraries.status IS '规则库状态: active=启用, inactive=停用';
COMMENT ON COLUMN governance_rule_libraries.created_by IS '创建该规则库的用户ID';
COMMENT ON COLUMN governance_rule_libraries.datasource_id IS '规则库绑定的数据源ID，必须关联，删除数据源时规则库会被级联删除';
COMMENT ON COLUMN governance_rule_libraries.created_at IS '规则库创建时间';
COMMENT ON COLUMN governance_rule_libraries.updated_at IS '规则库最后更新时间';

-- 2. 规则表
CREATE TABLE IF NOT EXISTS governance_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),           -- 规则ID
    library_id UUID REFERENCES governance_rule_libraries(id) ON DELETE CASCADE,  -- 所属规则库ID
    rule_name VARCHAR(255) NOT NULL,                        -- 规则名称
    rule_type VARCHAR(50) NOT NULL,                         -- 规则类型
    -- rule_type:
    --   基础类型: null_check=空值检测, unique=唯一性检测, format=格式检测,
    --            threshold=阈值检测, enum=枚举检测, custom_sql=自定义SQL
    --   扩展类型: length_check=长度检测, range_check=范围检测, date_check=日期检测,
    --            consistency_check=一致性检测, freshness_check=新鲜度检测, value_distribution=值分布检测
    --   复合类型: composite=复合条件(多条件AND/OR), table_stats=表级统计
    target_table VARCHAR(255),                              -- 目标表名（可选，不填则对所有表生效）
    target_column VARCHAR(255),                             -- 目标列名
    condition_expr TEXT,                                   -- 规则条件表达式（单条件场景）
    conditions_config TEXT,                                -- 多条件配置JSON（用于composite类型）
    sql_text TEXT,                                         -- 检测SQL语句（用于预览和执行）
    severity VARCHAR(20) DEFAULT 'warning',                 -- 严重级别: critical=严重, warning=警告, info=信息
    description TEXT,                                       -- 规则描述
    enabled BOOLEAN DEFAULT TRUE,                           -- 是否启用: true=启用, false=禁用
    create_source VARCHAR(20) DEFAULT 'manual',             -- 创建来源: manual=手动配置, template=模板导入, ai=AI智能解析
    db_type VARCHAR(20),                                    -- 目标数据库类型，从规则库关联的数据源继承
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),             -- 创建时间
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()             -- 更新时间
);

-- 表注释
COMMENT ON TABLE governance_rules IS '数据治理规则表 - 存储具体的治理规则定义，包括规则类型、目标表/列、条件表达式等';
-- 字段注释
COMMENT ON COLUMN governance_rules.id IS '规则唯一标识符';
COMMENT ON COLUMN governance_rules.library_id IS '所属规则库的ID，删除规则库时会级联删除该规则';
COMMENT ON COLUMN governance_rules.rule_name IS '规则名称，如"手机号非空检测"';
COMMENT ON COLUMN governance_rules.rule_type IS '规则类型: null_check=空值检测, unique=唯一性检测, format=格式检测, threshold=阈值检测, enum=枚举检测, custom_sql=自定义SQL, length_check=长度检测, range_check=范围检测, date_check=日期检测, consistency_check=一致性检测, freshness_check=新鲜度检测, value_distribution=值分布检测';
COMMENT ON COLUMN governance_rules.target_table IS '规则应用于的目标表名，不填则对所有表生效（多表模式下系统会自动识别相关表）';
COMMENT ON COLUMN governance_rules.target_column IS '规则应用于的目标列名';
COMMENT ON COLUMN governance_rules.condition_expr IS '规则条件表达式，支持自然语言或SQL表达式，如"手机号为空"或"column IS NULL OR column = ''''''"';
COMMENT ON COLUMN governance_rules.conditions_config IS '多条件配置JSON，用于composite复合规则类型，格式: {"conditions": [...], "condition_mode": "AND"}';
COMMENT ON COLUMN governance_rules.sql_text IS '规则对应的检测SQL语句，用于预览和执行时的查询语句';
COMMENT ON COLUMN governance_rules.severity IS '规则严重级别: critical=严重需立即处理, warning=警告建议处理, info=参考信息';
COMMENT ON COLUMN governance_rules.description IS '规则的详细描述说明，AI模式下存储用户输入的自然语言';
COMMENT ON COLUMN governance_rules.enabled IS '规则是否启用: true=启用(执行时会被应用), false=禁用(执行时跳过)';
COMMENT ON COLUMN governance_rules.create_source IS '规则创建来源: manual=手动配置, template=模板导入, ai=AI智能解析';
COMMENT ON COLUMN governance_rules.db_type IS '规则适用的目标数据库类型: postgresql/mysql/mssql/oracle/sqlite/trino/kingbase，从规则库关联的数据源继承';
COMMENT ON COLUMN governance_rules.created_at IS '规则创建时间';
COMMENT ON COLUMN governance_rules.updated_at IS '规则最后更新时间';

-- 3. 规则模板表
CREATE TABLE IF NOT EXISTS governance_rule_templates (
    id VARCHAR(50) PRIMARY KEY,                            -- 模板ID，如 'tmpl-null-check'
    rule_type VARCHAR(50) NOT NULL,                         -- 模板对应的规则类型
    template_name VARCHAR(255) NOT NULL,                    -- 模板名称
    description TEXT,                                       -- 模板描述
    default_condition TEXT,                                 -- 默认条件表达式
    applicable_columns TEXT,                              -- 适用的列类型，如 'varchar,text,int,bigint'
    default_severity VARCHAR(20) DEFAULT 'warning',          -- 默认严重级别: critical, warning, info
    condition_placeholder_hint TEXT,                         -- 条件占位符提示（如 min/max/days 等参数的说明）
    category VARCHAR(50),                                  -- 模板分类
    created_at TIMESTAMP NOT NULL DEFAULT NOW()              -- 创建时间
);

-- 表注释
COMMENT ON TABLE governance_rule_templates IS '数据治理规则模板表 - 存储系统预置的规则模板，用户可从模板快速导入规则';
-- 字段注释
COMMENT ON COLUMN governance_rule_templates.id IS '模板唯一标识符，如"tmpl-null-check"';
COMMENT ON COLUMN governance_rule_templates.rule_type IS '模板对应的规则类型';
COMMENT ON COLUMN governance_rule_templates.template_name IS '模板显示名称，如"空值检测"';
COMMENT ON COLUMN governance_rule_templates.description IS '模板功能描述';
COMMENT ON COLUMN governance_rule_templates.default_condition IS '模板默认的条件表达式，用户导入时可修改';
COMMENT ON COLUMN governance_rule_templates.applicable_columns IS '模板适用的列数据类型，多个用逗号分隔';
COMMENT ON COLUMN governance_rule_templates.created_at IS '模板创建时间';

-- 4. 治理报告表
CREATE TABLE IF NOT EXISTS governance_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),           -- 报告ID
    user_id UUID NOT NULL,                                  -- 用户ID
    datasource_id UUID,                                     -- 数据源ID
    report_name VARCHAR(255),                               -- 报告名称
    execution_time TIMESTAMP NOT NULL DEFAULT NOW(),         -- 执行时间
    scope_tables TEXT[],                                    -- 涉及的表列表
    rules_applied INTEGER,                                  -- 应用的规则数
    include_quality BOOLEAN DEFAULT TRUE,                    -- 是否包含数据质量检测
    include_basic_audit BOOLEAN DEFAULT FALSE,               -- 是否包含基础空值检测
    include_relationship BOOLEAN DEFAULT FALSE,             -- 是否包含关系发现
    quality_score DECIMAL(5,2),                             -- 数据质量评分(0-100)
    grade VARCHAR(20),                                      -- 评级: 优秀/良好/一般/较差/差
    -- 基础空值检测的完整结果（以表为单位，每表包含所有列的检测结果）
    -- 参考 dataaudit 的 audited_data 结构：
    -- [{
    --   "db_type": "postgresql", "database": "xxx", "schema": "public",
    --   "table": "sales_orders",
    --   "report": [{"column_name": "id", "data_type": "integer",
    --               "total_rows": 7, "null_count": 0, "empty_str_count": 0,
    --               "missing_count": 0, "missing_pct": 0.0}, ...]
    -- }, ...]
    basic_audit_result JSONB,
    -- 基础空值检测执行明细（从rule_execution_results表查询execution_source=basic_audit的记录）
    basic_audit_detail JSONB,
    -- 关系盘点的完整结果（直接复用全域盘点的 discover_all_relationships 返回值）
    -- 包含 tables_count, relationships_count, cards_count, relationships[],
    -- cards[], statistics, cross_source_count 等完整信息
    full_relation_discovery JSONB,
    -- 基于规则库的质检完整结果（只保留有 rule_id 的规则执行结果，便于追溯）
    quality_audit_result JSONB,
    summary JSONB,                                          -- 汇总数据(JSON格式)
    -- 执行接口完整返回值（三大模块的完整数据：basic_audit / quality_audit / relation_discovery / summary）
    -- 作为报告生成的唯一真实数据源，报告生成阶段直接读取此字段渲染 Markdown
    execution_response JSONB,
    details JSONB,                                          -- 详细结果(JSON格式)
    exported_file_path VARCHAR(512),                        -- 导出文件路径
    exported_file_type VARCHAR(20),                         -- 导出文件类型: pdf=PDF报告, excel=Excel报告, docx=Word报告
    exported_file_name VARCHAR(255),                        -- 导出文件显示名称
    file_size BIGINT,                                      -- 导出文件大小(字节)
    file_created_at TIMESTAMP,                              -- 文件创建时间
    file_status VARCHAR(20) DEFAULT 'pending',               -- 文件生成状态: pending=待生成, generating=生成中, completed=已完成, failed=失败
    file_error_msg TEXT,                                    -- 文件生成失败时的错误信息
    created_at TIMESTAMP NOT NULL DEFAULT NOW()              -- 记录创建时间
);

-- 表注释
COMMENT ON TABLE governance_reports IS '数据治理报告表 - 存储治理盘点生成的报告，包含质量评分、评级、执行明细及导出文件信息';
-- 字段注释
COMMENT ON COLUMN governance_reports.id IS '报告唯一标识符';
COMMENT ON COLUMN governance_reports.user_id IS '生成该报告的用户ID';
COMMENT ON COLUMN governance_reports.datasource_id IS '报告对应的数据源ID';
COMMENT ON COLUMN governance_reports.report_name IS '报告显示名称';
COMMENT ON COLUMN governance_reports.execution_time IS '报告执行/生成时间';
COMMENT ON COLUMN governance_reports.scope_tables IS '本次盘点涉及的表名数组';
COMMENT ON COLUMN governance_reports.rules_applied IS '本次应用/执行的规则总数';
COMMENT ON COLUMN governance_reports.include_quality IS '报告是否包含数据质量检测结果';
COMMENT ON COLUMN governance_reports.include_basic_audit IS '报告是否包含基础空值检测结果';
COMMENT ON COLUMN governance_reports.include_relationship IS '报告是否包含表关系发现结果';
COMMENT ON COLUMN governance_reports.quality_score IS '数据质量综合评分，范围0-100';
COMMENT ON COLUMN governance_reports.grade IS '数据质量评级: 优秀(95+), 良好(85-94), 一般(70-84), 较差(60-69), 差(<60)';
COMMENT ON COLUMN governance_reports.basic_audit_result IS '基础空值检测完整结果(JSON): 以表为单位，每表包含该表所有列的null/empty统计';
COMMENT ON COLUMN governance_reports.basic_audit_detail IS '基础空值检测执行明细(JSON): 从rule_execution_results表查询execution_source=basic_audit的记录';
COMMENT ON COLUMN governance_reports.full_relation_discovery IS '关系盘点完整结果(JSON): 直接复用全域盘点discover_all_relationships返回值，包含relationships、cards、statistics等';
COMMENT ON COLUMN governance_reports.quality_audit_result IS '基于规则库质检完整结果(JSON): 仅包含有rule_id的规则执行结果，用于追溯';
COMMENT ON COLUMN governance_reports.summary IS '报告汇总数据(JSON): 包含规则执行统计、分类统计等';
COMMENT ON COLUMN governance_reports.execution_response IS '执行接口完整返回值(JSON): 包含 basic_audit / quality_audit / relation_discovery / summary，作为报告生成的唯一真实数据源';
COMMENT ON COLUMN governance_reports.details IS '报告详细结果(JSON): 包含执行明细、问题列表、建议等';
COMMENT ON COLUMN governance_reports.exported_file_path IS '导出的报告文件完整路径';
COMMENT ON COLUMN governance_reports.exported_file_type IS '导出文件类型: pdf=PDF格式, excel=Excel格式, docx=Word格式';
COMMENT ON COLUMN governance_reports.exported_file_name IS '导出文件的用户友好显示名称，如"数据治理报告_20260629.docx"';
COMMENT ON COLUMN governance_reports.file_size IS '导出文件大小，单位字节';
COMMENT ON COLUMN governance_reports.file_created_at IS '导出文件生成时间';
COMMENT ON COLUMN governance_reports.file_status IS '文件生成状态: pending=待生成, generating=生成中, completed=已完成, failed=失败';
COMMENT ON COLUMN governance_reports.file_error_msg IS '文件生成失败时的错误信息';
COMMENT ON COLUMN governance_reports.created_at IS '报告记录创建时间';

-- 5. 规则执行结果表
CREATE TABLE IF NOT EXISTS rule_execution_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),           -- 结果ID
    report_id UUID REFERENCES governance_reports(id) ON DELETE CASCADE,  -- 所属报告ID
    library_id UUID,                                       -- 规则库ID（追溯结果来源）
    rule_id UUID,                                           -- 对应规则ID
    rule_name VARCHAR(255),                                 -- 规则名称
    rule_type VARCHAR(50),                                  -- 规则类型
    severity VARCHAR(20),                                   -- 严重级别: critical=严重, warning=警告, info=信息
    table_name VARCHAR(255),                                -- 目标表名
    column_name VARCHAR(255),                               -- 目标列名（单列场景）
    -- 执行模式：标识规则属于哪种类型
    --   scoped_single     = 有 target_table + target_column（单列/单条件规则）
    --   scoped_multi_cond = 有 target_table + conditions_config（多条件规则）
    --   unscoped          = 无 target_table（全局/无作用域规则）
    rule_mode VARCHAR(30),
    total_count BIGINT,                                    -- 总记录数
    passed_count BIGINT,                                   -- 通过记录数
    failed_count BIGINT,                                   -- 失败/不符合规则记录数
    failed_rate DECIMAL(5,2),                              -- 失败率(百分比)
    failed_samples JSONB,                                   -- 失败样本数据
    -- 本次执行的 SQL 文本（规则生成的检测 SQL）
    -- 注意：stored_sql_text 只在规则实际被执行时写入；如果规则有预存的 sql_text 字段，
    --       则与其相同（多条件规则会生成新的 SQL）
    executed_sql_text TEXT,
    -- SQL 执行耗时（毫秒），便于性能分析和慢查询定位
    execution_time_ms INTEGER,
    -- SQL 原始执行结果：以键值对形式存储查询返回的完整列名和值
    -- 例如 null_check: {total_count: 10000, failed_count: 20}
    --       unique:    {total_count: 10000, non_null_count: 9980, unique_count: 9900, duplicate_count: 80}
    --       threshold: {total_count: 10000, failed_count: 15}
    raw_result JSONB,
    status VARCHAR(20),                                     -- 执行状态: passed=通过, failed=失败, error=执行错误
    error_message TEXT,                                      -- 规则执行出错时的错误信息
    -- 执行结果来源: rule_library=规则库质检, basic_audit=基础空值检测
    execution_source VARCHAR(30),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()                  -- 创建时间
);

-- 表注释
COMMENT ON TABLE rule_execution_results IS '规则执行结果表 - 存储每条规则在盘点时的执行结果，包括通过/失败统计和失败样本';
-- 字段注释
COMMENT ON COLUMN rule_execution_results.id IS '执行结果唯一标识符';
COMMENT ON COLUMN rule_execution_results.report_id IS '所属报告ID，删除报告时会级联删除该结果';
COMMENT ON COLUMN rule_execution_results.library_id IS '规则库ID，用于追溯执行结果来自哪个规则库';
COMMENT ON COLUMN rule_execution_results.rule_id IS '执行的规则ID';
COMMENT ON COLUMN rule_execution_results.rule_name IS '执行的规则名称';
COMMENT ON COLUMN rule_execution_results.rule_type IS '执行的规则类型: null_check=空值检测, unique=唯一性检测, format=格式检测, threshold=阈值检测, enum=枚举检测, custom_sql=自定义SQL等';
COMMENT ON COLUMN rule_execution_results.severity IS '规则严重级别: critical=严重需立即处理, warning=警告建议处理, info=参考信息';
COMMENT ON COLUMN rule_execution_results.table_name IS '规则应用的目标表名';
COMMENT ON COLUMN rule_execution_results.column_name IS '规则应用的目标列名（单列/单条件场景时填充，多条件场景为空）';
COMMENT ON COLUMN rule_execution_results.rule_mode IS '执行模式: scoped_single=单列规则(有target_table+target_column), scoped_multi_cond=多条件规则(有target_table+conditions_config), unscoped=全局规则(无target_table)';
COMMENT ON COLUMN rule_execution_results.total_count IS '检测的总记录数';
COMMENT ON COLUMN rule_execution_results.passed_count IS '通过/符合规则的记录数';
COMMENT ON COLUMN rule_execution_results.failed_count IS '失败/不符合规则的记录数';
COMMENT ON COLUMN rule_execution_results.failed_rate IS '失败率，范围0-100，表示不符合规则的记录占比';
COMMENT ON COLUMN rule_execution_results.failed_samples IS '失败样本数据(JSON数组)，包含具体不符合规则的记录示例';
COMMENT ON COLUMN rule_execution_results.executed_sql_text IS '本次执行的检测SQL文本，便于审计和排查问题';
COMMENT ON COLUMN rule_execution_results.execution_time_ms IS 'SQL执行耗时（毫秒），用于性能分析和慢查询定位';
COMMENT ON COLUMN rule_execution_results.raw_result IS 'SQL查询原始返回结果(JSON)，以键值对形式存储查询返回的完整列名和值，便于审计和排查';
COMMENT ON COLUMN rule_execution_results.status IS '执行状态: passed=通过(失败率<5%), failed=失败, error=执行出错';
COMMENT ON COLUMN rule_execution_results.error_message IS '规则执行出错时的错误信息';
COMMENT ON COLUMN rule_execution_results.execution_source IS '执行结果来源: rule_library=规则库质检, basic_audit=基础空值检测';
COMMENT ON COLUMN rule_execution_results.created_at IS '执行结果记录创建时间';

-- =============================================
-- 创建索引
-- =============================================
-- governance_rules 表
CREATE INDEX IF NOT EXISTS idx_governance_rules_library_id ON governance_rules(library_id);
CREATE INDEX IF NOT EXISTS idx_governance_rules_enabled ON governance_rules(enabled);
CREATE INDEX IF NOT EXISTS idx_governance_rules_target_table ON governance_rules(target_table);
CREATE INDEX IF NOT EXISTS idx_governance_rules_rule_type ON governance_rules(rule_type);
-- 复合索引：覆盖 GovernanceRuleLibrary.datasource_id + created_by + library_id 过滤
CREATE INDEX IF NOT EXISTS idx_gr_lib_datasource_created ON governance_rule_libraries(datasource_id, created_by);
-- governance_reports 表
CREATE INDEX IF NOT EXISTS idx_governance_reports_user_id ON governance_reports(user_id);
CREATE INDEX IF NOT EXISTS idx_governance_reports_datasource_id ON governance_reports(datasource_id);
-- rule_execution_results 表
CREATE INDEX IF NOT EXISTS idx_rule_execution_results_report_id ON rule_execution_results(report_id);
CREATE INDEX IF NOT EXISTS idx_rule_execution_results_rule_id ON rule_execution_results(rule_id);
CREATE INDEX IF NOT EXISTS idx_rule_execution_results_library_id ON rule_execution_results(library_id);
CREATE INDEX IF NOT EXISTS idx_rule_execution_results_status ON rule_execution_results(status);
CREATE INDEX IF NOT EXISTS idx_rule_execution_results_rule_mode ON rule_execution_results(rule_mode);
CREATE INDEX IF NOT EXISTS idx_rule_execution_results_source ON rule_execution_results(report_id, execution_source);
-- raw_result 字段大，不建索引，仅用于详情展示

-- =============================================
-- 插入预置模板数据
-- =============================================
INSERT INTO governance_rule_templates (id, rule_type, template_name, description, default_condition, applicable_columns)
VALUES
    -- ========== 基础规则类型 ==========
    ('tmpl-null-check', 'null_check', '空值检测', '检测字段是否为空或空字符串', 'column IS NULL OR column = ''''', 'varchar,text,int,bigint,decimal,date,timestamp'),
    ('tmpl-unique', 'unique', '唯一性检测', '检测字段值是否存在重复（应唯一但实际重复）', 'COUNT(column) OVER (PARTITION BY column) = 1', 'varchar,text,int,bigint'),

    -- ========== 格式检测 ==========
    ('tmpl-format-email', 'format', '邮箱格式检测', '检测字段是否符合邮箱格式规范', 'column ~* ''^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$''', 'varchar,text'),
    ('tmpl-format-phone', 'format', '手机号格式检测', '检测字段是否符合中国大陆手机号格式（1开头11位）', 'column ~* ''^1[3-9]\d{9}$''', 'varchar,text'),
    ('tmpl-format-idcard', 'format', '身份证格式检测', '检测字段是否符合中国居民身份证格式', 'column ~* ''^[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]$''', 'varchar,text'),
    ('tmpl-format-url', 'format', 'URL格式检测', '检测字段是否符合URL格式规范', 'column ~* ''^https?://[\w.-]+\.[a-zA-Z]{2,}.*$''', 'varchar,text'),
    ('tmpl-format-postcode', 'format', '邮政编码检测', '检测字段是否符合中国邮政编码格式（6位数字）', 'column ~* ''^\d{6}$''', 'varchar,text'),

    -- ========== 阈值/范围检测 ==========
    ('tmpl-threshold-positive', 'threshold', '正数检测', '检测数值字段值是否为正数（大于0）', 'column > 0', 'int,bigint,decimal,numeric'),
    ('tmpl-threshold-non-negative', 'threshold', '非负数检测', '检测数值字段值是否大于等于0', 'column >= 0', 'int,bigint,decimal,numeric'),
    ('tmpl-threshold-range', 'threshold', '范围检测', '检测数值字段值是否在指定范围内', 'column >= min AND column <= max', 'int,bigint,decimal,numeric'),

    -- ========== 枚举检测 ==========
    ('tmpl-enum-status', 'enum', '状态枚举检测', '检测状态字段值是否在允许的枚举列表中', 'column IN (''pending'',''paid'',''shipped'',''completed'',''cancelled'')', 'varchar,text,int,bigint'),
    ('tmpl-enum-gender', 'enum', '性别枚举检测', '检测性别字段值是否为有效值', 'column IN (''M'',''F'',''Male'',''Female'')', 'varchar,text'),

    -- ========== 长度检测 ==========
    ('tmpl-length-range', 'length_check', '字符串长度检测', '检测字符串字段长度是否在指定范围内', 'LENGTH(column) >= min AND LENGTH(column) <= max', 'varchar,text'),
    ('tmpl-length-min', 'length_check', '最小长度检测', '检测字符串字段长度是否不小于最小值', 'LENGTH(column) >= min_length', 'varchar,text'),
    ('tmpl-length-max', 'length_check', '最大长度检测', '检测字符串字段长度是否不超过最大值', 'LENGTH(column) <= max_length', 'varchar,text'),

    -- ========== 日期检测 ==========
    ('tmpl-date-future', 'date_check', '未来日期检测', '检测日期字段是否存在不合理的未来日期', 'column <= NOW()', 'date,timestamp'),
    ('tmpl-date-past', 'date_check', '过去日期检测', '检测日期字段是否存在不合理的过去日期', 'column >= ''1900-01-01''', 'date,timestamp'),
    ('tmpl-date-logic', 'date_check', '日期逻辑检测', '检测结束日期是否晚于开始日期等逻辑关系', 'end_date >= start_date', 'date,timestamp'),
    ('tmpl-date-reasonable', 'date_check', '日期合理性检测', '检测日期是否在合理范围内（如年龄对应的出生日期）', 'column >= ''1900-01-01'' AND column <= CURRENT_DATE', 'date,timestamp'),

    -- ========== 一致性检测 ==========
    ('tmpl-consistency-field', 'consistency_check', '字段一致性检测', '检测两个相关字段的数据是否一致（如订单总额与明细总额）', 'column1 = column2', 'int,bigint,decimal,numeric'),
    ('tmpl-consistency-reference', 'consistency_check', '引用完整性检测', '检测外键引用的记录是否存在', 'referenced_id IN (SELECT id FROM reference_table)', 'int,bigint'),

    -- ========== 数据新鲜度检测 ==========
    ('tmpl-freshness-days', 'freshness_check', '数据新鲜度检测（天数）', '检测数据是否在指定天数内有更新', 'updated_at >= NOW() - INTERVAL ''{days} days''', 'timestamp,date'),
    ('tmpl-freshness-hours', 'freshness_check', '数据新鲜度检测（小时）', '检测数据是否在指定小时数内有更新', 'updated_at >= NOW() - INTERVAL ''{hours} hours''', 'timestamp'),
    ('tmpl-freshness-realtime', 'freshness_check', '实时数据检测', '检测数据是否在最近1小时内有更新', 'updated_at >= NOW() - INTERVAL ''1 hour''', 'timestamp'),

    -- ========== 值分布检测 ==========
    ('tmpl-distribution-null', 'value_distribution', '空值比例检测', '检测字段空值比例是否超过阈值', '空值比例 < {threshold}%', 'all'),
    ('tmpl-distribution-unique', 'value_distribution', '唯一值比例检测', '检测字段唯一值占总记录数的比例是否合理', '唯一值比例 BETWEEN {min}% AND {max}%', 'varchar,text,int,bigint'),
    ('tmpl-distribution-skew', 'value_distribution', '数据偏度检测', '检测数值字段的分布是否存在严重偏斜', '偏度值在合理范围内', 'int,bigint,decimal,numeric'),

    -- ========== 自定义SQL ==========
    ('tmpl-custom-sql', 'custom_sql', '自定义SQL规则', '用户编写自定义的SQL条件表达式进行检测', '自定义条件表达式', 'all')
ON CONFLICT (id) DO NOTHING;

-- =============================================
-- 6. 报告文件关联表（用于追踪同一报告的所有导出文件）
-- 解决：一份报告可导出多种格式，每次导出生成独立文件，旧文件路径需被追踪以便删除
-- =============================================
CREATE TABLE IF NOT EXISTS governance_report_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),                    -- 文件记录ID
    report_id UUID NOT NULL REFERENCES governance_reports(id) ON DELETE CASCADE,  -- 所属报告ID
    user_id UUID NOT NULL,                                            -- 用户ID（冗余存储，便于清理和查询）
    file_path VARCHAR(512) NOT NULL,                                  -- 文件完整路径
    file_name VARCHAR(255) NOT NULL,                                 -- 文件名（不含路径）
    file_type VARCHAR(20) NOT NULL,                                   -- 文件类型: md, docx, pdf, xlsx
    file_size BIGINT,                                                 -- 文件大小（字节）
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),                      -- 创建时间
    report_name VARCHAR(255)                                            -- 报告名称
);

-- 表注释
COMMENT ON TABLE governance_report_files IS '报告文件关联表 - 追踪同一报告的所有导出文件，解决一份报告多次导出产生多个文件的问题';

-- 字段注释
COMMENT ON COLUMN governance_report_files.id IS '文件记录唯一标识符';
COMMENT ON COLUMN governance_report_files.report_id IS '所属报告ID，删除报告时通过CASCADE级联删除文件记录';
COMMENT ON COLUMN governance_report_files.user_id IS '所属用户ID，冗余存储便于文件清理和权限校验';
COMMENT ON COLUMN governance_report_files.file_path IS '文件完整路径（统一使用正斜杠分隔符）';
COMMENT ON COLUMN governance_report_files.file_name IS '文件名（不含路径），用于显示';
COMMENT ON COLUMN governance_report_files.file_type IS '文件类型: md=Markdown, docx=Word, pdf=PDF, xlsx=Excel';
COMMENT ON COLUMN governance_report_files.file_size IS '文件大小，单位字节';
COMMENT ON COLUMN governance_report_files.created_at IS '文件记录创建时间';
COMMENT ON COLUMN governance_report_files.report_name IS '报告名称（冗余存储，便于文件管理和展示）';

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_report_files_report_id ON governance_report_files(report_id);
CREATE INDEX IF NOT EXISTS idx_report_files_user_id ON governance_report_files(user_id);
CREATE INDEX IF NOT EXISTS idx_report_files_file_type ON governance_report_files(file_type);

CREATE INDEX IF NOT EXISTS idx_table_relationship_governance_report_id
ON "public"."table_relationship" USING btree ("governance_report_id");

CREATE INDEX IF NOT EXISTS idx_table_relationship_card_governance_report_id
ON "public"."table_relationship_card" USING btree ("governance_report_id");