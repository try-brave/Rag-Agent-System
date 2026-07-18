"""服务层包声明。

这里故意不做 eager import，避免子模块之间产生循环依赖。
具体服务请按需从各自模块直接导入，例如：

- `from app.services.document_service import DocumentService`
- `from app.services.ocr_service import OCRService`
"""

__all__ = ['document_service', 'chunk_service', 'retrieval_service', 'chat_service', 'ocr_service']
