// Define consistent recipe interface to handle format mismatches
export interface Recipe {
  id: string;
  title: string;
  description: string;
  image: string;
  calories: number;
  macros: {
    protein_g: number;
    carbs_g: number;
    fat_g: number;
  };
  servings: number;
  prep_time_min: number;
  cook_time_min: number;
  difficulty: 'easy' | 'medium' | 'hard';
  tags: string[];
  ingredients: {
    name: string;
    amount: number | string;
    unit?: string;
  }[];
  steps: string[];
  ratings: {
    avg: number;
    count: number;
  };
  youtube?: string;
}

// Define flexible recipe input that can handle different formats
export interface FlexibleRecipe {
  id?: string;
  name?: string;
  title?: string;
  description?: string;
  image?: string;
  image_url?: string;
  calories?: number;
  calorie_count?: number;
  macros?: {
    protein_g?: number;
    carbs_g?: number;
    fat_g?: number;
    fats_g?: number; // Alternative property name
  };
  protein?: number; // Direct property as alternative
  carbs?: number;   // Direct property as alternative
  fat?: number;     // Direct property as alternative
  fats?: number;    // Direct property as alternative
  servings?: number;
  prep_time_min?: number;
  prepTime?: number;    // Alternative property name
  cook_time_min?: number;
  cookTime?: number;    // Alternative property name
  difficulty?: 'easy' | 'medium' | 'hard';
  tags?: string[] | string; // Allow string for raw data (comma separated)
  ingredients?: Array<string | { name?: string; amount?: number | string; unit?: string; measure?: string; ingredient?: string }>;
  steps?: string[];
  process?: string; // Alternative to steps
  ratings?: {
    avg?: number;
    count?: number;
  };
  rating?: number;  // Alternative property name
  category?: string; // From raw recipe data
  area?: string;     // From raw recipe data
  youtube?: string;  // From raw recipe data
}

// Type guard functions to help with format detection
export const isValidRecipe = (obj: any): obj is Recipe => {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    typeof obj.id === 'string' &&
    typeof obj.title === 'string' &&
    typeof obj.calories === 'number' &&
    obj.macros &&
    typeof obj.macros.protein_g === 'number' &&
    typeof obj.macros.carbs_g === 'number' &&
    typeof obj.macros.fat_g === 'number'
  );
};

export const isFlexibleRecipe = (obj: any): obj is FlexibleRecipe => {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    (typeof obj.id === 'string' || typeof obj.name === 'string')
  );
};