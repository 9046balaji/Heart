// Shim for @react-native/assets-registry/registry
// This provides a minimal implementation for web builds

const assets = {};
let assetId = 0;

export function registerAsset(asset) {
    assetId++;
    assets[assetId] = asset;
    return assetId;
}

export function getAssetByID(id) {
    return assets[id] || null;
}

export default {
    registerAsset,
    getAssetByID,
};
