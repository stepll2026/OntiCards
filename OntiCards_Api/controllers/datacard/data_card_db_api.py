"""
 @File: data_card_db_api.py
 @Description: 数据卡片入库工具类 postgre
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-09-17 16:21
"""

from extensions.ext_database import db
from models.datacards_datasource import DataCardDataSource

def add_data_card(doc_id: str, w_uuid: str, card_data_str: str,
                  user_id: str = None, datasource_id: str = None,
                  table_name: str = None, connect_name: str = None) -> dict:
    """
    新增数据卡

    Args:
        doc_id: 文档ID
        w_uuid: Weaviate UUID
        card_data_str: 卡片数据（JSON字符串）
        user_id: 用户ID（可选，用于快速查询）
        datasource_id: 数据源ID（可选，用于快速查询）
        table_name: 表名（可选，用于快速查询）
        connect_name: 连接名称（可选，便于显示）
    """
    card = DataCardDataSource(
        doc_id=str(doc_id),
        w_uuid=w_uuid,
        card_data=card_data_str,
        user_id=user_id,
        datasource_id=datasource_id,
        table_name=table_name,
        connect_name=connect_name
    )
    db.session.add(card)
    print("card:"+str(card.to_dict()))
    try:
        db.session.commit()
        return card.to_dict()
    except Exception as e:
        db.session.rollback()
        raise e

def delete_records_by_ids(ids: list) -> bool:
    """
    根据 id 列表删除 DataCardDataSource 表中的记录
    :param ids: 要删除的记录的 id 列表
    :return: True 如果成功，False 如果失败
    """
    try:
        # 获取数据库会话
        session = db.session  # 使用当前的数据库会话

        # 遍历 ids 列表，逐一删除记录
        for record_id in ids:
            record = DataCardDataSource.query.filter_by(doc_id=record_id).first()  # 查找记录
            if record:
                session.delete(record)  # 删除该记录
                print(f"已删除记录 doc_id: {record_id}")
            else:
                print(f"未找到 doc_id 为 {record_id} 的记录")

        session.commit()  # 提交事务
        print(f"共删除 {len(ids)} 条记录")
        return True

    except Exception as e:
        session.rollback()  # 回滚事务
        print(f"删除失败: {e}")
        return False

def get_data_card_by_doc_id(doc_id: str) -> dict | None:
    """
    根据 doc_id 查询单个数据卡
    """
    card = db.session.query(DataCardDataSource).filter_by(doc_id=str(doc_id)).first()
    return card.to_dict() if card else None