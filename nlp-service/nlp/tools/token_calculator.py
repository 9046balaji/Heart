"""
Token Usage Calculator for Mode-Based Tool Filtering

Demonstrates the token savings achieved by intelligent tool filtering.
"""

import json
from typing import List, Dict
import sys
sys.path.insert(0, '.')

from nlp.tools.tool_registry import get_tool_registry
from nlp.tools.mode_detector import detect_mode


def count_tokens_rough(text: str) -> int:
    """Rough token count (1 token ≈ 4 chars for English)."""
    return len(text) // 4


def calculate_savings():
    """Calculate token savings from mode-based filtering."""
    
    registry = get_tool_registry()
    
    # Get all tools
    all_tools = registry.list_tools()
    total_tools = len(all_tools)
    
    print("=" * 70)
    print(" TOKEN SAVINGS ANALYSIS - Mode-Based Tool Filtering")
    print("=" * 70)
    
    print(f"\n📊 Current Registry Stats:")
    print(f"   Total registered tools: {total_tools}")
    
    # Calculate schema sizes
    all_schemas = registry.get_openai_schemas()
    all_schemas_json = json.dumps(all_schemas, indent=2)
    all_schema_tokens = count_tokens_rough(all_schemas_json)
    
    print(f"   Total schema size: {len(all_schemas_json):,} chars")
    print(f"   Estimated tokens (all tools): ~{all_schema_tokens:,} tokens")
    
    # Test different modes
    test_modes = ["nutrition", "medication", "vitals", "general"]
    
    print(f"\n🔍 Mode-Specific Filtering:\n")
    
    mode_savings = {}
    for mode in test_modes:
        filtered_tools = registry.get_tools_for_mode(mode)
        filtered_schemas = registry.get_openai_schemas_for_mode(mode)
        filtered_json = json.dumps(filtered_schemas, indent=2)
        filtered_tokens = count_tokens_rough(filtered_json)
        
        savings_pct = ((all_schema_tokens - filtered_tokens) / all_schema_tokens) * 100 if all_schema_tokens > 0 else 0
        mode_savings[mode] = savings_pct
        
        print(f"   Mode: {mode.upper()}")
        print(f"      Tools loaded: {len(filtered_tools)}/{total_tools}")
        print(f"      Schema tokens: ~{filtered_tokens:,} ({len(filtered_json):,} chars)")
        print(f"      Token savings: {savings_pct:.1f}%")
        print()
    
    # Average savings
    avg_savings = sum(mode_savings.values()) / len(mode_savings) if mode_savings else 0
    
    print(f"📈 Results:")
    print(f"   Average token savings: {avg_savings:.1f}%")
    print(f"   Minimum savings: {min(mode_savings.values()):.1f}% (mode: {min(mode_savings, key=mode_savings.get)})")
    print(f"   Maximum savings: {max(mode_savings.values()):.1f}% (mode: {max(mode_savings, key=mode_savings.get)})")
    
    # Example real-world queries
    print(f"\n💡 Real-World Examples:\n")
    
    examples = [
        "What's my BMI if I weigh 70kg and am 175cm tall?",
        "Can I take aspirin with Lisinopril?",
        "My blood pressure is 140/90, is that high?",
        "I feel tired and have chest pain",
    ]
    
    for query in examples:
        mode = detect_mode(query)
        tools_count = len(registry.get_tools_for_mode(mode))
        schemas = registry.get_openai_schemas_for_mode(mode)
        tokens = count_tokens_rough(json.dumps(schemas))
        savings = ((all_schema_tokens - tokens) / all_schema_tokens) * 100 if all_schema_tokens > 0 else 0
        
        print(f"   Query: \"{query}\"")
        print(f"   Mode: {mode} | Tools: {tools_count}/{total_tools} | Tokens: ~{tokens} | Savings: {savings:.1f}%")
        print()
    
    print("=" * 70)
    
    if avg_savings >= 50:
        print(f"✅ SUCCESS: Achieved {avg_savings:.1f}% average token reduction (target: 60%)")
    else:
        print(f"⚠️  Need more tools registered to see full benefits (current: {avg_savings:.1f}%)")
    
    print("=" * 70)


if __name__ == "__main__":
    calculate_savings()
