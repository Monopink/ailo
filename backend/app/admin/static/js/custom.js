/* Custom JavaScript for Starlette-Admin */

document.addEventListener('DOMContentLoaded', function () {
    console.log('Custom JS loading...');

    setupFormEnhancements();
});

/**
 * Setup form enhancements
 */
function setupFormEnhancements() {
    // Add loading states to form submissions
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function () {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
            }
            form.classList.add('loading');
        });
    });

    // Enhance enum field styling
    const enumFields = document.querySelectorAll('.field-enum select');
    enumFields.forEach(field => {
        field.addEventListener('change', function () {
            // Add visual feedback for changes
            this.style.borderColor = '#198754';
            setTimeout(() => {
                this.style.borderColor = '';
            }, 1000);
        });
    });

    // Setup relation field enhancements
    setupRelationFields();
}

/**
 * Setup relation field enhancements
 */
function setupRelationFields() {
    // Initialize Select2 for relation fields if available
    if (typeof $ !== 'undefined' && $.fn.select2) {
        $('.field-relation select').select2({
            theme: 'bootstrap-5',
            placeholder: 'Select an option...',
            allowClear: true,
            width: '100%'
        });
    }
}

/**
 * Utility function to show notifications
 */
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.body.appendChild(notification);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

/**
 * Handle AJAX form submissions with better UX
 */
function handleAjaxForm(form, successCallback) {
    form.addEventListener('submit', function (e) {
        e.preventDefault();

        const formData = new FormData(form);
        const submitBtn = form.querySelector('button[type="submit"]');

        // Show loading state
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';
        }

        fetch(form.action, {
            method: form.method,
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showNotification('Operation completed successfully!', 'success');
                    if (successCallback) successCallback(data);
                } else {
                    showNotification(data.message || 'An error occurred', 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('An unexpected error occurred', 'danger');
            })
            .finally(() => {
                // Reset button state
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = 'Save';
                }
            });
    });
}

/**
 * Test AI Character function
 */
function testAICharacter(characterId) {
    // Create modal for AI character testing
    const modal = createTestModal('AI Character Test', `
        <form id="aiCharacterTestForm">
            <div class="mb-3">
                <label for="testMessage" class="form-label">Test Message</label>
                <textarea class="form-control" id="testMessage" name="test_message" rows="3"
                    placeholder="Enter a message to test with this AI character..." required>Hello, how are you today?</textarea>
            </div>
            <div class="mb-3">
                <label for="llmConfig" class="form-label">LLM Configuration</label>
                <select class="form-select" id="llmConfig" name="llm_config_key" required>
                    <option value="doubao_primary">Doubao Primary</option>
                </select>
            </div>
            <div class="mb-3">
                <label for="testUser" class="form-label">Test User</label>
                <input type="text" class="form-control" id="testUser" name="user_qiao_id"
                    value="test_user_001" readonly>
            </div>
        </form>
    `);

    // Handle form submission
    const form = modal.querySelector('#aiCharacterTestForm');
    form.addEventListener('submit', function (e) {
        e.preventDefault();

        const formData = new FormData(form);
        const testData = {
            character_qiao_id: characterId,
            user_qiao_id: formData.get('user_qiao_id'),
            llm_config_key: formData.get('llm_config_key'),
            test_message: formData.get('test_message'),
            enable_thinking: true,
            test_session_id: `admin_test_${characterId}_${Date.now()}`
        };

        // Show loading state
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Testing...';
        }

        // Call AI test API
        fetch('/admin-api/ai/test-chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(testData)
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const result = data.data;
                    showTestResult('AI Character Test Result', `
                    <div class="mb-3">
                        <strong>User Message:</strong>
                        <div class="border p-2 bg-light">${testData.test_message}</div>
                    </div>
                    <div class="mb-3">
                        <strong>AI Response:</strong>
                        <div class="border p-2 bg-light">${result.ai_response || 'No response'}</div>
                    </div>
                    ${result.thinking ? `
                    <div class="mb-3">
                        <strong>AI Thinking:</strong>
                        <div class="border p-2 bg-light"><pre>${result.thinking}</pre></div>
                    </div>
                    ` : ''}
                    <div class="mb-3">
                        <strong>Performance:</strong>
                        <div class="border p-2 bg-light">
                            Response Time: ${result.performance?.response_time_ms || 'N/A'}ms<br>
                            Tokens Used: ${result.performance?.tokens_used || 'N/A'}
                        </div>
                    </div>
                `);
                    modal.querySelector('.btn-close').click();
                } else {
                    showNotification(`Test failed: ${data.error?.message || 'Unknown error'}`, 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('Test request failed', 'danger');
            })
            .finally(() => {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = 'Test';
                }
            });
    });
}

/**
 * Test LLM Configuration function
 */
function testLLMConfig(configId) {
    // Create modal for LLM configuration testing
    const modal = createTestModal('LLM Configuration Test', `
        <form id="llmConfigTestForm">
            <div class="mb-3">
                <label for="testPrompt" class="form-label">Test Prompt</label>
                <textarea class="form-control" id="testPrompt" name="prompt" rows="3"
                    placeholder="Enter a prompt to test this LLM configuration..." required>Hello, please introduce yourself.</textarea>
            </div>
            <div class="row">
                <div class="col-md-6">
                    <label for="temperature" class="form-label">Temperature</label>
                    <input type="number" class="form-control" id="temperature" name="temperature"
                        value="0.7" min="0" max="2" step="0.1">
                </div>
                <div class="col-md-6">
                    <label for="maxTokens" class="form-label">Max Tokens</label>
                    <input type="number" class="form-control" id="maxTokens" name="max_tokens"
                        value="500" min="1" max="4000">
                </div>
            </div>
        </form>
    `);

    // Handle form submission
    const form = modal.querySelector('#llmConfigTestForm');
    form.addEventListener('submit', function (e) {
        e.preventDefault();

        const formData = new FormData(form);
        const testData = {
            config_keys: [configId],
            test_cases: [{
                name: 'admin_test',
                prompt: formData.get('prompt'),
                temperature: parseFloat(formData.get('temperature')),
                max_tokens: parseInt(formData.get('max_tokens'))
            }]
        };

        // Show loading state
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Testing...';
        }

        // Call LLM test API
        fetch('/admin-api/llm/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(testData)
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const result = data.data;
                    const testResults = result.test_results || {};
                    const configResult = testResults[configId] || {};
                    const testCaseResults = configResult.test_case_results || [];
                    const firstResult = testCaseResults[0] || {};

                    showTestResult('LLM Configuration Test Result', `
                    <div class="mb-3">
                        <strong>Test Prompt:</strong>
                        <div class="border p-2 bg-light">${testData.test_cases[0].prompt}</div>
                    </div>
                    <div class="mb-3">
                        <strong>LLM Response:</strong>
                        <div class="border p-2 bg-light">${firstResult.response || 'No response'}</div>
                    </div>
                    <div class="mb-3">
                        <strong>Performance:</strong>
                        <div class="border p-2 bg-light">
                            Success: ${firstResult.success ? 'Yes' : 'No'}<br>
                            Response Time: ${firstResult.response_time_ms || 'N/A'}ms<br>
                            Tokens Used: ${firstResult.token_usage?.total_tokens || 'N/A'}
                        </div>
                    </div>
                    ${configResult.performance_metrics ? `
                    <div class="mb-3">
                        <strong>Overall Metrics:</strong>
                        <div class="border p-2 bg-light">
                            Success Rate: ${(configResult.performance_metrics.success_rate * 100).toFixed(1)}%<br>
                            Average Response Time: ${configResult.performance_metrics.avg_response_time_ms?.toFixed(1) || 'N/A'}ms
                        </div>
                    </div>
                    ` : ''}
                `);
                    modal.querySelector('.btn-close').click();
                } else {
                    showNotification(`Test failed: ${data.error?.message || 'Unknown error'}`, 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('Test request failed', 'danger');
            })
            .finally(() => {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = 'Test';
                }
            });
    });
}

/**
 * Create a test modal
 */
function createTestModal(title, content) {
    // Remove existing modal if any
    const existingModal = document.getElementById('testModal');
    if (existingModal) {
        existingModal.remove();
    }

    // Create modal HTML
    const modalHtml = `
        <div class="modal fade" id="testModal" tabindex="-1" aria-labelledby="testModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="testModalLabel">${title}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        ${content}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="submit" form="${content.includes('aiCharacterTestForm') ? 'aiCharacterTestForm' : 'llmConfigTestForm'}" class="btn btn-primary">Test</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Add modal to DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // Show modal
    const modal = document.getElementById('testModal');
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();

    return modal;
}

/**
 * Show test result in a modal
 */
function showTestResult(title, content) {
    // Remove existing result modal if any
    const existingModal = document.getElementById('testResultModal');
    if (existingModal) {
        existingModal.remove();
    }

    // Create result modal HTML
    const modalHtml = `
        <div class="modal fade" id="testResultModal" tabindex="-1" aria-labelledby="testResultModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="testResultModalLabel">${title}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        ${content}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-primary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Add modal to DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // Show modal
    const modal = document.getElementById('testResultModal');
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();

    return modal;
}
