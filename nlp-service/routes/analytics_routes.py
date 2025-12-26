"""
Analytics API Routes.

Exposes endpoints for the AnalyticsManager to track and report on NLP service usage.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Dict, List, Any, Optional
import logging

from core.analytics import AnalyticsManager
from core.security import get_optional_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

# Global analytics manager instance
# In a production app, this might be a singleton dependency
analytics_manager = AnalyticsManager()


@router.get("/summary")
async def get_analytics_summary(
    current_user: Optional[dict] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get comprehensive analytics summary."""
    try:
        return analytics_manager.get_analytics_summary()
    except Exception as e:
        logger.error(f"Error getting analytics summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/intents")
async def get_intent_distribution(
    current_user: Optional[dict] = Depends(get_optional_user),
) -> Dict[str, int]:
    """Get distribution of detected intents."""
    try:
        return analytics_manager.get_intent_distribution()
    except Exception as e:
        logger.error(f"Error getting intent distribution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sentiment")
async def get_sentiment_distribution(
    current_user: Optional[dict] = Depends(get_optional_user),
) -> Dict[str, int]:
    """Get distribution of detected sentiments."""
    try:
        return analytics_manager.get_sentiment_distribution()
    except Exception as e:
        logger.error(f"Error getting sentiment distribution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entities")
async def get_entity_type_distribution(
    current_user: Optional[dict] = Depends(get_optional_user),
) -> Dict[str, int]:
    """Get distribution of entity types."""
    try:
        return analytics_manager.get_entity_type_distribution()
    except Exception as e:
        logger.error(f"Error getting entity distribution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-intents")
async def get_top_intents(
    limit: int = Query(10, ge=1, le=50),
    current_user: Optional[dict] = Depends(get_optional_user),
) -> List[Any]:
    """Get most common intents."""
    try:
        return analytics_manager.get_top_intents(limit=limit)
    except Exception as e:
        logger.error(f"Error getting top intents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-entities")
async def get_top_entities(
    limit: int = Query(10, ge=1, le=50),
    current_user: Optional[dict] = Depends(get_optional_user),
) -> List[Any]:
    """Get most common entity types."""
    try:
        return analytics_manager.get_top_entities(limit=limit)
    except Exception as e:
        logger.error(f"Error getting top entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends/performance")
async def get_performance_trends(
    current_user: Optional[dict] = Depends(get_optional_user),
) -> List[Dict[str, Any]]:
    """Get performance trends over time."""
    try:
        return analytics_manager.get_performance_trends()
    except Exception as e:
        logger.error(f"Error getting performance trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/anomalies")
async def detect_anomalies(
    current_user: Optional[dict] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Detect anomalies in analytics data."""
    try:
        return analytics_manager.detect_anomalies()
    except Exception as e:
        logger.error(f"Error detecting anomalies: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}")
async def get_user_analytics(
    user_id: str,
    current_user: Optional[dict] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get analytics for a specific user."""
    try:
        return analytics_manager.get_user_analytics(user_id)
    except Exception as e:
        logger.error(f"Error getting user analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
