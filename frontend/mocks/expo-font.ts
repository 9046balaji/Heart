// Mock for expo-font module
// Provides web-compatible font loading stubs for @expo/vector-icons

const loadedFonts = new Set<string>();

export const loadAsync = async (fontMap: Record<string, any>) => {
    // Mark fonts as loaded
    Object.keys(fontMap).forEach(fontName => {
        loadedFonts.add(fontName);
    });
    return Promise.resolve();
};

export const isLoaded = (fontName: string): boolean => {
    // Return true for common icon fonts used by @expo/vector-icons
    // These are typically loaded via CSS or are system fonts on web
    const alwaysLoadedFonts = [
        'MaterialIcons',
        'material-icons',
        'FontAwesome',
        'Ionicons',
        'Entypo',
        'EvilIcons',
        'Feather',
        'Foundation',
        'MaterialCommunityIcons',
        'Octicons',
        'SimpleLineIcons',
        'Zocial',
    ];

    if (alwaysLoadedFonts.includes(fontName)) {
        return true;
    }

    return loadedFonts.has(fontName);
};

export const isLoading = (fontName: string): boolean => {
    return false;
};

export const unloadAsync = async (fontName: string) => {
    loadedFonts.delete(fontName);
};

export const unloadAllAsync = async () => {
    loadedFonts.clear();
};

// Font object for default export compatibility
const Font = {
    loadAsync,
    isLoaded,
    isLoading,
    unloadAsync,
    unloadAllAsync,
};

export default Font;
