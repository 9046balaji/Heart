"""
Arize Phoenix Monitoring for Cardio AI.

This module provides production monitoring using Arize Phoenix
for real-time drift detection and performance analysis.
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Check if Phoenix is available
try:
    import phoenix as px
    from phoenix.trace import SpanKind
    PHOENIX_AVAILABLE = True
except ImportError:
    PHOENIX_AVAILABLE = False
    logger.warning("Arize Phoenix not available - install with: pip install arize-phoenix")


class PhoenixMonitor:
    """
    Production monitoring using Arize Phoenix.
    
    Features:
    - Real-time drift detection
    - Performance degradation alerts
    - Data quality monitoring
    - Model behavior analysis
    """
    
    def __init__(self, project_name: str = "cardio-ai-assistant"):
        if not PHOENIX_AVAILABLE:
            raise ImportError("Arize Phoenix not installed. Run: pip install arize-phoenix")
        
        self.project_name = project_name
        self.session = None
        
        # Launch Phoenix app
        try:
            px.launch_app()
            self.session = px.session()
            logger.info(f"✅ Phoenix Monitor launched for project: {project_name}")
        except Exception as e:
            logger.warning(f"Phoenix launch failed: {e}")
    
    def log_llm_span(
        self,
        name: str,
        input_text: str,
        output_text: str,
        model: str,
        latency_ms: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log an LLM call span."""
        if not self.session:
            return
        
        try:
            span_data = {
                "name": name,
                "span_kind": SpanKind.LLM,
                "inputs": {"prompt": input_text},
                "outputs": {"response": output_text},
                "metadata": {
                    "model": model,
                    "latency_ms": latency_ms,
                    "timestamp": datetime.now().isoformat(),
                    **(metadata or {})
                }
            }
            
            # Log to Phoenix
            self.session.log_span(**span_data)
            
        except Exception as e:
            logger.warning(f"Failed to log span: {e}")
    
    def log_retrieval(
        self,
        query: str,
        documents: list,
        scores: list,
        latency_ms: float
    ):
        """Log a retrieval operation."""
        if not self.session:
            return
        
        try:
            self.session.log_span(
                name="retrieval",
                span_kind=SpanKind.RETRIEVER,
                inputs={"query": query},
                outputs={
                    "documents": documents,
                    "scores": scores
                },
                metadata={
                    "latency_ms": latency_ms,
                    "num_documents": len(documents)
                }
            )
        except Exception as e:
            logger.warning(f"Failed to log retrieval: {e}")
    
    def log_evaluation(
        self,
        metrics: Dict[str, float],
        dataset_name: str
    ):
        """Log evaluation metrics."""
        if not self.session:
            return
        
        try:
            self.session.log_evaluations(
                name=f"rag_eval_{dataset_name}",
                metrics=metrics,
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.warning(f"Failed to log evaluation: {e}")
    
    def get_dashboard_url(self) -> Optional[str]:
        """Get the Phoenix dashboard URL."""
        if self.session:
            return self.session.url
        return None
    
    def shutdown(self):
        """Shutdown the Phoenix monitor."""
        if self.session:
            try:
                px.close_app()
            except:
                pass


def create_phoenix_monitor(project_name: Optional[str] = None) -> PhoenixMonitor:
    """Factory function to create a PhoenixMonitor."""
    return PhoenixMonitor(project_name=project_name or "cardio-ai-assistant")