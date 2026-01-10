"""
NLP Debug Routes
================
Endpoints for visualizing and debugging the NLP pipeline.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import spacy
from spacy import displacy
import logging

from core.services.spacy_service import get_spacy_service

router = APIRouter()
logger = logging.getLogger(__name__)

class VisualizeRequest(BaseModel):
    text: str
    style: str = "ent"  # "ent" or "dep"
    minify: bool = True

@router.post("/visualize", response_class=HTMLResponse)
async def visualize_text(request: VisualizeRequest):
    """
    Render spaCy visualization for text.
    
    Args:
        text: Text to analyze
        style: Visualization style ("ent" for entities, "dep" for dependencies)
    """
    try:
        service = get_spacy_service()
        doc = service.process(request.text)
        
        options = {}
        if request.style == "ent":
            # Custom colors for medical entities
            colors = {
                "DRUG": "#f08080",      # Light Coral
                "MEDICATION": "#f08080",
                "DOSAGE": "#add8e6",    # Light Blue
                "DISEASE": "#90ee90",   # Light Green
                "CONDITION": "#90ee90",
                "SYMPTOM": "#ffb6c1",   # Light Pink
                "PROBLEM": "#ffb6c1",
            }
            options = {"colors": colors}
            
        html = displacy.render(
            doc, 
            style=request.style, 
            page=True, 
            minify=request.minify,
            options=options
        )
        return html
        
    except Exception as e:
        logger.error(f"Visualization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pipeline/info")
async def get_pipeline_info():
    """Get information about the active NLP pipeline."""
    service = get_spacy_service()
    nlp = service.nlp
    
    return {
        "model": nlp.meta["name"],
        "version": nlp.meta["version"],
        "pipeline": nlp.pipe_names,
        "tokenizer": str(type(nlp.tokenizer)),
    }

@router.post("/tokenize")
async def inspect_tokens(request: VisualizeRequest):
    """Inspect how text is tokenized."""
    service = get_spacy_service()
    doc = service.process(request.text)
    
    tokens = []
    for token in doc:
        tokens.append({
            "text": token.text,
            "lemma": token.lemma_,
            "pos": token.pos_,
            "dep": token.dep_,
            "is_alpha": token.is_alpha,
            "is_stop": token.is_stop,
        })
        
    return {"tokens": tokens}
