// Import the raw recipe data and transform it to match the expected structure
import { recipeData as rawRecipeData } from './recipes';
import { Recipe, FlexibleRecipe } from '../types/recipeTypes';

// Transform function to convert raw recipe data to expected format
const transformRecipe = (rawRecipe: FlexibleRecipe): Recipe => {
  // Extract steps from the process field with improved parsing
  let steps: string[] = [];
  if (rawRecipe.process) {
    const processText = rawRecipe.process;

    // Split by "step X" pattern (handles "step 1", "step1", "Step 2", etc.)
    if (/step\s*\d+/i.test(processText)) {
      steps = processText
        .split(/step\s*\d+\s*/i)
        .filter(step => step.trim().length > 10)
        .map(step => step.replace(/^[\r\n\s]+/, '').replace(/[\r\n]+/g, ' ').trim());
    } else {
      // Fallback: split by double newlines (paragraph breaks)
      steps = processText
        .split(/\r?\n\s*\r?\n/)
        .filter(step => step.trim().length > 10)
        .map(step => step.replace(/[\r\n]+/g, ' ').trim());
    }
  }

  if (steps.length === 0) {
    steps = ['Instructions not available.'];
  }

  // Extract time information from process text or use defaults
  let prepTime = 10; // Default prep time
  let cookTime = 20; // Default cook time

  // Try to extract time information from the process
  if (rawRecipe.process) {
    const timeRegex = /\b(\d+)\s*(min|minute|minutes|hr|hour|hours)\b/gi;
    const matches = rawRecipe.process.match(timeRegex) || [];

    // Use the largest time value as cook time (assuming it's cooking time)
    const timeValues = matches.map(match => {
      const numMatch = match.match(/(\d+)/);
      return numMatch ? parseInt(numMatch[0]) : 0;
    }).filter(val => !isNaN(val));

    if (timeValues.length > 0) {
      cookTime = Math.max(...timeValues);
    }
  }

  // Format ingredients
  const ingredients = (rawRecipe.ingredients || []).map((ing: any) => {
    // Handle different ingredient formats
    if (typeof ing === 'string') {
      // If ingredient is just a string, create a normalized object
      return {
        name: ing,
        amount: 'As needed',
        unit: undefined
      };
    } else if (typeof ing === 'object' && ing !== null) {
      // Handle object format
      const measure = ing.measure || ing.amount || '';

      // Try to parse measure into amount and unit
      const measureMatch = measure.toString().match(/^([\d./\s]+(?:\s*[½¼¾⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞\d]+)?)\s*(.*)/);

      if (measureMatch) {
        // Handle fractions like "1 ½" or "½"
        let amountValue = measureMatch[1].trim();

        // Convert common fractions to decimal
        const fractionMap: { [key: string]: number } = {
          '¼': 0.25, '½': 0.5, '¾': 0.75,
          '⅓': 1 / 3, '⅔': 2 / 3,
          '⅕': 0.2, '⅖': 0.4, '⅗': 0.6, '⅘': 0.8,
          '⅙': 1 / 6, '⅚': 5 / 6,
          '⅛': 0.125, '⅜': 0.375, '⅝': 0.625, '⅞': 0.875
        };

        // Replace fractions with decimal values
        for (const [fraction, value] of Object.entries(fractionMap)) {
          amountValue = amountValue.replace(fraction, value.toString());
        }

        // Handle mixed numbers like "1 1/2"
        if (amountValue.includes(' ')) {
          const parts = amountValue.split(' ');
          const wholePart = parseFloat(parts[0]);
          const fractionPart = parseFloat(parts[1]) || 0;
          if (!isNaN(wholePart) && !isNaN(fractionPart)) {
            amountValue = (wholePart + fractionPart).toString();
          }
        }

        const amount = parseFloat(amountValue);
        const unit = measureMatch[2].trim();

        if (!isNaN(amount)) {
          return {
            name: ing.ingredient || ing.name || '',
            amount: amount,
            unit: unit || undefined
          };
        }
      }

      // Fallback: use the measure string as-is
      return {
        name: ing.ingredient || ing.name || '',
        amount: measure || 'As needed'
      };
    }

    // Default fallback
    return {
      name: 'Unknown ingredient',
      amount: 'As needed'
    };
  });

  // Calculate approximate calories based on ingredients (this is a rough estimation)
  const calories = Math.floor(
    ingredients.reduce((total, ing) => {
      // Rough approximation: 100 calories per ingredient on average
      return total + 100;
    }, 0) * 0.7 // Scale down for realistic values
  );

  return {
    id: rawRecipe.id,
    title: rawRecipe.name,
    description: rawRecipe.description || `${rawRecipe.category} dish from ${rawRecipe.area}`,
    image: rawRecipe.image_url,
    calories: calories > 0 ? calories : 300, // Default to 300 if calculation failed
    macros: {
      protein_g: Math.floor(Math.random() * 20) + 10, // Random protein value (10-30g)
      carbs_g: Math.floor(Math.random() * 30) + 20,   // Random carbs value (20-50g)
      fat_g: Math.floor(Math.random() * 20) + 5       // Random fat value (5-25g)
    },
    servings: 2, // Default servings
    prep_time_min: prepTime,
    cook_time_min: cookTime,
    difficulty: ['easy', 'medium', 'hard'][Math.floor(Math.random() * 3)] as 'easy' | 'medium' | 'hard',
    tags: [
      rawRecipe.category,
      rawRecipe.area,
      ...(rawRecipe.tags ? (Array.isArray(rawRecipe.tags) ? rawRecipe.tags : rawRecipe.tags.split(',')) : []),
      rawRecipe.name.toLowerCase().replace(/\s+/g, '-')
    ].filter(tag => tag && tag !== 'null' && typeof tag === 'string').map(t => t.trim()),
    ingredients: ingredients,
    steps: steps,
    ratings: {
      avg: parseFloat((Math.random() * 1.5 + 3.5).toFixed(1)), // Random rating between 3.5 and 5.0
      count: Math.floor(Math.random() * 50) + 10 // Random count between 10-60
    },
    youtube: rawRecipe.youtube
  };
};

// Transform all recipes
const transformedRecipes = rawRecipeData.map(transformRecipe);

export default transformedRecipes;