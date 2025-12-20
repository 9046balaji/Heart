"""
Document-Aware Chatbot Integration.

Enables the chatbot to answer questions using patient's
scanned medical documents as context (RAG pattern).

From medical.md Section 5:
"Once structured, the data can feed: Chatbot (contextualized Q&A)"
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import re

logger = logging.getLogger(__name__)


@dataclass
class DocumentContext:
    """Context from a medical document for chatbot."""

    document_id: str
    document_type: str
    summary: str
    key_data: Dict[str, Any]
    relevance_score: float
    source_date: Optional[datetime] = None


@dataclass
class ChatbotContextResult:
    """Result from context retrieval for chatbot."""

    context_text: str
    sources: List[DocumentContext]
    total_documents_searched: int
    query_keywords: List[str]


class ChatbotDocumentContextService:
    """
    Provides document context for chatbot Q&A.

    Implements RAG (Retrieval Augmented Generation) pattern:
    1. User asks question
    2. Find relevant documents
    3. Extract context from documents
    4. Inject context into chatbot prompt
    5. Generate answer with source attribution
    """

    # Keywords for different medical topics
    TOPIC_KEYWORDS = {
        "lab": [
            "lab",
            "test",
            "result",
            "blood",
            "cholesterol",
            "glucose",
            "hdl",
            "ldl",
            "hemoglobin",
            "creatinine",
            "hba1c",
            "triglycerides",
            "panel",
        ],
        "medication": [
            "medication",
            "medicine",
            "drug",
            "prescription",
            "dose",
            "dosage",
            "pill",
            "tablet",
            "capsule",
            "taking",
            "prescribed",
        ],
        "vitals": [
            "heart rate",
            "blood pressure",
            "bp",
            "pulse",
            "temperature",
            "oxygen",
            "vital",
            "vitals",
            "reading",
        ],
        "diagnosis": [
            "diagnosis",
            "condition",
            "disease",
            "disorder",
            "illness",
            "diagnosed",
        ],
        "hospital": [
            "hospital",
            "admission",
            "discharge",
            "inpatient",
            "emergency",
            "er",
        ],
        "risk": [
            "risk",
            "prediction",
            "chance",
            "likelihood",
            "heart disease",
            "cardiovascular",
        ],
    }

    def __init__(self, timeline_service=None, vector_store=None, audit_service=None):
        """
        Initialize chatbot context service.

        Args:
            timeline_service: Patient timeline service
            vector_store: Optional vector store for semantic search
            audit_service: Audit service for logging
        """
        self.timeline = timeline_service
        self.vector_store = vector_store
        self.audit = audit_service

        # In-memory document index (replace with vector DB in production)
        self._document_index: Dict[str, Dict[str, Any]] = {}

        logger.info("ChatbotDocumentContextService initialized")

    def index_document(
        self,
        user_id: str,
        document_id: str,
        document_type: str,
        extracted_data: Dict[str, Any],
        raw_text: str,
    ) -> None:
        """
        Index a document for context retrieval.

        Args:
            user_id: User ID
            document_id: Document ID
            document_type: Type of document
            extracted_data: Structured data extracted from document
            raw_text: Raw OCR text from document
        """
        # Create document summary
        summary = self._generate_document_summary(document_type, extracted_data)

        # Extract keywords
        keywords = self._extract_keywords(document_type, extracted_data, raw_text)

        # Store in index
        if user_id not in self._document_index:
            self._document_index[user_id] = {}

        self._document_index[user_id][document_id] = {
            "document_type": document_type,
            "extracted_data": extracted_data,
            "summary": summary,
            "keywords": keywords,
            "raw_text": raw_text[:5000],  # Limit raw text storage
            "indexed_at": datetime.utcnow(),
        }

        logger.info(f"Indexed document {document_id} for user {user_id}")

    def get_relevant_context(
        self, user_id: str, query: str, top_k: int = 3
    ) -> ChatbotContextResult:
        """
        Get relevant document context for a user query.

        Args:
            user_id: User ID
            query: User's question
            top_k: Number of top relevant documents to return

        Returns:
            ChatbotContextResult with context and sources
        """
        user_docs = self._document_index.get(user_id, {})

        if not user_docs:
            return ChatbotContextResult(
                context_text="",
                sources=[],
                total_documents_searched=0,
                query_keywords=[],
            )

        # Extract query keywords
        query_keywords = self._extract_query_keywords(query)

        # Score documents by relevance
        scored_docs = []
        for doc_id, doc_data in user_docs.items():
            relevance = self._calculate_relevance(query, query_keywords, doc_data)
            if relevance > 0:
                scored_docs.append((doc_id, doc_data, relevance))

        # Sort by relevance
        scored_docs.sort(key=lambda x: x[2], reverse=True)

        # Take top K
        top_docs = scored_docs[:top_k]

        # Build context
        sources = []
        for doc_id, doc_data, relevance in top_docs:
            # Extract query-relevant data
            relevant_data = self._extract_query_relevant_data(
                query, query_keywords, doc_data["extracted_data"]
            )

            sources.append(
                DocumentContext(
                    document_id=doc_id,
                    document_type=doc_data["document_type"],
                    summary=doc_data["summary"],
                    key_data=relevant_data,
                    relevance_score=relevance,
                    source_date=doc_data.get("indexed_at"),
                )
            )

        # Build context text
        context_text = self._build_context_text(sources)

        return ChatbotContextResult(
            context_text=context_text,
            sources=sources,
            total_documents_searched=len(user_docs),
            query_keywords=query_keywords,
        )

    def build_chatbot_prompt(
        self, user_id: str, query: str, base_prompt: Optional[str] = None
    ) -> str:
        """
        Build a complete chatbot prompt with document context.

        Args:
            user_id: User ID
            query: User's question
            base_prompt: Base system prompt (optional)

        Returns:
            Complete prompt with context injected
        """
        # Get relevant context
        context_result = self.get_relevant_context(user_id, query)

        # Build prompt
        prompt_parts = []

        # Base instructions
        if base_prompt:
            prompt_parts.append(base_prompt)
        else:
            prompt_parts.append(
                "You are a helpful healthcare assistant. Answer the user's question "
                "based on their medical documents and health data. Always remind users "
                "to consult their healthcare provider for medical advice."
            )

        # Add context if available
        if context_result.context_text:
            prompt_parts.append("\n--- PATIENT MEDICAL CONTEXT ---")
            prompt_parts.append(context_result.context_text)
            prompt_parts.append("--- END CONTEXT ---\n")
            prompt_parts.append(
                "Use the above context from the patient's medical documents to answer "
                "their question. Cite specific documents when relevant."
            )
        else:
            prompt_parts.append(
                "\nNote: No relevant medical documents found for this query. "
                "Provide general guidance and recommend the user upload relevant documents."
            )

        # Add query
        prompt_parts.append(f"\nUser Question: {query}")

        return "\n".join(prompt_parts)

    def get_document_qa_context(
        self, user_id: str, document_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get context for Q&A about a specific document.

        Args:
            user_id: User ID
            document_id: Specific document to query about

        Returns:
            Document context or None if not found
        """
        user_docs = self._document_index.get(user_id, {})
        doc_data = user_docs.get(document_id)

        if not doc_data:
            return None

        return {
            "document_type": doc_data["document_type"],
            "summary": doc_data["summary"],
            "extracted_data": doc_data["extracted_data"],
            "context_prompt": (
                f"The user is asking about their {doc_data['document_type']}.\n"
                f"Document Summary: {doc_data['summary']}\n"
                f"Key Data: {doc_data['extracted_data']}"
            ),
        }

    def _generate_document_summary(
        self, document_type: str, extracted_data: Dict[str, Any]
    ) -> str:
        """Generate a brief summary of the document."""
        summary_parts = []

        doc_type_display = document_type.replace("_", " ").title()
        summary_parts.append(f"{doc_type_display}")

        if document_type == "lab_report":
            test_results = extracted_data.get("test_results", [])
            if test_results:
                test_names = [t.get("test_name", "") for t in test_results[:5]]
                summary_parts.append(f"containing {len(test_results)} test results")
                summary_parts.append(f"including {', '.join(test_names)}")

        elif document_type == "prescription":
            medications = extracted_data.get("medications", [])
            if medications:
                med_names = [m.get("name", "") for m in medications]
                summary_parts.append(f"for {', '.join(med_names)}")
            prescriber = extracted_data.get("prescriber_name")
            if prescriber:
                summary_parts.append(f"prescribed by {prescriber}")

        elif document_type == "discharge_summary":
            diagnosis = extracted_data.get("discharge_diagnosis")
            if diagnosis:
                summary_parts.append(f"with diagnosis: {diagnosis}")
            hospital = extracted_data.get("hospital_name")
            if hospital:
                summary_parts.append(f"from {hospital}")

        return " ".join(summary_parts)

    def _extract_keywords(
        self, document_type: str, extracted_data: Dict[str, Any], raw_text: str
    ) -> List[str]:
        """Extract searchable keywords from document."""
        keywords = set()

        # Add document type keywords
        keywords.add(document_type.lower())
        keywords.update(document_type.lower().split("_"))

        # Extract from structured data
        if document_type == "lab_report":
            for test in extracted_data.get("test_results", []):
                test_name = test.get("test_name", "").lower()
                keywords.add(test_name)
                keywords.update(test_name.split())

        elif document_type == "prescription":
            for med in extracted_data.get("medications", []):
                med_name = med.get("name", "").lower()
                keywords.add(med_name)

        # Extract from raw text
        words = re.findall(r"\b[a-zA-Z]{3,}\b", raw_text.lower())
        medical_words = [w for w in words if self._is_medical_term(w)]
        keywords.update(medical_words[:50])

        return list(keywords)

    def _extract_query_keywords(self, query: str) -> List[str]:
        """Extract keywords from user query."""
        # Normalize query
        query_lower = query.lower()

        # Find topic matches
        matched_keywords = []
        for topic, topic_keywords in self.TOPIC_KEYWORDS.items():
            for kw in topic_keywords:
                if kw in query_lower:
                    matched_keywords.append(kw)
                    matched_keywords.append(topic)

        # Extract other significant words
        words = re.findall(r"\b[a-zA-Z]{3,}\b", query_lower)
        stop_words = {
            "what",
            "when",
            "where",
            "how",
            "why",
            "the",
            "and",
            "for",
            "are",
            "was",
            "were",
            "been",
            "have",
            "has",
            "had",
            "does",
            "did",
            "can",
            "could",
            "would",
            "should",
            "may",
            "might",
            "will",
            "shall",
            "about",
            "from",
            "with",
            "this",
            "that",
            "these",
            "those",
            "your",
            "you",
            "my",
            "me",
            "tell",
            "show",
        }

        significant_words = [w for w in words if w not in stop_words]
        matched_keywords.extend(significant_words)

        return list(set(matched_keywords))

    def _calculate_relevance(
        self, query: str, query_keywords: List[str], document: Dict[str, Any]
    ) -> float:
        """Calculate relevance score between query and document."""
        score = 0.0

        doc_keywords = set(document.get("keywords", []))
        doc_summary = document.get("summary", "").lower()
        doc_type = document.get("document_type", "")

        # Keyword overlap
        query_kw_set = set(query_keywords)
        overlap = len(query_kw_set & doc_keywords)
        if query_keywords:
            score += (overlap / len(query_keywords)) * 0.5

        # Summary match
        for kw in query_keywords:
            if kw in doc_summary:
                score += 0.1

        # Document type relevance
        query_lower = query.lower()
        type_relevance = {
            "lab_report": ["lab", "test", "result", "blood", "cholesterol"],
            "prescription": ["medication", "medicine", "drug", "prescription", "dose"],
            "discharge_summary": ["hospital", "discharge", "admission", "diagnosis"],
            "medical_bill": ["bill", "cost", "charge", "payment", "insurance"],
        }

        if doc_type in type_relevance:
            for term in type_relevance[doc_type]:
                if term in query_lower:
                    score += 0.2
                    break

        return min(score, 1.0)

    def _extract_query_relevant_data(
        self, query: str, query_keywords: List[str], extracted_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract data relevant to the query."""
        relevant = {}
        query_lower = query.lower()

        # For lab results, find matching tests
        if "test_results" in extracted_data:
            matching_tests = []
            for test in extracted_data["test_results"]:
                test_name = test.get("test_name", "").lower()
                if any(kw in test_name for kw in query_keywords):
                    matching_tests.append(test)
            if matching_tests:
                relevant["matching_tests"] = matching_tests

        # For prescriptions, find matching medications
        if "medications" in extracted_data:
            matching_meds = []
            for med in extracted_data["medications"]:
                med_name = med.get("name", "").lower()
                if (
                    any(kw in med_name for kw in query_keywords)
                    or "medication" in query_lower
                    or "medicine" in query_lower
                ):
                    matching_meds.append(med)
            if matching_meds:
                relevant["medications"] = matching_meds

        # For general queries, include key fields
        for key in ["diagnosis", "discharge_diagnosis", "procedures", "follow_up"]:
            if key in extracted_data:
                relevant[key] = extracted_data[key]

        return relevant

    def _build_context_text(self, sources: List[DocumentContext]) -> str:
        """Build context text from sources."""
        if not sources:
            return ""

        context_parts = []

        for i, source in enumerate(sources, 1):
            context_parts.append(
                f"\n[Document {i}: {source.document_type.replace('_', ' ').title()}]"
            )
            context_parts.append(f"Summary: {source.summary}")

            if source.key_data:
                context_parts.append("Relevant Data:")
                for key, value in source.key_data.items():
                    if isinstance(value, list):
                        context_parts.append(f"  - {key}:")
                        for item in value[:5]:  # Limit items
                            if isinstance(item, dict):
                                item_str = ", ".join(
                                    f"{k}: {v}" for k, v in item.items()
                                )
                                context_parts.append(f"    • {item_str}")
                            else:
                                context_parts.append(f"    • {item}")
                    else:
                        context_parts.append(f"  - {key}: {value}")

        return "\n".join(context_parts)

    def _is_medical_term(self, word: str) -> bool:
        """Check if a word is likely a medical term."""
        medical_suffixes = [
            "emia",
            "itis",
            "osis",
            "ectomy",
            "plasty",
            "gram",
            "graph",
            "scopy",
            "logy",
            "pathy",
        ]
        medical_prefixes = [
            "hyper",
            "hypo",
            "cardio",
            "hemo",
            "hepat",
            "nephro",
            "neuro",
            "gastro",
            "pulmo",
        ]

        word_lower = word.lower()

        for suffix in medical_suffixes:
            if word_lower.endswith(suffix):
                return True

        for prefix in medical_prefixes:
            if word_lower.startswith(prefix):
                return True

        return False


# Global instance
_context_service: Optional[ChatbotDocumentContextService] = None


def get_context_service() -> ChatbotDocumentContextService:
    """Get or create the global context service instance."""
    global _context_service
    if _context_service is None:
        _context_service = ChatbotDocumentContextService()
    return _context_service
