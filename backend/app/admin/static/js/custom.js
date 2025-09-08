/* Custom JavaScript for Starlette-Admin */

document.addEventListener('DOMContentLoaded', function() {
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
        form.addEventListener('submit', function() {
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
        field.addEventListener('change', function() {
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
    form.addEventListener('submit', function(e) {
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
