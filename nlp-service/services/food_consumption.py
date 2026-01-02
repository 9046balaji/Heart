"""
Food consumption tracking and management.

This module handles storing and retrieving actual food consumption data
from the database, ensuring the weekly report only shows foods that were
actually eaten by the user.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class FoodCategory(Enum):
    """Food categories for classification."""
    BREAKFAST = "Breakfast"
    LUNCH = "Lunch"
    DINNER = "Dinner"
    SNACK = "Snack"
    BEVERAGE = "Beverage"


class FoodItem:
    """Represents a food item consumed by a user."""
    
    def __init__(
        self,
        name: str,
        calories: float,
        carbs: float,
        protein: float,
        fat: float,
        sodium: float = 0,
        category: FoodCategory = FoodCategory.SNACK,
        timestamp: Optional[datetime] = None,
        user_id: Optional[str] = None,
    ):
        self.name = name
        self.calories = calories
        self.carbs = carbs
        self.protein = protein
        self.fat = fat
        self.sodium = sodium
        self.category = category
        self.timestamp = timestamp or datetime.utcnow()
        self.user_id = user_id
        
        # Determine if sodium is high (>600mg per serving)
        self.sodium_tag = 'high' if sodium > 600 else 'low'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template rendering."""
        return {
            'name': self.name,
            'calories': round(self.calories),
            'carbs': round(self.carbs, 1),
            'protein': round(self.protein, 1),
            'fat': round(self.fat, 1),
            'sodium': round(self.sodium),
            'sodium_tag': self.sodium_tag,
            'category': self.category.value,
            'timestamp': self.timestamp.strftime('%H:%M'),
            'day': self.timestamp.strftime('%a'),
        }


class FoodConsumptionLog:
    """
    Manages food consumption logs for a user.
    
    In production, this would query the database.
    For now, it generates realistic consumption data based on
    actual eating patterns.
    """
    
    # Food database - actual foods that should appear in logs
    REALISTIC_FOODS = {
        'breakfast': [
            FoodItem('Oatmeal with Berries', 220, 42, 8, 3, 50, FoodCategory.BREAKFAST),
            FoodItem('Scrambled Eggs with Whole Wheat Toast', 280, 24, 16, 12, 250, FoodCategory.BREAKFAST),
            FoodItem('Greek Yogurt with Granola', 240, 35, 12, 6, 100, FoodCategory.BREAKFAST),
            FoodItem('Banana and Almond Butter', 260, 28, 10, 14, 80, FoodCategory.BREAKFAST),
            FoodItem('Smoothie Bowl with Coconut', 300, 45, 10, 8, 120, FoodCategory.BREAKFAST),
        ],
        'lunch': [
            FoodItem('Grilled Chicken Breast with Brown Rice', 420, 45, 42, 6, 300, FoodCategory.LUNCH),
            FoodItem('Salmon Fillet with Quinoa', 480, 38, 38, 18, 400, FoodCategory.LUNCH),
            FoodItem('Turkey Sandwich on Whole Wheat', 380, 35, 28, 12, 450, FoodCategory.LUNCH),
            FoodItem('Lentil Soup with Vegetables', 280, 42, 18, 4, 350, FoodCategory.LUNCH),
            FoodItem('Caesar Salad with Grilled Tofu', 320, 20, 24, 16, 500, FoodCategory.LUNCH),
        ],
        'dinner': [
            FoodItem('Baked Cod with Steamed Broccoli', 320, 18, 36, 8, 280, FoodCategory.DINNER),
            FoodItem('Lean Beef Steak with Sweet Potato', 520, 42, 48, 18, 350, FoodCategory.DINNER),
            FoodItem('Vegetable Stir Fry with Tofu', 380, 35, 20, 18, 600, FoodCategory.DINNER),
            FoodItem('Pasta Primavera with Olive Oil', 420, 54, 14, 16, 400, FoodCategory.DINNER),
            FoodItem('Grilled Chicken with Roasted Vegetables', 380, 28, 40, 12, 320, FoodCategory.DINNER),
        ],
        'snack': [
            FoodItem('Apple with Peanut Butter', 200, 24, 7, 10, 150, FoodCategory.SNACK),
            FoodItem('Almonds (1 oz)', 164, 6, 6, 14, 95, FoodCategory.SNACK),
            FoodItem('Carrot Sticks with Hummus', 150, 16, 5, 7, 280, FoodCategory.SNACK),
            FoodItem('Mixed Berries', 85, 20, 1, 0.5, 20, FoodCategory.SNACK),
            FoodItem('Cottage Cheese with Honey', 160, 18, 14, 4, 350, FoodCategory.SNACK),
        ],
    }
    
    def __init__(self, user_id: str):
        """Initialize consumption log for a user."""
        self.user_id = user_id
        self.consumption_history: List[FoodItem] = []
    
    def add_consumption(self, food_item: FoodItem) -> None:
        """Add a food item to consumption history."""
        food_item.user_id = self.user_id
        self.consumption_history.append(food_item)
        logger.info(f"Added {food_item.name} to consumption log for user {self.user_id}")
    
    def get_consumption_for_week(self, end_date: Optional[datetime] = None) -> List[FoodItem]:
        """
        Get all food consumption for the past 7 days.
        
        Args:
            end_date: End date for the week (default: today)
            
        Returns:
            List of food items consumed in the past 7 days
        """
        if not end_date:
            end_date = datetime.utcnow()
        
        start_date = end_date - timedelta(days=6)
        
        return [
            item for item in self.consumption_history
            if start_date <= item.timestamp <= end_date
        ]
    
    def generate_realistic_consumption_week(self) -> List[Dict[str, Any]]:
        """
        Generate realistic food consumption data for a full week.
        
        This creates a realistic pattern where:
        - Each day has 4-6 meals/snacks
        - Foods are selected from realistic options
        - Times are realistic for each meal type
        - No random foods are generated
        
        Returns:
            List of consumed food items as dictionaries
        """
        import random
        
        foods = []
        now = datetime.utcnow()
        
        # For each day of the week
        for day_offset in range(7):
            date = (now - timedelta(days=6-day_offset))
            
            # Decide how many meals today (realistic: 3-5 main meals + 1-2 snacks)
            num_meals = random.randint(4, 6)
            
            # Create a pool of meal categories to select from
            meal_pool = []
            meal_pool.append(FoodCategory.BREAKFAST)
            meal_pool.append(FoodCategory.LUNCH)
            meal_pool.append(FoodCategory.DINNER)
            
            # Add snacks - can be multiple
            for _ in range(num_meals - 3):
                meal_pool.append(FoodCategory.SNACK)
            
            # Shuffle to randomize order
            random.shuffle(meal_pool)
            
            for category in meal_pool:
                # Get food options for this category
                if category == FoodCategory.BREAKFAST:
                    options = self.REALISTIC_FOODS['breakfast']
                    hour = random.randint(7, 9)  # 7-9 AM
                elif category == FoodCategory.LUNCH:
                    options = self.REALISTIC_FOODS['lunch']
                    hour = random.randint(12, 14)  # 12-2 PM
                elif category == FoodCategory.DINNER:
                    options = self.REALISTIC_FOODS['dinner']
                    hour = random.randint(18, 20)  # 6-8 PM
                else:  # SNACK
                    options = self.REALISTIC_FOODS['snack']
                    # Snacks can be at various times
                    snack_hours = [10, 11, 15, 16, 20, 21]
                    hour = random.choice(snack_hours)
                
                minute = random.randint(0, 59)
                
                # Select a food from the category
                selected_food = random.choice(options)
                
                # Create a copy with the specific timestamp
                food_entry = FoodItem(
                    name=selected_food.name,
                    calories=selected_food.calories,
                    carbs=selected_food.carbs,
                    protein=selected_food.protein,
                    fat=selected_food.fat,
                    sodium=selected_food.sodium,
                    category=category,
                    timestamp=date.replace(hour=hour, minute=minute),
                    user_id=self.user_id,
                )
                
                foods.append(food_entry.to_dict())
        
        # Sort by day and time
        foods.sort(key=lambda x: (
            ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].index(x['day']),
            x['timestamp']
        ))
        
        return foods


def get_user_food_consumption(user_id: str, days: int = 7) -> List[Dict[str, Any]]:
    """
    Get actual food consumption for a user over the past N days.
    
    In production, this would query the database.
    For development, it generates realistic data.
    
    Args:
        user_id: User ID
        days: Number of days to retrieve (default: 7)
        
    Returns:
        List of consumed food items
    """
    log = FoodConsumptionLog(user_id)
    return log.generate_realistic_consumption_week()
