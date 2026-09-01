from weaviate import WeaviateClient
from weaviate.connect import ConnectionParams  # ✅ 4.x 正确导入方式

from config import Weaviate_url


def init_app(app):
    client = WeaviateClient(ConnectionParams.from_url(Weaviate_url, grpc_port=50051))  # ✅ 确保传入 gRPC 端口
    client.connect()  # ✅ 4.x 版本必须手动连接
    app.extensions['weaviate'] = client  # 存入 Flask 扩展