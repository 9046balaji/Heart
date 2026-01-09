// Shim for invariant module
// Provides a default export for web compatibility

function invariant(condition, message) {
    if (!condition) {
        const error = new Error(message || 'Invariant violation');
        error.name = 'Invariant Violation';
        throw error;
    }
}

export default invariant;
export { invariant };
