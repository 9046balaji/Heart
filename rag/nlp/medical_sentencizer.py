"""
Medical Sentencizer
===================
Custom sentence segmentation for medical text.
Handles abbreviations (Dr., mg., etc.) and vital signs (120/80) that confuse standard splitters.
"""

from spacy.language import Language
from spacy.tokens import Doc

@Language.component("medical_sentencizer")
def medical_sentencizer(doc: Doc) -> Doc:
    """Custom sentencizer that handles medical abbreviations."""
    
    # Medical abbreviations that shouldn't end sentences
    MEDICAL_ABBREVS = {
        "dr", "mr", "mrs", "ms", "vs", "mg", "ml", "mcg", "kg",
        "hr", "min", "sec", "qt", "qd", "bid", "tid", "qid",
        "prn", "po", "iv", "im", "sq", "sl", "pr", "os", "ou",
        "od", "etc", "e.g", "i.e", "approx", "pt", "dx", "rx",
        "hx", "sx", "tx", "bx", "fx", "no"
    }
    
    for i, token in enumerate(doc[:-1]):
        # Check for abbreviation
        is_abbrev = False
        if token.text.lower() in MEDICAL_ABBREVS:
            is_abbrev = True
        elif token.text == "." and i > 0 and doc[i-1].text.lower() in MEDICAL_ABBREVS:
            is_abbrev = True
            
        # Don't split after medical abbreviations
        if is_abbrev:
            doc[token.i + 1].is_sent_start = False
            
        # Don't split in middle of vital readings (e.g., "120/80 mmHg")
        elif token.text == "/" and token.i > 0:
            if doc[token.i - 1].like_num and doc[token.i + 1].like_num:
                doc[token.i + 1].is_sent_start = False
                
    return doc
