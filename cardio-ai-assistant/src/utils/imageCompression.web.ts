/**
 * Image Compression Utilities for Web/PWA
 * 
 * Browser-based image compression using browser-image-compression library.
 * Provides the same API as the React Native version for code portability.
 * 
 * Uses Web Workers for non-blocking compression.
 */

import imageCompression from 'browser-image-compression';

export interface CompressionOptions {
    maxWidth?: number;
    maxHeight?: number;
    quality?: number;
    format?: 'jpeg' | 'png';
}

export interface CompressionResult {
    uri: string;
    originalSize: number;
    compressedSize: number;
    ratio: number;
}

/**
 * Compress image before upload (Web version).
 * 
 * @param file File object from input or drag-drop
 * @param options Compression settings
 * @returns Compressed image as data URI with statistics
 */
export async function compressImage(
    file: File,
    options: CompressionOptions = {}
): Promise<CompressionResult> {
    const {
        maxWidth = 1024,
        quality = 0.8
    } = options;

    try {
        const originalSize = file.size;

        console.log(`Original: ${(originalSize / 1024 / 1024).toFixed(2)} MB`);

        // Compress using browser-image-compression
        const compressedFile = await imageCompression(file, {
            maxWidthOrHeight: maxWidth,
            initialQuality: quality,
            useWebWorker: true  // Non-blocking compression
        });

        const compressedSize = compressedFile.size;
        const ratio = ((1 - compressedSize / originalSize) * 100);

        console.log(`Compressed: ${(compressedSize / 1024 / 1024).toFixed(2)} MB`);
        console.log(`Saved: ${ratio.toFixed(1)}%`);

        // Convert to data URI
        const uri = await fileToDataUri(compressedFile);

        return {
            uri,
            originalSize,
            compressedSize,
            ratio: parseFloat(ratio.toFixed(1))
        };
    } catch (error) {
        console.error('Image compression failed:', error);

        // Fallback to original
        const uri = await fileToDataUri(file);
        return {
            uri,
            originalSize: file.size,
            compressedSize: file.size,
            ratio: 0
        };
    }
}

/**
 * Convert File to data URI.
 */
function fileToDataUri(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            resolve(e.target?.result as string);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

/**
 * Convert image URI to base64 (already base64 for web).
 */
export async function imageToBase64(uri: string): Promise<string> {
    return uri;  // Already base64 data URI
}

/**
 * Get image file size from data URI.
 */
export async function getImageSize(uri: string): Promise<number> {
    // Estimate size from base64 string
    const base64Length = uri.split(',')[1]?.length || 0;
    return Math.round(base64Length * 0.75);  // Base64 → bytes
}

/**
 * Format file size for display.
 */
export function formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

/**
 * Preset compression profiles (same as React Native).
 */
export const CompressionPresets = {
    MEDICAL_DOCUMENT: {
        maxWidth: 1600,
        quality: 0.85,
        format: 'jpeg' as const
    },

    ECG_STRIP: {
        maxWidth: 2048,
        quality: 0.90,
        format: 'jpeg' as const
    },

    FOOD_PHOTO: {
        maxWidth: 1024,
        quality: 0.75,
        format: 'jpeg' as const
    },

    PILL_BOTTLE: {
        maxWidth: 1200,
        quality: 0.80,
        format: 'jpeg' as const
    },

    GENERAL: {
        maxWidth: 1024,
        quality: 0.80,
        format: 'jpeg' as const
    }
};

/**
 * Compress and prepare for upload (Web version).
 */
export async function compressForUpload(
    file: File,
    preset: CompressionOptions = CompressionPresets.GENERAL,
    onProgress?: (stage: string, progress: number) => void
): Promise<{
    base64: string;
    stats: CompressionResult;
}> {
    try {
        onProgress?.('compressing', 0);
        const compressed = await compressImage(file, preset);
        onProgress?.('compressing', 50);

        onProgress?.('encoding', 75);
        const base64 = await imageToBase64(compressed.uri);
        onProgress?.('complete', 100);

        return {
            base64,
            stats: compressed
        };
    } catch (error) {
        console.error('Compress for upload failed:', error);
        throw error;
    }
}
