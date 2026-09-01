"""
@File: datacard_sampling.py
@Description: 数据卡片生成 - 数据采样服务
@Author: 韩小豪 849631113@qq.com
@Create: 2026-08-13

核心能力：
1. 数据库表数据采样（方言适配）
2. AI 驱动的敏感字段识别
3. 字段特征分析（枚举/数值/日期/文本）
"""

# ============================================================
# 采样配置 - 可根据需求调整
# ============================================================

# 每个字段最多采样的 distinct 值数量
# 建议值：50-200（太大可能导致 prompt 过长，太小可能导致分析不准确）
SAMPLING_DISTINCT_LIMIT = 50

# 枚举值阈值：distinct 值数量 <= 此值时判定为枚举型
# 建议值：30-100
ENUM_DISTINCT_THRESHOLD = 50

# 敏感字段采样分析的限制数量（敏感字段只返回 count，不返回实际数据）
SENSITIVE_FIELD_SAMPLE_LIMIT = 10

# ============================================================
# 以下为核心代码
# ============================================================

import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

from controllers.governance.dialect_adapter import DialectAdapter
from models.prompt_config import prompt_manager


@dataclass
class FieldSampleData:
    """字段采样数据"""
    field_name: str
    distinct_values: List[Any] = field(default_factory=list)
    total_count: int = 0
    distinct_count: int = 0


@dataclass
class SensitiveField:
    """敏感字段信息"""
    name: str
    reason: str
    suggested_comment: Optional[str] = None


@dataclass
class NonSensitiveField:
    """非敏感字段分析结果"""
    name: str
    category: str  # enum, numeric, date, text
    can_show_sample: bool
    sample_display: str
    suggested_comment: Optional[str] = None  # 缺失注释时推断的注释
    enum_values: Optional[List[Any]] = None
    enum_meanings: Optional[Dict[str, str]] = None
    statistics: Optional[Dict[str, float]] = None
    range_str: Optional[str] = None


@dataclass
class SamplingAnalysisResult:
    """采样分析结果"""
    sensitive_fields: List[SensitiveField] = field(default_factory=list)
    non_sensitive_fields: Dict[str, NonSensitiveField] = field(default_factory=dict)
    table_summary: Dict[str, Any] = field(default_factory=dict)

    def get_sensitive_field_names(self) -> List[str]:
        """获取敏感字段名列表"""
        return [f.name for f in self.sensitive_fields]

    def is_sensitive(self, field_name: str) -> bool:
        """判断字段是否敏感"""
        return field_name in self.get_sensitive_field_names()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'sensitive_fields': [
                {
                    'name': f.name,
                    'reason': f.reason,
                    'suggested_comment': f.suggested_comment
                }
                for f in self.sensitive_fields
            ],
            'non_sensitive_fields': {
                name: {
                    'category': f.category,
                    'can_show_sample': f.can_show_sample,
                    'sample_display': f.sample_display,
                    'suggested_comment': f.suggested_comment,
                    'enum_values': f.enum_values,
                    'enum_meanings': f.enum_meanings,
                    'statistics': f.statistics,
                    'range': f.range_str
                }
                for name, f in self.non_sensitive_fields.items()
            },
            'table_summary': self.table_summary
        }


class DataCardSamplingService:
    """
    数据卡片采样服务

    负责：
    1. 从数据库采样表数据（方言适配）
    2. 调用 AI 分析敏感字段
    3. 分析字段特征（枚举/数值/日期/文本）
    """

    # ============================================================
    # 敏感字段预过滤配置（分层设计）
    # ============================================================

    # 第一层：极高置信度敏感字段（几乎不会误杀）
    # 这些字段名本身就是敏感信息的直接标识，必须脱敏
    HIGH_CONFIDENCE_SENSITIVE_PATTERNS = [
        # 认证密码类 - 极高敏感
        r'^password$', r'^passwd$', r'^pwd$', r'^pass$',
        r'^login_password$', r'^user_password$', r'^pwd_hash$',
        # 密钥令牌类 - 极高敏感
        r'^secret$', r'^secret_key$', r'^app_secret$', r'^client_secret$',
        r'^private_?key$', r'^private_?secret$',
        r'^token$', r'^access_?token$', r'^refresh_?token$', r'^auth_?token$',
        r'^api_?key$', r'^api_?secret$', r'^api_?token$', r'^apikey$', r'^apikey$',
        r'^auth_?key$', r'^auth_?secret$', r'^credential$', r'^credentials$',
        r'^jwt$', r'^jwt_?token$', r'^bearer$',
        # 身份证号 - 极高敏感
        r'^id_?card$', r'^id_?no$', r'^id_?number$', r'^identity_?card$',
        r'^identity_?no$', r'^cert_?no$', r'^cert_?number$',
        r'^ssn$', r'^social_?security_?no$',
        # 银行卡号 - 极高敏感
        r'^bank_?card$', r'^bank_?card_?no$', r'^card_?no$', r'^card_?number$',
        r'^credit_?card$', r'^credit_?card_?no$', r'^debit_?card$',
        r'^account_?no$', r'^account_?number$', r'^acct_?no$',
        # 密码相关 - 极高敏感
        r'^encrypt_?key$', r'^encrypt_?salt$', r'^salt$',
        r'^hash$', r'^password_?hash$', r'^pwd_?salt$',
    ]

    # 第二层：高置信度敏感字段（误杀概率很低）
    # 这些字段名强烈暗示敏感信息，但在某些业务场景下可能是普通字段
    MEDIUM_CONFIDENCE_SENSITIVE_PATTERNS = [
        # 联系方式类 - 较高敏感（可能误杀电话簿等）
        r'^phone$', r'^mobile$', r'^mobile_?no$', r'^phone_?no$',
        r'^telephone$', r'^tel$', r'^tel_?no$', r'^phone_?num$',
        # 邮箱类 - 较高敏感
        r'^email$', r'^email_?address$', r'^mail$', r'^mail_?addr$',
        r'^e_?mail$', r'^contact_?email$',
        # 财务类 - 较高敏感
        r'^salary$', r'^wage$', r'^bonus$', r'^commission$',
        r'^income$', r'^revenue$', r'^tax$', r'^tax_?amount$',
        r'^balance$', r'^account_?balance$',
        r'^credit_?limit$', r'^debt$', r'^loan$',
        # 生物特征类 - 极高敏感
        r'^face_?data$', r'^face_?feature$', r'^fingerprint$',
        r'^biometric$', r'^iris$', r'^voice_?print$',
        r'^face_?image$', r'^avatar_?data$',
        # 地址位置类 - 中等敏感
        r'^address$', r'^home_?address$', r'^addr$', r'^addr_?detail$',
        r'^location$', r'^gps$', r'^coordinate$', r'^longitude$', r'^latitude$',
        r'^ip_?addr$', r'^ip_?address$', r'^mac_?addr$',
        # 医疗健康类 - 极高敏感
        r'^medical_?record$', r'^diagnosis$', r'^prescription$',
        r'^health_?record$', r'^medical_?history$', r'^病历$', r'^诊断$',
    ]

    # 第三层：需要结合数据内容进一步判断的字段
    # 这些字段名可能是敏感的，也可能是普通的，由 LLM 二次判断
    NEED_LLM_CHECK_PATTERNS = [
        r'^name$', r'^real_?name$', r'^true_?name$',           # 可能真实姓名
        r'^birthday$', r'^birth_?date$', r'^birthdate$',       # 出生日期
        r'^age$', r'^birth_?year$',                            # 年龄/出生年
        r'^gender$', r'^sex$', r'^male$', r'^female$',        # 性别
        r'^nation$', r'^nationality$', r'^ethnicity$',        # 民族/国籍
        r'^id_?type$', r'^cert_?type$',                        # 证件类型
        r'^qq$', r'^wechat$', r'^weibo$', r'^social_?account$',  # 社交账号
    ]

    def __init__(
        self,
        db_type: str,
        schema: str = None,
        sampling_limit: int = SAMPLING_DISTINCT_LIMIT
    ):
        """
        初始化采样服务

        Args:
            db_type: 数据库类型 (postgresql/mysql/mssql/oracle/sqlite/trino/kingbase/oceanbase/dm)
            schema: Schema 名（可选）
            sampling_limit: 每个字段最多采样的 distinct 值数量（默认使用 SAMPLING_DISTINCT_LIMIT）
        """
        self.db_type = db_type.lower()
        self.schema = schema
        self.sampling_limit = sampling_limit
        self.dialect_adapter = DialectAdapter(db_type)

    def sample_table_data(
        self,
        connection,
        table: str,
        columns: List[str]
    ) -> Dict[str, FieldSampleData]:
        """
        从数据库表采样数据

        Args:
            connection: 数据库连接对象（SQLAlchemy 2.0+ Connection 或传统 cursor）
            table: 表名
            columns: 字段名列表

        Returns:
            字段名 -> 采样数据的映射

        Raises:
            SamplingError: 当采样过程出现不可恢复的错误时（如连接失败）
        """
        from sqlalchemy import text

        results = {}

        # 兼容 SQLAlchemy 2.0+ Connection 和传统 cursor
        # SQLAlchemy 2.0+: connection.execute(text(sql))
        # 传统 cursor: connection.cursor()
        use_execute = hasattr(connection, 'execute')

        for col in columns:
            sql = self.dialect_adapter.build_sample_sql_for_column(
                table=table,
                column=col,
                schema=self.schema,
                limit=self.sampling_limit
            )

            try:
                if use_execute:
                    # SQLAlchemy 2.0+ Connection
                    result = connection.execute(text(sql))
                    rows = result.fetchall()
                else:
                    # 传统 cursor
                    with connection.cursor() as cursor:
                        cursor.execute(sql)
                        rows = cursor.fetchall()

                # 提取值
                values = []
                for row in rows:
                    if row and len(row) > 0:
                        value = row[0]
                        if value is not None:
                            values.append(value)

                results[col] = FieldSampleData(
                    field_name=col,
                    distinct_values=values,
                    total_count=len(values),
                    distinct_count=len(set(values))
                )
            except Exception as e:
                # 某些类型可能不支持 DISTINCT（如 JSON、BLOB），跳过
                # 同时捕获方言不兼容导致的语法错误
                print(f"[WARN] 采样字段 {table}.{col} 失败: {str(e)}")
                results[col] = FieldSampleData(
                    field_name=col,
                    distinct_values=[],
                    total_count=0,
                    distinct_count=0
                )

        return results

    def _quick_sensitive_check(self, field_name: str) -> Optional[str]:
        """
        快速判断字段是否敏感（基于字段名模式）

        采用分层预过滤策略：
        1. 第一层：高置信度敏感字段 - 直接判定为敏感
        2. 第二层：中高置信度敏感字段 - 判定为敏感
        3. 第三层：需要 LLM 判断的字段 - 返回 None，让 LLM 二次判断

        Args:
            field_name: 字段名

        Returns:
            敏感原因字符串（高/中置信度），如果需要 LLM 判断则返回 None
        """
        field_lower = field_name.lower()

        # 第一层：极高置信度敏感字段（几乎不会误杀）
        for pattern in self.HIGH_CONFIDENCE_SENSITIVE_PATTERNS:
            if re.match(pattern, field_lower):
                return self._get_sensitive_reason(field_lower, 'high')

        # 第二层：高置信度敏感字段（误杀概率很低）
        for pattern in self.MEDIUM_CONFIDENCE_SENSITIVE_PATTERNS:
            if re.match(pattern, field_lower):
                return self._get_sensitive_reason(field_lower, 'medium')

        # 第三层：需要 LLM 进一步判断的字段
        # 这些字段名可能是敏感的也可能是普通的，不在这里做判断
        for pattern in self.NEED_LLM_CHECK_PATTERNS:
            if re.match(pattern, field_lower):
                return None  # 让 LLM 根据数据内容判断

        return None

    def _get_sensitive_reason(self, field_lower: str, confidence: str) -> str:
        """
        根据字段名和置信度获取敏感原因

        Args:
            field_lower: 小写字段名
            confidence: 置信度 ('high' 或 'medium')

        Returns:
            敏感原因描述
        """
        # 高置信度敏感原因
        high_reasons = {
            'password': '密码字段，必须脱敏',
            'passwd': '密码字段，必须脱敏',
            'pwd': '密码字段，必须脱敏',
            'secret': '密钥字段，必须脱敏',
            'secret_key': '密钥字段，必须脱敏',
            'private_key': '私钥字段，必须脱敏',
            'token': '令牌字段，必须脱敏',
            'api_key': 'API密钥，必须脱敏',
            'credential': '凭证字段，必须脱敏',
            'id_card': '身份证号，必须脱敏',
            'id_card_no': '身份证号，必须脱敏',
            'identity': '身份证号，必须脱敏',
            'ssn': '社保号，必须脱敏',
            'bank_card': '银行卡号，必须脱敏',
            'card_no': '卡号字段，必须脱敏',
            'credit_card': '信用卡号，必须脱敏',
            'account_no': '账号，必须脱敏',
            'encrypt_key': '加密密钥，必须脱敏',
            'hash': '哈希值字段，必须脱敏',
        }

        # 中置信度敏感原因
        medium_reasons = {
            'phone': '手机号，可能包含个人隐私信息',
            'mobile': '手机号，可能包含个人隐私信息',
            'tel': '电话号码，可能包含个人隐私信息',
            'email': '邮箱地址，可能包含个人隐私信息',
            'mail': '邮箱地址，可能包含个人隐私信息',
            'salary': '薪资信息，财务敏感',
            'income': '收入信息，财务敏感',
            'balance': '余额信息，财务敏感',
            'tax': '税务信息，财务敏感',
            'face_data': '人脸数据，生物特征信息',
            'fingerprint': '指纹数据，生物特征信息',
            'biometric': '生物特征信息',
            'address': '地址信息，可能包含个人隐私',
            'location': '位置信息，可能包含个人隐私',
            'gps': 'GPS坐标，位置敏感',
            'ip_addr': 'IP地址，可能关联个人位置',
            'medical_record': '医疗记录，健康敏感',
            'diagnosis': '诊断信息，健康敏感',
        }

        reasons = high_reasons if confidence == 'high' else medium_reasons

        # 精确匹配
        for key, reason in reasons.items():
            if key in field_lower:
                return reason

        # 默认原因
        if confidence == 'high':
            return '根据字段名判定为高敏感字段'
        else:
            return '根据字段名判定为中高敏感字段'

    def analyze_with_ai(
        self,
        table_name: str,
        sampling_data: Dict[str, FieldSampleData],
        llm_client=None,
        missing_comment_fields: List[Dict] = None
    ) -> SamplingAnalysisResult:
        """
        使用 AI 分析采样数据，识别敏感字段和字段特征

        Args:
            table_name: 表名
            sampling_data: 字段采样数据
            llm_client: LLM 客户端（可选，如果不提供则使用 prompt_manager）
            missing_comment_fields: 缺失注释的字段列表

        Returns:
            采样分析结果
        """
        # 构建采样数据 JSON（带预过滤优化）
        # 预过滤策略：
        # 1. 高/中置信度敏感字段：直接标记为敏感，不送 LLM
        # 2. 其他字段：返回采样数据，让 LLM 做完整分析
        sampling_json = {}

        for field_name, data in sampling_data.items():
            # 先进行预过滤检查
            pre_check_result = self._quick_sensitive_check(field_name)

            if pre_check_result:
                # 高/中置信度敏感字段：直接标记为敏感，不送 LLM
                sampling_json[field_name] = {
                    '_sensitive': True,
                    '_reason': pre_check_result,
                    '_count': data.distinct_count
                }
            else:
                # 其他字段：返回采样数据让 LLM 分析
                display_values = []
                for v in data.distinct_values[:20]:
                    if hasattr(v, 'isoformat'):  # datetime, date 等
                        display_values.append(v.isoformat())
                    elif isinstance(v, (int, float, str, bool, type(None))):
                        display_values.append(v)
                    else:
                        # Decimal, bytes 等转为字符串
                        display_values.append(str(v))
                sampling_json[field_name] = display_values

        # 构建 Prompt - 优先从数据库读取
        prompt_template = prompt_manager.get_prompt(
            "datacard_sample_prompt.txt",
            use_cache=False  # 不使用缓存，确保读取最新
        )

        if not prompt_template:
            # 回退到文件读取
            from pathlib import Path
            prompt_file = Path(__file__).resolve().parent.parent.parent / "libs" / "prompt" / "datacard_generate" / "datacard_sample_prompt.txt"
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    prompt_template = f.read()
            else:
                # 使用简化逻辑
                return self._simple_analysis(sampling_data)

        # 替换模板变量
        prompt = prompt_template
        prompt = prompt.replace('{{table_name}}', table_name)
        prompt = prompt.replace('{{schema_name}}', self.schema or 'default')
        prompt = prompt.replace('{{db_type}}', self.db_type)
        prompt = prompt.replace('{{sampling_data_json}}', json.dumps(sampling_json, ensure_ascii=False, indent=2))

        # 替换缺失注释字段列表
        if missing_comment_fields:
            missing_fields_str = '\n'.join([
                f"- {f['name']} ({f['type']}) - 示例数据: {sampling_json.get(f['name'], [])}"
                for f in missing_comment_fields
            ])
        else:
            missing_fields_str = "无"
        prompt = prompt.replace('{{missing_comment_fields}}', missing_fields_str)

        # 调用 LLM
        if llm_client and hasattr(llm_client, 'chat'):
            response = llm_client.chat(prompt)
        else:
            # 没有 LLM 客户端时使用简单分析
            print(f"[INFO] 采样分析: 使用简单分析模式（无 LLM）")
            return self._simple_analysis(sampling_data)

        # 解析响应
        return self._parse_analysis_response(response, sampling_data)

    def _parse_analysis_response(
        self,
        response: str,
        sampling_data: Dict[str, FieldSampleData]
    ) -> SamplingAnalysisResult:
        """
        解析 AI 分析响应

        Args:
            response: AI 响应文本
            sampling_data: 原始采样数据

        Returns:
            解析后的分析结果
        """
        try:
            # 提取 JSON（可能包含在 markdown 代码块中）
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析整个响应
                json_str = response

            result = json.loads(json_str)

            # 解析敏感字段
            sensitive_fields = []
            for item in result.get('sensitive_fields', []):
                sensitive_fields.append(SensitiveField(
                    name=item['name'],
                    reason=item.get('reason', ''),
                    suggested_comment=item.get('suggested_comment')
                ))

            # 解析非敏感字段
            non_sensitive_fields = {}
            for name, info in result.get('non_sensitive_fields', {}).items():
                non_sensitive_fields[name] = NonSensitiveField(
                    name=name,
                    category=info.get('category', 'text'),
                    can_show_sample=info.get('can_show_sample', True),
                    sample_display=info.get('sample_display', ''),
                    suggested_comment=info.get('suggested_comment'),
                    enum_values=info.get('enum_values'),
                    enum_meanings=info.get('enum_meanings'),
                    statistics=info.get('statistics'),
                    range_str=info.get('range')
                )

            # 解析表摘要
            table_summary = result.get('table_summary', {})

            return SamplingAnalysisResult(
                sensitive_fields=sensitive_fields,
                non_sensitive_fields=non_sensitive_fields,
                table_summary=table_summary
            )

        except json.JSONDecodeError as e:
            print(f"[WARN] 解析 AI 响应失败: {str(e)}")
            # 使用简单逻辑作为回退
            return self._simple_analysis(sampling_data)

    def _simple_analysis(
        self,
        sampling_data: Dict[str, FieldSampleData]
    ) -> SamplingAnalysisResult:
        """
        简单的分析逻辑（当 AI 调用失败时的回退方案）

        Args:
            sampling_data: 字段采样数据

        Returns:
            简单的分析结果
        """
        sensitive_fields = []
        non_sensitive_fields = {}

        for field_name, data in sampling_data.items():
            # 快速检查敏感字段
            quick_reason = self._quick_sensitive_check(field_name)
            if quick_reason:
                sensitive_fields.append(SensitiveField(
                    name=field_name,
                    reason=quick_reason
                ))
            else:
                # 简单分类
                sample_values = data.distinct_values
                if not sample_values:
                    category = 'text'
                    sample_display = '(无数据)'
                else:
                    # 转换 datetime 为字符串
                    str_values = []
                    for v in sample_values:
                        if hasattr(v, 'isoformat'):  # datetime, date
                            str_values.append(v.isoformat())
                        else:
                            str_values.append(str(v))

                    # 检查是否都是数字
                    numeric_values = [v for v in sample_values if isinstance(v, (int, float))]

                    if len(str_values) <= 10 and len(numeric_values) != len(str_values):
                        # 值数量少且不完全是数字 -> 枚举
                        category = 'enum'
                        sample_display = ', '.join(str(v) for v in str_values[:10])
                    elif len(numeric_values) == len(str_values) and len(numeric_values) > 0:
                        # 全部是数字 -> 数值
                        category = 'numeric'
                        sample_display = f"{min(numeric_values):.2f} ~ {max(numeric_values):.2f}"
                    else:
                        # 检查是否为日期
                        date_pattern = r'^\d{4}-\d{2}-\d{2}'
                        if all(re.match(date_pattern, str(v)) for v in str_values[:3] if v):
                            category = 'date'
                            sample_display = f"{min(str_values)} ~ {max(str_values)}"
                        else:
                            category = 'text'
                            sample_display = ', '.join(str(v)[:30] for v in str_values[:3])

                non_sensitive_fields[field_name] = NonSensitiveField(
                    name=field_name,
                    category=category,
                    can_show_sample=True,
                    sample_display=sample_display
                )

        total_count = len(sampling_data)
        sensitive_count = len(sensitive_fields)

        return SamplingAnalysisResult(
            sensitive_fields=sensitive_fields,
            non_sensitive_fields=non_sensitive_fields,
            table_summary={
                'sensitive_count': sensitive_count,
                'total_count': total_count,
                'sensitivity_ratio': f"{sensitive_count}/{total_count}"
            }
        )

    def get_sample_data_for_llm(
        self,
        analysis_result: SamplingAnalysisResult,
        sampling_data: Dict[str, FieldSampleData]
    ) -> Dict[str, Any]:
        """
        获取供 LLM 使用的数据采样上下文

        整合分析结果和原始采样数据，生成供数据卡片生成和字段注释填充使用的上下文。

        Args:
            analysis_result: 采样分析结果
            sampling_data: 原始采样数据

        Returns:
            供 LLM 使用的上下文数据
        """
        sensitive_field_names = analysis_result.get_sensitive_field_names()

        # 构建采样数据上下文
        sample_context = {}

        for field_name, data in sampling_data.items():
            if field_name in sensitive_field_names:
                # 敏感字段：不返回实际数据
                sample_context[field_name] = {
                    'is_sensitive': True,
                    'sensitive_reason': next(
                        (f.reason for f in analysis_result.sensitive_fields if f.name == field_name),
                        ''
                    ),
                    'sample_count': data.distinct_count
                }
            elif field_name in analysis_result.non_sensitive_fields:
                # 非敏感字段：返回分析结果
                analysis = analysis_result.non_sensitive_fields[field_name]
                sample_context[field_name] = {
                    'is_sensitive': False,
                    'category': analysis.category,
                    'sample_display': analysis.sample_display,
                    'enum_values': analysis.enum_values,
                    'enum_meanings': analysis.enum_meanings,
                    'statistics': analysis.statistics,
                    'range': analysis.range_str
                }
            else:
                # 未知字段：返回原始采样数据（截断）
                sample_context[field_name] = {
                    'is_sensitive': False,
                    'category': 'text',
                    'sample_display': ', '.join(str(v)[:20] for v in data.distinct_values[:3])
                }

        return {
            'sensitive_fields': sensitive_field_names,
            'sample_data': sample_context
        }


def sample_and_analyze(
    connection,
    db_type: str,
    table: str,
    schema: str,
    columns: List[Dict],
    llm_client=None,
    sampling_limit: int = SAMPLING_DISTINCT_LIMIT
) -> SamplingAnalysisResult:
    """
    便捷函数：采样并分析表数据

    Args:
        connection: 数据库连接
        db_type: 数据库类型
        table: 表名
        schema: Schema 名
        columns: 字段列表（包含 name, type, comment 等信息）
        llm_client: LLM 客户端
        sampling_limit: 采样限制（默认使用 SAMPLING_DISTINCT_LIMIT）

    Returns:
        采样分析结果
    """
    service = DataCardSamplingService(
        db_type=db_type,
        schema=schema,
        sampling_limit=sampling_limit
    )

    # 提取字段名列表
    column_names = [col.get('name', '') for col in columns]

    # 识别缺失注释的字段
    missing_comment_fields = [
        {
            'name': col.get('name'),
            'type': col.get('type'),
            'comment': ''
        }
        for col in columns
        if not (col.get('comment') or '').strip()
    ]

    # 采样数据
    sampling_data = service.sample_table_data(connection, table, column_names)

    # AI 分析（传入缺失注释的字段信息）
    analysis_result = service.analyze_with_ai(
        table, sampling_data, llm_client, missing_comment_fields
    )

    return analysis_result
