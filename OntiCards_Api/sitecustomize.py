"""
 @File: sitecustomize.py
 @Description: 屏蔽项目启动无关警告
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-09-15 17:26
"""

# sitecustomize.py  —— Python 启动时会自动导入
import warnings
warnings.filterwarnings(
    "ignore",
    message=r"pkg_resources is deprecated as an API",
    category=UserWarning
)