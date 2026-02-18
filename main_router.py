import logging
import time
from rag.rag_engines import HeartDiseaseRAG
from core.llm.medgemma_service import MedGemmaService
from tools.openfda import get_safety_service

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)



# ═══════════════════════════════════════════════════════════════════════════
# SAFETY SERVICE HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def extract_drug_name(query: str) -> str:
    """
    Extract drug name from user query with improved NLP heuristics.
    
    Uses multiple strategies to identify drug names:
    1. Capitalized words (proper nouns - like "Lipitor", "Warfarin")
    2. Contextual keywords (words after "taking", "drug", "medication")
    3. Multi-word drug names (like "High Blood Pressure")
    4. Common drug name patterns
    
    Args:
        query: User's natural language query
        
    Returns:
        Extracted drug name or empty string
    """
    # Context keywords that precede drug names
    context_keywords = {
        'taking': 1,
        'took': 1,
        'take': 1,
        'medication': 1,
        'medicine': 1,
        'drug': 1,
        'called': 1,
        'named': 1,
        'prescription': 1,
        'prescribed': 1,
    }
    
    # Common words to skip
    skip_words = {
        'the', 'is', 'a', 'an', 'are', 'of', 'and', 'or', 'take', 'taking',
        'causes', 'cause', 'side', 'effects', 'about', 'what', 'does',
        'do', 'i', 'you', 'me', 'him', 'her', 'it', 'they', 'we',
        'be', 'have', 'has', 'had', 'will', 'would', 'can', 'could',
        'should', 'may', 'might', 'safe', 'dangerous', 'risk', 'adverse',
        'if', 'from', 'with', 'for', 'on', 'in', 'at', 'by', 'to',
        'interactions', 'interactions', 'my', 'his', 'her', 'their',
    }
    
    words = query.split()
    
    # Strategy 1: Look for capitalized words (proper nouns - drug names)
    for i, word in enumerate(words):
        clean_word = word.strip('.,!?;:')
        if clean_word and len(clean_word) > 2:
            # Check if it's a capitalized word (proper noun)
            if clean_word[0].isupper() and clean_word.lower() not in skip_words:
                return clean_word
    
    # Strategy 2: Look for words following context keywords
    for i, word in enumerate(words):
        if word.lower() in context_keywords and i + 1 < len(words):
            next_word = words[i + 1].strip('.,!?;:')
            if next_word and len(next_word) > 2 and next_word.lower() not in skip_words:
                return next_word.capitalize()
    
    # Strategy 3: Look for any significant word that's not a common word
    for word in words:
        clean_word = word.strip('.,!?;:')
        if (clean_word and 
            len(clean_word) > 3 and 
            clean_word.lower() not in skip_words and
            not clean_word.lower() in ['medication', 'medicine', 'drug', 'pill', 'tablet']):
            return clean_word.capitalize()
    
    return ""


def extract_food_product(query: str) -> str:
    """
    Extract food product name from user query.
    
    Args:
        query: User's natural language query
        
    Returns:
        Extracted food product name or empty string
    """
    skip_words = {'the', 'is', 'a', 'an', 'are', 'of', 'and', 'or', 'food',
                  'recall', 'recalled', 'safe', 'about', 'what', 'does', 'do',
                  'is', 'it', 'any', 'have', 'has', 'eat', 'eating'}
    
    words = query.lower().split()
    
    for word in words:
        clean_word = word.strip('.,!?;:')
        if clean_word and clean_word not in skip_words and len(clean_word) > 2:
            return clean_word.capitalize()
    
    return ""


def should_query_safety_service(query: str) -> bool:
    """
    Detect if query should be routed to OpenFDA safety service.
    
    Args:
        query: User's natural language query
        
    Returns:
        True if query relates to drug/food safety
    """
    safety_keywords = [
        'side effect', 'adverse', 'reaction', 'safe', 'dangerous', 'risky',
        'recall', 'recalled', 'contamination', 'allerg', 'peanut', 'milk',
        'egg', 'soy', 'wheat', 'fish', 'severe', 'hospitalization', 'death',
        'dangerous', 'supplement', 'vitamin', 'food', 'risk', 'warning',
        'fda', 'drug', 'medication', 'medicine', 'pill', 'tablet'
    ]
    
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in safety_keywords)


def process_safety_query(query: str, safety_service) -> str:
    """
    Process a safety-related query using OpenFDA services.
    
    Args:
        query: User's natural language query
        safety_service: OpenFDASafetyService instance
        
    Returns:
        Safety information from OpenFDA
    """
    query_lower = query.lower()
    
    # Side effects queries
    if any(kw in query_lower for kw in ['side effect', 'adverse', 'reaction']):
        drug_name = extract_drug_name(query)
        if drug_name:
            return f"**OpenFDA Data:** {safety_service.get_drug_side_effects(drug_name)}"
    
    # Safety/severity queries
    if any(kw in query_lower for kw in ['safe', 'dangerous', 'risk', 'severe']):
        drug_name = extract_drug_name(query)
        if drug_name:
            return f"**OpenFDA Data:** {safety_service.check_drug_severity(drug_name)}"
    
    # Drug recall queries
    if any(kw in query_lower for kw in ['recall', 'recalled']) and 'food' not in query_lower:
        drug_name = extract_drug_name(query)
        if drug_name:
            return f"**OpenFDA Data:** {safety_service.check_drug_recalls(drug_name)}"
    
    # Food recall queries
    if any(kw in query_lower for kw in ['food recall', 'contaminated', 'contamination']) and 'drug' not in query_lower:
        product_name = extract_food_product(query)
        if product_name:
            return f"**OpenFDA Data:** {safety_service.check_food_recalls(product_name)}"
    
    # Allergen queries
    if any(kw in query_lower for kw in ['allerg', 'peanut', 'milk', 'egg', 'soy', 'wheat', 'fish']):
        allergen_keywords = ['peanut', 'milk', 'egg', 'soy', 'wheat', 'fish', 'crustacean', 'sesame']
        for allergen in allergen_keywords:
            if allergen in query_lower:
                return f"**OpenFDA Data:** {safety_service.check_allergen_recalls(allergen.capitalize())}"
    
    # Supplement/food adverse events
    if any(kw in query_lower for kw in ['supplement', 'adverse event', 'health risk']):
        product_name = extract_food_product(query)
        if product_name:
            return f"**OpenFDA Data:** {safety_service.check_food_adverse_events(product_name)}"
    
    return None


import asyncio

async def main_async():
    print("\n" + "="*60)
    print("   ❤️  HeartGuard AI - Clinical Assistant")
    print("   (Powered by ChromaDB + Gemma-2b + RTX 4050 + OpenFDA)")
    print("="*60 + "\n")

    # 1. Initialize Components
    logger.info("🧠 Loading RAG Engine (Memory/Brain)...")
    try:
        rag_engine = HeartDiseaseRAG.get_instance()
    except Exception as e:
        logger.error(f"❌ Failed to load RAG Engine: {e}")
        return
    
    logger.info("🗣️  Loading MedGemma LLM (Voice/Mouth)...")
    try:
        llm_engine = MedGemmaService.get_instance()
    except Exception as e:
        logger.error("❌ Could not load LLM. Check internet connection or HuggingFace login.")
        logger.error(f"Details: {e}")
        return
    
    logger.info("🛡️  Loading OpenFDA Safety Service (Safety Officer)...")
    try:
        safety_service = get_safety_service()
    except Exception as e:
        logger.warning(f"⚠️  Could not load Safety Service: {e}")
        safety_service = None

    print("\n✅ System Ready. Type 'exit' to quit.\n")

    # 2. Conversation Loop
    while True:
        # Use asyncio.to_thread for input to avoid blocking the event loop entirely
        # (though for a CLI it matters less, it's good practice)
        query = await asyncio.to_thread(input, "👨‍⚕️ Doctor/User: ")
        
        if query.lower() in ['exit', 'quit', 'q']:
            print("\n👋 Goodbye! Stay healthy.\n")
            break
            
        if not query.strip():
            continue
            
        start_time = time.time()
        
        try:
            # Check if this is a safety-related query
            safety_result = None
            if safety_service and should_query_safety_service(query):
                logger.info("🛡️  Processing safety query...")
                print("   🛡️  Checking OpenFDA database...", end="\r")
                try:
                    # Run safety query in thread pool to avoid blocking
                    safety_result = await asyncio.to_thread(process_safety_query, query, safety_service)
                except Exception as e:
                    logger.warning(f"Could not process safety query: {e}")
                    safety_result = None
            
            # A. Retrieval (The Brain)
            print("   🧠 Retrieving medical guidelines...", end="\r")
            # Run retrieval in thread pool if it's CPU bound or sync I/O
            retrieval_result = await asyncio.to_thread(rag_engine.retrieve_context, query, top_k=3)
            context_text = retrieval_result.get("context", "")
            sources = retrieval_result.get("sources", [])
            
            if not context_text and not safety_result:
                print("❌ No relevant medical info found in database.")
                continue

            # B. Generation (The Mouth) - only if we have RAG context
            answer = ""
            if context_text:
                print("   🤔 Thinking...", end="\r")
                # Await the async generation
                answer = await llm_engine.generate_response(query, context_text)
            
            elapsed = time.time() - start_time
            
            # C. Output
            print("\n" + "🤖 HeartGuard AI:")
            print("-" * 60)
            
            # Show safety result if available
            if safety_result:
                print(safety_result)
                print("-" * 60)
            
            # Show RAG-based answer if available
            if answer:
                print(answer)
                print("-" * 60)
            
            if context_text:
                print(f"📚 Sources: {', '.join(sources) if sources else 'Unknown'}")
            print(f"⏱️  Response Time: {elapsed:.2f}s\n")
            
        except Exception as e:
            logger.error(f"❌ Error during processing: {e}")
            print(f"Error: {e}\n")
            continue

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
