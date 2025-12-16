#!/usr/bin/env node

/**
 * Python Virtual Environment Setup Script
 * Creates and initializes a Python venv for the NLP service
 * Works cross-platform (Windows, macOS, Linux)
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const SERVICE_DIR = __dirname;
// Use shared chatbot-env from parent directory
const VENV_DIR = path.join(SERVICE_DIR, '..', 'chatbot-env');
const REQUIREMENTS_FILE = path.join(SERVICE_DIR, 'requirements.txt');

const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  cyan: '\x1b[36m',
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function error(message) {
  log(`❌ ERROR: ${message}`, 'red');
  process.exit(1);
}

function success(message) {
  log(`✅ ${message}`, 'green');
}

function info(message) {
  log(`ℹ️  ${message}`, 'cyan');
}

function warning(message) {
  log(`⚠️  ${message}`, 'yellow');
}

try {
  log('\n🔧 Setting up Python Virtual Environment for NLP Service', 'cyan');
  log('=' + '='.repeat(60), 'cyan');

  // Step 1: Check if Python is installed
  info('Step 1: Checking Python installation...');
  try {
    const pythonVersion = execSync('python --version 2>&1 || python3 --version').toString().trim();
    success(`Found Python: ${pythonVersion}`);
  } catch (e) {
    error('Python is not installed or not in PATH. Please install Python 3.8+');
  }

  // Step 2: Check if venv already exists
  if (fs.existsSync(VENV_DIR)) {
    warning(`Virtual environment already exists at ${VENV_DIR}`);
    info('Skipping venv creation. Running pip install to ensure dependencies are current...');
  } else {
    // Step 3: Create virtual environment
    info('Step 2: Creating virtual environment...');
    try {
      execSync(`python -m venv venv 2>/dev/null || python3 -m venv venv`, {
        cwd: SERVICE_DIR,
        stdio: 'inherit',
      });
      success('Virtual environment created successfully');
    } catch (e) {
      error(`Failed to create virtual environment: ${e.message}`);
    }
  }

  // Step 4: Install requirements
  info('Step 3: Installing Python dependencies...');
  if (!fs.existsSync(REQUIREMENTS_FILE)) {
    error(`requirements.txt not found at ${REQUIREMENTS_FILE}`);
  }

  try {
    // Platform-specific pip activation
    const isWindows = process.platform === 'win32';
    const pipCommand = isWindows
      ? path.join(VENV_DIR, 'Scripts', 'pip')
      : path.join(VENV_DIR, 'bin', 'pip');

    execSync(`${pipCommand} install --upgrade pip`, {
      cwd: SERVICE_DIR,
      stdio: 'inherit',
    });

    execSync(`${pipCommand} install -r requirements.txt`, {
      cwd: SERVICE_DIR,
      stdio: 'inherit',
    });

    success('Python dependencies installed successfully');
  } catch (e) {
    error(`Failed to install dependencies: ${e.message}`);
  }

  log('\n' + '='.repeat(61), 'cyan');
  success('Python environment setup complete!');
  log('\n📋 Next steps:', 'cyan');
  log('  1. Run the NLP service: npm run dev:nlp');
  log('  2. Or run all services:  npm run dev\n', 'cyan');

} catch (e) {
  error(`Unexpected error: ${e.message}`);
}
