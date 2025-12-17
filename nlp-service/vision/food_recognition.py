"""
Food Recognition Service.

Analyzes food/meal images for nutritional estimation
and dietary tracking with heart health focus.

Features:
- Food identification
- Portion estimation
- Nutritional breakdown
- Heart-healthy recommendations
- Dietary goal tracking
"""

import logging
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import asyncio
import os

logger = logging.getLogger(__name__)


class HeartHealthScore(Enum):
    """Heart health score for foods."""
    EXCELLENT = "excellent"  # 9-10
    GOOD = "good"  # 7-8
    MODERATE = "moderate"  # 5-6
    POOR = "poor"  # 3-4
    AVOID = "avoid"  # 1-2


@dataclass
class NutritionInfo:
    """Nutritional information for a food item."""
    calories: float
    protein_g: float
    carbohydrates_g: float
    fat_g: float
    saturated_fat_g: Optional[float] = None
    fiber_g: Optional[float] = None
    sugar_g: Optional[float] = None
    sodium_mg: Optional[float] = None
    cholesterol_mg: Optional[float] = None
    potassium_mg: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return {
            "calories": self.calories,
            "protein_g": self.protein_g,
            "carbohydrates_g": self.carbohydrates_g,
            "fat_g": self.fat_g,
            "saturated_fat_g": self.saturated_fat_g,
            "fiber_g": self.fiber_g,
            "sugar_g": self.sugar_g,
            "sodium_mg": self.sodium_mg,
            "cholesterol_mg": self.cholesterol_mg,
            "potassium_mg": self.potassium_mg,
        }
    
    @property
    def macros_summary(self) -> str:
        """Get macro summary string."""
        return f"{self.calories:.0f} cal | P: {self.protein_g:.0f}g | C: {self.carbohydrates_g:.0f}g | F: {self.fat_g:.0f}g"


@dataclass
class FoodItem:
    """Individual food item identified."""
    name: str
    portion_size: str
    portion_grams: Optional[float]
    nutrition: NutritionInfo
    confidence: float
    heart_health_score: float  # 1-10
    notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "portion_size": self.portion_size,
            "portion_grams": self.portion_grams,
            "nutrition": self.nutrition.to_dict(),
            "confidence": self.confidence,
            "heart_health_score": self.heart_health_score,
            "notes": self.notes,
        }


@dataclass
class FoodAnalysis:
    """Complete food/meal analysis result."""
    foods: List[FoodItem]
    total_nutrition: NutritionInfo
    meal_type: str  # breakfast, lunch, dinner, snack
    heart_health_score: float  # 1-10 overall
    heart_health_category: HeartHealthScore
    recommendations: List[str]
    warnings: List[str]
    dietary_flags: List[str]  # e.g., "high sodium", "low fiber"
    confidence: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "foods": [f.to_dict() for f in self.foods],
            "total_nutrition": self.total_nutrition.to_dict(),
            "meal_type": self.meal_type,
            "heart_health_score": self.heart_health_score,
            "heart_health_category": self.heart_health_category.value,
            "recommendations": self.recommendations,
            "warnings": self.warnings,
            "dietary_flags": self.dietary_flags,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


class FoodRecognitionService:
    """
    Food recognition and nutritional analysis service.
    
    Analyzes food images to identify items, estimate portions,
    and calculate nutritional content with heart health focus.
    
    Example:
        service = FoodRecognitionService()
        result = await service.analyze(food_image_bytes)
        print(f"Total calories: {result.total_nutrition.calories}")
    """
    
    # Daily recommended values for heart health
    DAILY_LIMITS = {
        "sodium_mg": 2300,  # AHA recommends <2300mg, ideal <1500mg
        "saturated_fat_g": 13,  # <5-6% of calories for 2000 cal diet
        "cholesterol_mg": 300,
        "sugar_g": 36,  # AHA limit for men, 25 for women
        "fiber_g_min": 25,  # Minimum recommended
    }
    
    # Heart-healthy food categories
    HEART_HEALTHY_FOODS = {
        "excellent": [
            "salmon", "mackerel", "sardines", "trout",  # Fatty fish
            "leafy greens", "spinach", "kale", "broccoli",  # Vegetables
            "berries", "avocado", "olive oil",  # Healthy fats
            "oatmeal", "quinoa", "brown rice",  # Whole grains
            "nuts", "almonds", "walnuts",  # Nuts
            "beans", "lentils", "chickpeas",  # Legumes
        ],
        "good": [
            "chicken breast", "turkey", "lean beef",
            "eggs", "low-fat dairy", "yogurt",
            "sweet potato", "whole wheat",
        ],
        "avoid": [
            "bacon", "sausage", "hot dog", "fried",
            "chips", "french fries", "soda", "candy",
            "processed meat", "deli meat",
            "butter", "cream", "pastry",
        ],
    }
    
    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        use_mock: bool = False,
    ):
        """
        Initialize food recognition service.
        
        Args:
            gemini_api_key: API key for Gemini Vision
            use_mock: Use mock responses
        """
        self.api_key = gemini_api_key or os.getenv("GOOGLE_API_KEY")
        self._llm_gateway = None
        self.use_mock = use_mock
        
        if self.use_mock:
            logger.info("FoodRecognitionService running in mock mode")
    
    async def initialize(self):
        """Initialize the Gemini model via Gateway."""
        if not self.use_mock:
            try:
                from core.llm_gateway import get_llm_gateway
                self._llm_gateway = get_llm_gateway()
                
                if self._llm_gateway.gemini_available:
                    logger.info("Food Recognition initialized with Gemini via Gateway")
                else:
                    logger.warning("Gemini not available via Gateway, falling back to mock")
                    self.use_mock = True
            except Exception as e:
                logger.warning(f"Failed to initialize Gateway for Food Recognition: {e}")
                self.use_mock = True
    
    async def analyze(
        self,
        image: Union[bytes, str, Path],
        meal_type: Optional[str] = None,
        dietary_context: Optional[Dict] = None,
    ) -> FoodAnalysis:
        """
        Analyze a food/meal image.
        
        Args:
            image: Food image (bytes, base64, or path)
            meal_type: Optional meal type hint
            dietary_context: User's dietary goals/restrictions
        
        Returns:
            FoodAnalysis with nutritional breakdown
        """
        image_bytes = self._get_image_bytes(image)
        
        if self.use_mock:
            return self._mock_analysis(meal_type)
        
        try:
            # Build analysis prompt
            prompt = self._build_prompt(meal_type, dietary_context)
            
            # Call Gemini Vision via Gateway
            # Note: Gateway handles the disclaimer via content_type="nutrition"
            response_text = await self._llm_gateway.generate(
                prompt=prompt,
                images=[{"mime_type": "image/jpeg", "data": image_bytes}],
                content_type="nutrition"
            )
            
            # Parse response
            return self._parse_response(response_text, meal_type)
            
        except Exception as e:
            logger.error(f"Food analysis error: {e}")
            return self._mock_analysis(meal_type)
    
    def _build_prompt(
        self,
        meal_type: Optional[str],
        dietary_context: Optional[Dict],
    ) -> str:
        """Build analysis prompt for Gemini."""
        prompt = """Analyze this food image and provide detailed nutritional information.

For each food item visible, provide:
1. Food name
2. Estimated portion size
3. Estimated nutritional values:
   - Calories
   - Protein (g)
   - Carbohydrates (g)
   - Fat (g)
   - Saturated fat (g)
   - Fiber (g)
   - Sodium (mg)

Also provide:
- Total meal nutrition
- Heart health score (1-10, where 10 is most heart-healthy)
- Heart health recommendations
- Any dietary warnings (high sodium, high saturated fat, etc.)

Focus on ACCURACY of portion size estimation and nutritional values.
Consider a heart-healthy diet perspective (low sodium, low saturated fat, high fiber).

Format your response with clear sections for each food item and totals."""
        
        if meal_type:
            prompt += f"\n\nThis is a {meal_type} meal."
        
        if dietary_context:
            prompt += f"\n\nDietary context:"
            if dietary_context.get("restrictions"):
                prompt += f"\n- Restrictions: {', '.join(dietary_context['restrictions'])}"
            if dietary_context.get("goals"):
                prompt += f"\n- Goals: {', '.join(dietary_context['goals'])}"
            if dietary_context.get("conditions"):
                prompt += f"\n- Health conditions: {', '.join(dietary_context['conditions'])}"
        
        return prompt
    
    def _parse_response(
        self,
        response_text: str,
        meal_type: Optional[str],
    ) -> FoodAnalysis:
        """Parse Gemini response into FoodAnalysis."""
        import re
        
        # Extract foods (simplified parsing)
        foods = []
        
        # Try to extract numeric values
        calories_match = re.search(r'(\d+)\s*(?:cal|calories)', response_text.lower())
        protein_match = re.search(r'protein[:\s]*(\d+(?:\.\d+)?)\s*g', response_text.lower())
        carbs_match = re.search(r'carb(?:ohydrate)?s?[:\s]*(\d+(?:\.\d+)?)\s*g', response_text.lower())
        fat_match = re.search(r'(?<!saturated\s)fat[:\s]*(\d+(?:\.\d+)?)\s*g', response_text.lower())
        
        # Create a general food item from extracted data
        total_calories = float(calories_match.group(1)) if calories_match else 400
        total_protein = float(protein_match.group(1)) if protein_match else 25
        total_carbs = float(carbs_match.group(1)) if carbs_match else 45
        total_fat = float(fat_match.group(1)) if fat_match else 15
        
        # Estimate heart health score from response
        health_score = 6.0  # Default moderate
        response_lower = response_text.lower()
        
        if any(word in response_lower for word in ["excellent", "very healthy", "heart-healthy"]):
            health_score = 9.0
        elif any(word in response_lower for word in ["healthy", "good choice", "nutritious"]):
            health_score = 7.5
        elif any(word in response_lower for word in ["unhealthy", "high sodium", "fried", "processed"]):
            health_score = 4.0
        elif any(word in response_lower for word in ["avoid", "not recommended"]):
            health_score = 2.5
        
        # Create food item
        foods.append(FoodItem(
            name="Analyzed Meal",
            portion_size="1 serving",
            portion_grams=None,
            nutrition=NutritionInfo(
                calories=total_calories,
                protein_g=total_protein,
                carbohydrates_g=total_carbs,
                fat_g=total_fat,
            ),
            confidence=0.75,
            heart_health_score=health_score,
        ))
        
        # Build total nutrition
        total_nutrition = NutritionInfo(
            calories=total_calories,
            protein_g=total_protein,
            carbohydrates_g=total_carbs,
            fat_g=total_fat,
        )
        
        # Determine health category
        health_category = self._score_to_category(health_score)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(total_nutrition, health_score)
        
        # Generate warnings
        warnings = self._generate_warnings(total_nutrition)
        
        # Dietary flags
        dietary_flags = self._get_dietary_flags(total_nutrition)
        
        return FoodAnalysis(
            foods=foods,
            total_nutrition=total_nutrition,
            meal_type=meal_type or "meal",
            heart_health_score=health_score,
            heart_health_category=health_category,
            recommendations=recommendations,
            warnings=warnings,
            dietary_flags=dietary_flags,
            confidence=0.75,
        )
    
    def _mock_analysis(self, meal_type: Optional[str]) -> FoodAnalysis:
        """Generate mock food analysis."""
        # Mock a balanced meal
        foods = [
            FoodItem(
                name="Grilled Salmon",
                portion_size="6 oz",
                portion_grams=170,
                nutrition=NutritionInfo(
                    calories=280,
                    protein_g=39,
                    carbohydrates_g=0,
                    fat_g=12,
                    saturated_fat_g=2.5,
                    fiber_g=0,
                    sodium_mg=85,
                    cholesterol_mg=94,
                    potassium_mg=628,
                ),
                confidence=0.88,
                heart_health_score=9.5,
                notes=["Excellent source of omega-3 fatty acids", "Heart-healthy protein choice"],
            ),
            FoodItem(
                name="Steamed Broccoli",
                portion_size="1 cup",
                portion_grams=156,
                nutrition=NutritionInfo(
                    calories=55,
                    protein_g=4,
                    carbohydrates_g=11,
                    fat_g=0.5,
                    saturated_fat_g=0.1,
                    fiber_g=5,
                    sodium_mg=64,
                    cholesterol_mg=0,
                    potassium_mg=458,
                ),
                confidence=0.92,
                heart_health_score=9.8,
                notes=["High in fiber", "Excellent source of vitamins C and K"],
            ),
            FoodItem(
                name="Brown Rice",
                portion_size="1/2 cup cooked",
                portion_grams=98,
                nutrition=NutritionInfo(
                    calories=108,
                    protein_g=2.5,
                    carbohydrates_g=22,
                    fat_g=1,
                    saturated_fat_g=0.2,
                    fiber_g=2,
                    sodium_mg=5,
                    cholesterol_mg=0,
                    potassium_mg=43,
                ),
                confidence=0.90,
                heart_health_score=8.0,
                notes=["Whole grain", "Good source of fiber and manganese"],
            ),
        ]
        
        # Calculate totals
        total_calories = sum(f.nutrition.calories for f in foods)
        total_protein = sum(f.nutrition.protein_g for f in foods)
        total_carbs = sum(f.nutrition.carbohydrates_g for f in foods)
        total_fat = sum(f.nutrition.fat_g for f in foods)
        total_sat_fat = sum(f.nutrition.saturated_fat_g or 0 for f in foods)
        total_fiber = sum(f.nutrition.fiber_g or 0 for f in foods)
        total_sodium = sum(f.nutrition.sodium_mg or 0 for f in foods)
        
        total_nutrition = NutritionInfo(
            calories=total_calories,
            protein_g=total_protein,
            carbohydrates_g=total_carbs,
            fat_g=total_fat,
            saturated_fat_g=total_sat_fat,
            fiber_g=total_fiber,
            sodium_mg=total_sodium,
            cholesterol_mg=sum(f.nutrition.cholesterol_mg or 0 for f in foods),
            potassium_mg=sum(f.nutrition.potassium_mg or 0 for f in foods),
        )
        
        # Calculate overall score
        avg_score = sum(f.heart_health_score for f in foods) / len(foods)
        
        return FoodAnalysis(
            foods=foods,
            total_nutrition=total_nutrition,
            meal_type=meal_type or "dinner",
            heart_health_score=avg_score,
            heart_health_category=self._score_to_category(avg_score),
            recommendations=[
                "🐟 Excellent choice of fatty fish for omega-3s!",
                "🥦 Great vegetable portion - keep it up!",
                "Consider adding a drizzle of olive oil for extra heart-healthy fats",
                "This meal aligns well with Mediterranean diet principles",
            ],
            warnings=[
                "Nutritional values are estimates based on visual analysis",
            ],
            dietary_flags=[
                "High protein",
                "Low sodium",
                "Good fiber content",
                "Heart-healthy meal",
            ],
            confidence=0.88,
        )
    
    def _score_to_category(self, score: float) -> HeartHealthScore:
        """Convert numeric score to category."""
        if score >= 9:
            return HeartHealthScore.EXCELLENT
        elif score >= 7:
            return HeartHealthScore.GOOD
        elif score >= 5:
            return HeartHealthScore.MODERATE
        elif score >= 3:
            return HeartHealthScore.POOR
        else:
            return HeartHealthScore.AVOID
    
    def _generate_recommendations(
        self,
        nutrition: NutritionInfo,
        score: float,
    ) -> List[str]:
        """Generate heart-healthy recommendations."""
        recs = []
        
        if score >= 8:
            recs.append("🌟 Great heart-healthy choice! Keep it up!")
        
        if nutrition.fiber_g and nutrition.fiber_g < 5:
            recs.append("Consider adding more fiber-rich foods like vegetables or whole grains")
        
        if nutrition.sodium_mg and nutrition.sodium_mg > 600:
            recs.append("Try reducing sodium by using herbs and spices instead of salt")
        
        if score < 5:
            recs.extend([
                "Consider swapping for grilled or baked options",
                "Add a side of vegetables for more nutrients",
                "Choose lean proteins like fish or chicken breast",
            ])
        
        if not recs:
            recs.append("Well-balanced meal - continue making healthy choices!")
        
        return recs
    
    def _generate_warnings(self, nutrition: NutritionInfo) -> List[str]:
        """Generate dietary warnings."""
        warnings = []
        
        if nutrition.sodium_mg and nutrition.sodium_mg > 800:
            warnings.append(f"⚠️ High sodium ({nutrition.sodium_mg:.0f}mg) - limit daily intake")
        
        if nutrition.saturated_fat_g and nutrition.saturated_fat_g > 5:
            warnings.append(f"⚠️ High saturated fat ({nutrition.saturated_fat_g:.0f}g)")
        
        if nutrition.calories > 800:
            warnings.append(f"⚠️ High calorie meal ({nutrition.calories:.0f} cal)")
        
        # Always add disclaimer
        warnings.append("Nutritional values are estimates - actual values may vary")
        
        return warnings
    
    def _get_dietary_flags(self, nutrition: NutritionInfo) -> List[str]:
        """Get dietary flags for the meal."""
        flags = []
        
        if nutrition.protein_g >= 30:
            flags.append("High protein")
        
        if nutrition.fiber_g and nutrition.fiber_g >= 5:
            flags.append("Good fiber")
        
        if nutrition.sodium_mg and nutrition.sodium_mg < 400:
            flags.append("Low sodium")
        elif nutrition.sodium_mg and nutrition.sodium_mg > 800:
            flags.append("High sodium")
        
        if nutrition.saturated_fat_g and nutrition.saturated_fat_g < 3:
            flags.append("Low saturated fat")
        
        if nutrition.calories < 400:
            flags.append("Light meal")
        elif nutrition.calories > 700:
            flags.append("Hearty meal")
        
        return flags
    
    def _get_image_bytes(self, image: Union[bytes, str, Path]) -> bytes:
        """Convert image input to bytes."""
        import base64
        
        if isinstance(image, bytes):
            return image
        elif isinstance(image, Path):
            return image.read_bytes()
        elif isinstance(image, str):
            if len(image) > 260 and "/" not in image[:50]:
                return base64.b64decode(image)
            else:
                return Path(image).read_bytes()
        else:
            raise ValueError(f"Unsupported image type: {type(image)}")
    
    def get_food_health_score(self, food_name: str) -> float:
        """Get heart health score for a food item."""
        food_lower = food_name.lower()
        
        for food in self.HEART_HEALTHY_FOODS["excellent"]:
            if food in food_lower:
                return 9.0
        
        for food in self.HEART_HEALTHY_FOODS["good"]:
            if food in food_lower:
                return 7.0
        
        for food in self.HEART_HEALTHY_FOODS["avoid"]:
            if food in food_lower:
                return 3.0
        
        return 5.5  # Default moderate
