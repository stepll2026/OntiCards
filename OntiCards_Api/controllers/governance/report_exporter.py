"""
@File: report_exporter.py
@Description: 报告导出辅助 - 仅提供导出文件删除能力。
              报告文档的生成（PDF/Excel/Markdown/DOCX）统一由
              controllers.governance.libreoffice_exporter.LibreOfficeExporter
              和 controllers.governance.markdown_exporter.MarkdownExporter 承担。
@Author: 韩小豪 849631113@qq.com
@Create: 2026-06-01
"""

import os


class ReportExporter:
    """报告导出辅助类（仅提供文件清理能力，文档生成由 LibreOfficeExporter 负责）"""

    @staticmethod
    def delete_export_file(file_path: str) -> bool:
        """删除导出文件

        Args:
            file_path: 文件路径

        Returns:
            是否删除成功
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception:
            return False
