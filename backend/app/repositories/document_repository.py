"""Repository for persisting and querying processed documents."""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.app.models.document import ProcessedDocument
from backend.app.core.logging import logger


class DocumentRepository:
    """Encapsulates database access operations for ProcessedDocument records."""

    def __init__(self, db: Session):
        self.db = db

    def save(self, doc: ProcessedDocument) -> ProcessedDocument:
        """Persists a new or updated document record."""
        try:
            self.db.add(doc)
            self.db.commit()
            self.db.refresh(doc)
            return doc
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to persist document '{doc.document_name}': {e}")
            raise e

    def get_latest_by_name(self, document_name: str) -> Optional[ProcessedDocument]:
        """
        Retrieves the latest structured result matching document_name.
        Returns None if no matching record is found.
        """
        return (
            self.db.query(ProcessedDocument)
            .filter(ProcessedDocument.document_name == document_name)
            .order_by(desc(ProcessedDocument.created_at))
            .first()
        )

    def get_by_id(self, doc_id: int) -> Optional[ProcessedDocument]:
        """Retrieves a document record by primary key."""
        return self.db.query(ProcessedDocument).filter(ProcessedDocument.id == doc_id).first()

    def list_documents(
        self,
        skip: int = 0,
        limit: int = 100,
        document_type: Optional[str] = None
    ) -> List[ProcessedDocument]:
        """Returns paginated processed documents, latest first."""
        query = self.db.query(ProcessedDocument)
        if document_type:
            query = query.filter(ProcessedDocument.document_type == document_type)
        return query.order_by(desc(ProcessedDocument.created_at)).offset(skip).limit(limit).all()

    def delete(self, doc_id: int) -> bool:
        """Deletes a document record by id."""
        doc = self.get_by_id(doc_id)
        if doc:
            self.db.delete(doc)
            self.db.commit()
            return True
        return False
