# Technical Implementation Report: Integrating New AI/ML Frameworks into Cardio AI Assistant

## Executive Summary

This report provides a comprehensive technical roadmap for implementing the new AI/ML frameworks identified in the temp.md analysis into the Cardio AI Assistant (HeartGuard) system. The system currently has foundational implementations for all recommended frameworks but lacks proper integration into active production flows. This report outlines how to bridge that gap effectively.

---

## Current State Analysis

Based on the temp.md file analysis, the following frameworks have been implemented but are not actively used in production flows:

- **LangGraph** - Implemented in `agents/langgraph_orchestrator.py` but no endpoints use it
- **CrewAI** - Implemented in `agents/crew_simulation.py` but no endpoints use it
- **Langfuse** - Implemented in `core/observable_llm_gateway.py` as an observability wrapper
- **LangChain** - Partially implemented in `core/langchain_gateway.py` with no import references found
- **LlamaIndex** - Implemented in `rag/llama_index_pipeline.py` with no import references found
- **Unstructured.io** - Implemented in `document_scanning/unstructured_processor.py` with no import references found
- **Ragas** - Implemented in `evaluation/rag_evaluator.py` with no runtime usage

---

## 1. LangGraph Implementation Plan

### Current Implementation Status

The LangGraph orchestrator is fully implemented in `agents/langgraph_orchestrator.py` with the following features:
- Visualizable workflow graphs for debugging
- Built-in checkpointing and persistence
- Improved state management
- Easier addition of new agent types

### Integration Strategy

- **Endpoint Activation**: The framework is already exposed through the `/api/agent/process` endpoint in `main.py` (lines 1026-1063)
- **Replace Legacy Orchestrator**: Modify the existing `agents/orchestrator.py` to delegate complex queries to the LangGraph implementation
- **Routing Logic**: Update the agent routing in `routes/agents.py` to utilize LangGraph for multi-step processing

### Implementation Steps

1. Add LangGraph orchestrator initialization in NLPState (already done in `main.py` lines 310-336)
2. Update the `/api/agents/chat` endpoint in `routes/agents.py` to route complex queries to LangGraph
3. Add configuration options to enable/disable LangGraph processing

### 🔥 Critical Refinement: Semantic Router Pattern (routes/agents.py)

The current `process_nlp` uses a simple `IntentRecognizer`. We need to implement a **Semantic Router** that checks query complexity and routes accordingly:

```python
# routes/agents.py - Semantic Router Implementation

from enum import Enum
from typing import Optional
import os

class IntentEnum(Enum):
    SIMPLE_QUERY = "simple_query"
    COMPLEX_DIAGNOSIS = "complex_diagnosis"
    MULTI_DOMAIN = "multi_domain"
    HEALTH_CHECK = "health_check"
    APPOINTMENT = "appointment"
    MEDICATION = "medication"

class SemanticRouter:
    """Routes queries based on complexity and intent analysis."""
    
    def __init__(self, intent_recognizer, langgraph_orchestrator=None):
        self.intent_recognizer = intent_recognizer
        self.langgraph_orchestrator = langgraph_orchestrator
        self.complexity_threshold = float(os.getenv("COMPLEXITY_THRESHOLD", "0.8"))
    
    def calculate_complexity_score(self, query: str) -> float:
        """
        Calculate query complexity based on multiple factors:
        - Length of query
        - Number of medical terms
        - Presence of multiple symptoms/conditions
        - Question depth indicators
        """
        score = 0.0
        
        # Length factor (longer queries tend to be more complex)
        if len(query) > 200:
            score += 0.3
        elif len(query) > 100:
            score += 0.15
        
        # Medical complexity indicators
        complex_keywords = [
            "diagnosis", "differential", "interaction", "contraindication",
            "prognosis", "etiology", "comorbidity", "treatment plan",
            "multiple symptoms", "history of", "risk factors"
        ]
        for keyword in complex_keywords:
            if keyword.lower() in query.lower():
                score += 0.15
        
        # Multi-domain indicators (cardiac + nutrition + medication)
        domain_indicators = {
            "cardiac": ["heart", "cardiac", "cardiovascular", "arrhythmia", "ecg", "blood pressure"],
            "nutrition": ["diet", "nutrition", "food", "eating", "weight"],
            "medication": ["drug", "medication", "prescription", "dosage", "medicine"]
        }
        domains_present = sum(1 for domain, keywords in domain_indicators.items() 
                            if any(kw in query.lower() for kw in keywords))
        if domains_present >= 2:
            score += 0.3
        
        return min(score, 1.0)  # Cap at 1.0


async def process_nlp(query: str, context: Optional[dict] = None) -> dict:
    """
    Main NLP processing function with semantic routing.
    Routes to LangGraph for complex queries, legacy handler for simple ones.
    """
    from app_state import get_nlp_state
    
    nlp_state = get_nlp_state()
    router = SemanticRouter(
        intent_recognizer=nlp_state.intent_recognizer,
        langgraph_orchestrator=nlp_state.langgraph_orchestrator
    )
    
    # Analyze intent and complexity
    intent = nlp_state.intent_recognizer.recognize(query)
    complexity_score = router.calculate_complexity_score(query)
    
    # Semantic routing decision
    if intent == IntentEnum.COMPLEX_DIAGNOSIS or complexity_score > router.complexity_threshold:
        # Route to LangGraph for complex multi-step processing
        if router.langgraph_orchestrator:
            return await router.langgraph_orchestrator.process(query, context)
        else:
            # Fallback if LangGraph not available
            return await legacy_intent_handler(query, intent, context)
    else:
        # Use legacy handler for simple queries
        return await legacy_intent_handler(query, intent, context)


async def legacy_intent_handler(query: str, intent: IntentEnum, context: Optional[dict] = None) -> dict:
    """
    Legacy intent handler for simple queries.
    Maintains backward compatibility with existing implementation.
    """
    from app_state import get_nlp_state
    nlp_state = get_nlp_state()
    
    response = {
        "query": query,
        "intent": intent.value if isinstance(intent, IntentEnum) else str(intent),
        "response": None,
        "confidence": 0.0
    }
    
    try:
        # Process based on intent type
        if intent in [IntentEnum.SIMPLE_QUERY, IntentEnum.HEALTH_CHECK]:
            result = await nlp_state.llm_gateway.generate(query)
            response["response"] = result
            response["confidence"] = 0.9
        elif intent == IntentEnum.APPOINTMENT:
            response["response"] = "I'll help you schedule an appointment."
            response["confidence"] = 0.95
        elif intent == IntentEnum.MEDICATION:
            result = await nlp_state.llm_gateway.generate(
                f"Provide medication guidance for: {query}"
            )
            response["response"] = result
            response["confidence"] = 0.85
        else:
            result = await nlp_state.llm_gateway.generate(query)
            response["response"] = result
            response["confidence"] = 0.7
            
    except Exception as e:
        response["error"] = str(e)
        response["confidence"] = 0.0
    
    return response
```

---

## 2. CrewAI Implementation Plan

### Current Implementation Status

The CrewAI healthcare simulation is fully implemented in `agents/crew_simulation.py` with:
- Dynamic agent collaboration
- Role-based specialization (Cardiologist, Nutritionist, Pharmacist)
- Delegation and escalation capabilities
- Built-in task management

### Integration Strategy

- **Endpoint Activation**: The framework is already exposed through the `/api/agent/simulate` endpoint in `main.py` (lines 1061-1099)
- **Specialized Use Cases**: Integrate CrewAI for complex healthcare scenarios requiring multi-disciplinary input
- **Trigger Conditions**: Activate CrewAI simulation for queries involving multiple health domains (e.g., medication + diet + symptoms)

### Implementation Steps

1. Add CrewAI initialization in NLPState (already done in `main.py` lines 310-336)
2. Update intent recognition in `routes/agents.py` to identify when CrewAI coordination is needed
3. Add configuration for CrewAI provider selection (Gemini vs Ollama)

---

## 3. Langfuse Observability Implementation Plan

### Current Implementation Status

Langfuse observability is implemented in `core/observable_llm_gateway.py` with:
- Detailed tracing of LLM calls
- Performance monitoring
- Cost tracking
- Debugging capabilities

### Integration Strategy

- **Gateway Integration**: The ObservableLLMGateway is already integrated in the NLPState initialization (`main.py` lines 310-336)
- **Trace Propagation**: Extend tracing to cover the entire request lifecycle from API entry to response
- **Dashboard Integration**: Set up Langfuse dashboard for monitoring LLM performance and costs

### Implementation Steps

1. Configure Langfuse environment variables (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`)
2. Update all LLM calling sites to use the ObservableLLMGateway
3. Add trace context propagation for multi-step workflows
4. Implement custom tracing for critical business logic paths

---

## 4. LlamaIndex RAG Enhancement Plan

### Current Implementation Status

LlamaIndex RAG pipeline is implemented in `rag/llama_index_pipeline.py` with:
- Industry-standard RAG implementation
- Built-in GraphRAG capabilities
- Multiple retrieval strategies
- Advanced indexing options

### Integration Strategy

- **Pipeline Replacement**: Replace the existing custom RAG implementation in `rag/rag_pipeline.py` with LlamaIndex
- **API Endpoint Updates**: Update RAG API endpoints in `rag_api.py` to use LlamaIndex
- **Document Processing**: Integrate LlamaIndex with document ingestion workflows

### Implementation Steps

1. Update `rag_api.py` to instantiate LlamaIndexRAG instead of custom RAGPipeline
2. Add document ingestion endpoints that use LlamaIndex's indexing capabilities
3. Configure embedding models and chunking strategies for medical documents
4. Implement hybrid search combining keyword and semantic search

### 🔥 Critical Refinement: LlamaIndex "Hot Swap" with Feature Flag

Since `main.py` conditionally imports RAG components, use a feature flag to swap the implementation without breaking the API contract:

```python
# rag_api.py - LlamaIndex Hot Swap Implementation

import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/rag", tags=["RAG"])

# Feature flag for LlamaIndex
USE_LLAMA_INDEX = os.getenv("USE_LLAMA_INDEX", "false").lower() == "true"


class RAGQuery(BaseModel):
    query: str
    top_k: int = 5
    filters: Optional[Dict[str, Any]] = None


class RAGResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    confidence: float


def get_rag_pipeline():
    """
    Factory function to get the appropriate RAG pipeline based on feature flag.
    Allows hot-swapping between implementations without code changes.
    """
    if USE_LLAMA_INDEX:
        from rag.llama_index_pipeline import LlamaIndexRAG
        return LlamaIndexRAG()
    else:
        from rag.rag_pipeline import RAGPipeline
        return RAGPipeline()


# Singleton instance - lazy loaded
_rag_instance = None


def get_rag_instance():
    """Get or create the RAG pipeline singleton."""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = get_rag_pipeline()
    return _rag_instance


@router.post("/query", response_model=RAGResponse)
async def query_rag(request: RAGQuery, rag_pipeline = Depends(get_rag_instance)):
    """
    Query the RAG pipeline with semantic search.
    Uses LlamaIndex or custom RAG based on USE_LLAMA_INDEX env var.
    """
    try:
        # Both implementations should expose the same interface
        result = await rag_pipeline.query(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters
        )
        
        return RAGResponse(
            answer=result.get("answer", ""),
            sources=result.get("sources", []),
            confidence=result.get("confidence", 0.0)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query failed: {str(e)}")


@router.post("/ingest")
async def ingest_documents(
    documents: List[Dict[str, Any]],
    rag_pipeline = Depends(get_rag_instance)
):
    """
    Ingest documents into the RAG pipeline.
    Works with both LlamaIndex and custom implementations.
    """
    try:
        result = await rag_pipeline.ingest(documents)
        return {"status": "success", "ingested": result.get("count", len(documents))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document ingestion failed: {str(e)}")


@router.get("/status")
async def get_rag_status():
    """Get current RAG configuration and status."""
    return {
        "implementation": "LlamaIndex" if USE_LLAMA_INDEX else "Custom RAGPipeline",
        "feature_flag": USE_LLAMA_INDEX,
        "status": "active"
    }
```

**Environment Configuration (.env)**:
```bash
# Set to 'true' to use LlamaIndex, 'false' for custom RAGPipeline
USE_LLAMA_INDEX=true
```

---

## 5. Unstructured.io Document Processing Plan

### Current Implementation Status

Unstructured.io document processor is implemented in `document_scanning/unstructured_processor.py` with:
- Handles complex document layouts automatically
- Built-in table and form extraction
- Header/footer removal
- Better text cleaning and normalization

### Integration Strategy

- **OCR Replacement**: Replace the custom OCR engine in `document_scanning/ocr_engine.py` with Unstructured.io
- **Document Routes**: Update document processing endpoints in `routes/document_routes.py`
- **Entity Extraction**: Enhance entity extraction from processed documents

### Implementation Steps

1. Update document scanning routes to use UnstructuredDocumentProcessor
2. Add support for various document formats (PDF, DOCX, images, etc.)
3. Implement entity extraction enhancements using Unstructured's built-in capabilities
4. Add document classification based on content analysis

### 🔥 Critical Refinement: Unstructured.io Fallback with Chain of Responsibility

Replacing the custom OCR engine entirely might be risky due to latency or dependency size. Use the **Chain of Responsibility** pattern:

```python
# routes/document_routes.py - Chain of Responsibility Pattern

import os
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
import logging

router = APIRouter(prefix="/api/documents", tags=["Documents"])
logger = logging.getLogger(__name__)

# Configuration
UNSTRUCTURED_TIMEOUT = float(os.getenv("UNSTRUCTURED_TIMEOUT", "30.0"))
USE_UNSTRUCTURED_FALLBACK = os.getenv("USE_UNSTRUCTURED_FALLBACK", "true").lower() == "true"


class DocumentProcessingResult(BaseModel):
    text: str
    metadata: Dict[str, Any]
    processor_used: str
    entities: List[Dict[str, Any]] = []
    tables: List[Dict[str, Any]] = []
    confidence: float = 0.0


class DocumentProcessor(ABC):
    """Abstract base class for document processors (Chain of Responsibility)."""
    
    def __init__(self):
        self._next_processor: Optional["DocumentProcessor"] = None
    
    def set_next(self, processor: "DocumentProcessor") -> "DocumentProcessor":
        """Set the next processor in the chain."""
        self._next_processor = processor
        return processor
    
    @abstractmethod
    async def can_process(self, file_content: bytes, file_type: str) -> bool:
        """Check if this processor can handle the file."""
        pass
    
    @abstractmethod
    async def process(self, file_content: bytes, file_type: str) -> DocumentProcessingResult:
        """Process the document."""
        pass
    
    async def handle(self, file_content: bytes, file_type: str) -> DocumentProcessingResult:
        """
        Handle the document processing request.
        Try this processor first, fall back to next in chain on failure.
        """
        try:
            if await self.can_process(file_content, file_type):
                return await self.process(file_content, file_type)
        except Exception as e:
            logger.warning(f"{self.__class__.__name__} failed: {e}, trying next processor")
        
        # Fall back to next processor in chain
        if self._next_processor:
            return await self._next_processor.handle(file_content, file_type)
        
        raise HTTPException(status_code=500, detail="All document processors failed")


class UnstructuredProcessor(DocumentProcessor):
    """
    Primary processor using Unstructured.io for high-quality document parsing.
    Handles complex layouts, tables, and forms automatically.
    """
    
    async def can_process(self, file_content: bytes, file_type: str) -> bool:
        """Unstructured.io can handle most document types."""
        supported_types = ["pdf", "docx", "doc", "pptx", "xlsx", "html", "txt", "md", "png", "jpg", "jpeg"]
        return file_type.lower() in supported_types
    
    async def process(self, file_content: bytes, file_type: str) -> DocumentProcessingResult:
        """Process using Unstructured.io with timeout protection."""
        from document_scanning.unstructured_processor import UnstructuredDocumentProcessor
        
        processor = UnstructuredDocumentProcessor()
        
        try:
            # Apply timeout to prevent hanging on large documents
            result = await asyncio.wait_for(
                processor.process_document(file_content, file_type),
                timeout=UNSTRUCTURED_TIMEOUT
            )
            
            return DocumentProcessingResult(
                text=result.get("text", ""),
                metadata=result.get("metadata", {}),
                processor_used="UnstructuredIO",
                entities=result.get("entities", []),
                tables=result.get("tables", []),
                confidence=result.get("confidence", 0.95)
            )
        except asyncio.TimeoutError:
            logger.warning(f"Unstructured.io timed out after {UNSTRUCTURED_TIMEOUT}s")
            raise
        except ImportError as e:
            logger.error(f"Unstructured.io not available: {e}")
            raise


class TesseractOCRProcessor(DocumentProcessor):
    """
    Fallback processor using Tesseract OCR for image-based documents.
    Lighter weight but less feature-rich than Unstructured.io.
    """
    
    async def can_process(self, file_content: bytes, file_type: str) -> bool:
        """Tesseract handles images and PDFs."""
        supported_types = ["pdf", "png", "jpg", "jpeg", "tiff", "bmp"]
        return file_type.lower() in supported_types
    
    async def process(self, file_content: bytes, file_type: str) -> DocumentProcessingResult:
        """Process using legacy Tesseract OCR engine."""
        from document_scanning.ocr_engine import OCREngine
        
        ocr = OCREngine()
        result = await ocr.extract_text(file_content, file_type)
        
        return DocumentProcessingResult(
            text=result.get("text", ""),
            metadata={"source": "tesseract_ocr", "file_type": file_type},
            processor_used="TesseractOCR",
            confidence=result.get("confidence", 0.7)
        )


class SimpleTextProcessor(DocumentProcessor):
    """
    Last-resort processor for plain text files.
    No dependencies, always available.
    """
    
    async def can_process(self, file_content: bytes, file_type: str) -> bool:
        """Text processor handles plain text formats."""
        return file_type.lower() in ["txt", "md", "csv", "json"]
    
    async def process(self, file_content: bytes, file_type: str) -> DocumentProcessingResult:
        """Simple text extraction with encoding detection."""
        import chardet
        
        # Detect encoding
        detected = chardet.detect(file_content)
        encoding = detected.get("encoding", "utf-8")
        
        try:
            text = file_content.decode(encoding)
        except:
            text = file_content.decode("utf-8", errors="ignore")
        
        return DocumentProcessingResult(
            text=text,
            metadata={"encoding": encoding, "file_type": file_type},
            processor_used="SimpleText",
            confidence=0.99
        )


def create_processor_chain() -> DocumentProcessor:
    """
    Create the Chain of Responsibility for document processing.
    Order: Unstructured.io -> Tesseract OCR -> Simple Text
    """
    # Build the chain
    unstructured = UnstructuredProcessor()
    tesseract = TesseractOCRProcessor()
    simple_text = SimpleTextProcessor()
    
    if USE_UNSTRUCTURED_FALLBACK:
        # Full chain: Unstructured -> Tesseract -> Simple
        unstructured.set_next(tesseract).set_next(simple_text)
        return unstructured
    else:
        # Skip Unstructured: Tesseract -> Simple
        tesseract.set_next(simple_text)
        return tesseract


# Global processor chain
_processor_chain: Optional[DocumentProcessor] = None


def get_processor_chain() -> DocumentProcessor:
    """Get or create the processor chain singleton."""
    global _processor_chain
    if _processor_chain is None:
        _processor_chain = create_processor_chain()
    return _processor_chain


@router.post("/process", response_model=DocumentProcessingResult)
async def process_document(file: UploadFile = File(...)):
    """
    Process an uploaded document using the Chain of Responsibility pattern.
    Tries Unstructured.io first, falls back to Tesseract OCR if needed.
    """
    # Get file extension
    file_type = file.filename.split(".")[-1] if "." in file.filename else "txt"
    
    # Read file content
    file_content = await file.read()
    
    # Process through the chain
    processor_chain = get_processor_chain()
    result = await processor_chain.handle(file_content, file_type)
    
    logger.info(f"Document processed by: {result.processor_used}")
    return result


@router.get("/processors/status")
async def get_processors_status():
    """Get status of available document processors."""
    status = {
        "chain_order": [],
        "unstructured_enabled": USE_UNSTRUCTURED_FALLBACK,
        "timeout_seconds": UNSTRUCTURED_TIMEOUT
    }
    
    # Check which processors are available
    try:
        from document_scanning.unstructured_processor import UnstructuredDocumentProcessor
        status["chain_order"].append("UnstructuredIO")
    except ImportError:
        pass
    
    try:
        from document_scanning.ocr_engine import OCREngine
        status["chain_order"].append("TesseractOCR")
    except ImportError:
        pass
    
    status["chain_order"].append("SimpleText")  # Always available
    
    return status
```

**Environment Configuration (.env)**:
```bash
# Unstructured.io settings
USE_UNSTRUCTURED_FALLBACK=true
UNSTRUCTURED_TIMEOUT=30.0
```

---

## 6. Ragas Evaluation Implementation Plan

### Current Implementation Status

Ragas evaluation framework is implemented in `evaluation/rag_evaluator.py` with:
- Automated RAG quality assessment
- Hallucination detection
- Context relevance scoring
- Continuous improvement feedback

### Integration Strategy

- **Evaluation Pipeline**: Integrate Ragas into CI/CD pipeline for automated RAG evaluation
- **Production Monitoring**: Implement continuous evaluation of RAG performance in production
- **Feedback Loop**: Use Ragas metrics to trigger retraining or index updates

### Implementation Steps

1. Set up automated evaluation datasets for cardiovascular health queries
2. Implement scheduled evaluation runs using Ragas
3. Add Ragas metrics to monitoring dashboards
4. Create alerting for performance degradation
5. Implement A/B testing framework for RAG improvements

---

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
- [ ] Activate LangGraph and CrewAI endpoints
- [ ] Configure Langfuse observability
- [ ] **Implement Semantic Router pattern in `routes/agents.py`**
- [ ] Update routing logic to utilize new orchestrators

### Phase 2: RAG Enhancement (Weeks 3-4)
- [ ] **Implement LlamaIndex Hot Swap with feature flag**
- [ ] Replace custom RAG implementation with LlamaIndex
- [ ] **Implement Chain of Responsibility for document processing**
- [ ] Integrate Unstructured.io document processing with fallback
- [ ] Update document scanning workflows

### Phase 3: Evaluation & Monitoring (Weeks 5-6)
- [ ] Deploy Ragas evaluation suite
- [ ] Implement continuous evaluation pipelines
- [ ] Set up monitoring dashboards

---

## Risk Mitigation Strategies

- **Gradual Migration**: Replace components incrementally to minimize disruption
- **Backward Compatibility**: Maintain existing APIs during transition
- **Feature Flags**: Use environment variables for hot-swapping implementations
- **Fallback Patterns**: Chain of Responsibility ensures graceful degradation
- **Comprehensive Testing**: Implement unit and integration tests for all new components
- **Monitoring**: Deploy observability tools before production rollout
- **Documentation**: Update all documentation to reflect new implementations

---

## Expected Benefits

- **Improved Reliability**: Industry-standard frameworks reduce bugs and edge cases
- **Enhanced Observability**: Better debugging and monitoring capabilities
- **Scalability**: More efficient resource utilization and horizontal scaling
- **Maintainability**: Reduced technical debt and easier onboarding
- **Performance**: Optimized algorithms and caching strategies
- **Extensibility**: Easier addition of new features and capabilities
- **Resilience**: Fallback patterns prevent single points of failure

---

## Conclusion

The Cardio AI Assistant system has a solid foundation with all recommended AI/ML frameworks already implemented. The primary task is activating these implementations in production flows and replacing legacy components. 

**Key Integration Patterns Added:**
1. **Semantic Router** - Intelligent query routing based on complexity analysis
2. **Hot Swap with Feature Flags** - Safe LlamaIndex migration with rollback capability
3. **Chain of Responsibility** - Resilient document processing with automatic fallback

The phased approach ensures minimal disruption while progressively modernizing the architecture. The combination of LangGraph for orchestration, LlamaIndex for RAG, and Langfuse for observability provides a robust foundation for a production-grade healthcare AI system.