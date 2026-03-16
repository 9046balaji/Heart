import assert from 'assert';
import { classifyError, ErrorType } from '../utils/errorHandling';

// Mock browser navigator for Node environment
if (typeof navigator !== 'undefined') {
  Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });
}

console.log('Running real tests...');

try {
  // Test 1: Network Error
  const fakeNetworkError = new Error('Network timeout fetching data');
  const result1 = classifyError(fakeNetworkError);
  assert.strictEqual(result1.type, ErrorType.NETWORK, 'Should classify as NETWORK error');

  // Test 2: Validation Error
  const fakeValidationError = { status: 400, message: 'Invalid field' };
  const result2 = classifyError(fakeValidationError);
  assert.strictEqual(result2.type, ErrorType.VALIDATION, 'Should classify as VALIDATION error');
  
  console.log('✅ All utility tests passed!');
  process.exit(0);
} catch (e) {
  console.error('❌ Test failed!', e);
  process.exit(1);
}
