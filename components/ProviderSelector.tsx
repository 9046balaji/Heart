import React, { useState } from 'react';
import { useProvider } from '../contexts/ProviderContext';
import '../styles/ProviderSelector.css';

export const ProviderSelector: React.FC = () => {
  const { selectedProvider, setSelectedProvider, providerStatus, isLoading, availableProviders } = useProvider();
  const [isOpen, setIsOpen] = useState(false);

  const handleSelectProvider = async (provider: 'ollama' | 'openrouter') => {
    try {
      await setSelectedProvider(provider);
      setIsOpen(false);
    } catch (error) {
      console.error('Failed to switch provider:', error);
    }
  };

  const currentProviderLabel = availableProviders.find(p => p.name === selectedProvider)?.label || selectedProvider;

  return (
    <div className="provider-selector">
      <button
        className="provider-button"
        onClick={() => setIsOpen(!isOpen)}
        title="Switch between Ollama (local) and OpenRouter (cloud)"
      >
        <span className="provider-icon">
          {selectedProvider === 'ollama' ? '🔒' : '☁️'}
        </span>
        <span className="provider-label">{currentProviderLabel}</span>
        <span className="chevron">{isOpen ? '▼' : '▶'}</span>
      </button>

      {isOpen && (
        <div className="provider-dropdown">
          <div className="dropdown-header">Select AI Provider</div>

          {isLoading ? (
            <div className="dropdown-item loading">Loading providers...</div>
          ) : (
            <>
              {availableProviders.length > 0 ? (
                availableProviders.map((provider) => (
                  <button
                    key={provider.name}
                    className={`dropdown-item ${
                      selectedProvider === provider.name ? 'active' : ''
                    } ${!provider.available ? 'disabled' : ''}`}
                    onClick={() => provider.available && handleSelectProvider(provider.name as 'ollama' | 'openrouter')}
                    disabled={!provider.available}
                    title={provider.description}
                  >
                    <span className="item-icon">
                      {provider.name === 'ollama' ? '🔒' : '☁️'}
                    </span>
                    <span className="item-content">
                      <span className="item-label">{provider.label}</span>
                      <span className="item-description">{provider.description}</span>
                    </span>
                    {selectedProvider === provider.name && (
                      <span className="checkmark">✓</span>
                    )}
                    {!provider.available && (
                      <span className="unavailable">Unavailable</span>
                    )}
                  </button>
                ))
              ) : (
                <div className="dropdown-item">No providers available</div>
              )}

              {providerStatus && (
                <div className="provider-status">
                  <div className="status-item">
                    <span className="status-label">Ollama:</span>
                    <span className={`status-value ${providerStatus.ollama_available ? 'available' : 'unavailable'}`}>
                      {providerStatus.ollama_available ? '✓ Running' : '✗ Offline'}
                    </span>
                  </div>
                  <div className="status-item">
                    <span className="status-label">OpenRouter:</span>
                    <span className={`status-value ${providerStatus.openrouter_configured ? 'available' : 'unavailable'}`}>
                      {providerStatus.openrouter_configured ? '✓ Configured' : '✗ Not configured'}
                    </span>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default ProviderSelector;
