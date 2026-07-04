/**
 * Subscription Countdown Timer
 * Displays remaining time for broker subscription
 * Sends notifications when subscription expires
 */

class SubscriptionCountdown {
    constructor(options = {}) {
        this.endDate = options.endDate;
        this.container = options.container;
        this.onExpire = options.onExpire || this.defaultOnExpire;
        this.updateInterval = options.updateInterval || 1000; // 1 second
        this.warningThreshold = options.warningThreshold || 7 * 24 * 60 * 60 * 1000; // 7 days
        this.timer = null;
        this.hasWarned = false;
        this.hasExpired = false;
    }

    init() {
        if (!this.endDate) {
            console.error('End date is required for countdown timer');
            return;
        }

        this.render();
        this.start();
    }

    start() {
        this.update();
        this.timer = setInterval(() => this.update(), this.updateInterval);
    }

    stop() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
    }

    update() {
        const now = new Date().getTime();
        const end = new Date(this.endDate).getTime();
        const distance = end - now;

        if (distance < 0) {
            this.stop();
            this.renderExpired();
            if (!this.hasExpired) {
                this.hasExpired = true;
                this.onExpire();
            }
            return;
        }

        // Warning threshold check
        if (distance < this.warningThreshold && !this.hasWarned) {
            this.hasWarned = true;
            this.showWarning();
        }

        const days = Math.floor(distance / (1000 * 60 * 60 * 24));
        const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((distance % (1000 * 60)) / 1000);

        this.updateDisplay(days, hours, minutes, seconds);
    }

    render() {
        if (!this.container) return;

        this.container.innerHTML = `
            <div class="subscription-countdown">
                <div class="countdown-header">
                    <span class="countdown-icon">⏰</span>
                    <span class="countdown-title">وقت انتهاء الاشتراك</span>
                </div>
                <div class="countdown-timer">
                    <div class="time-unit">
                        <span class="time-value" id="days">00</span>
                        <span class="time-label">يوم</span>
                    </div>
                    <div class="time-separator">:</div>
                    <div class="time-unit">
                        <span class="time-value" id="hours">00</span>
                        <span class="time-label">ساعة</span>
                    </div>
                    <div class="time-separator">:</div>
                    <div class="time-unit">
                        <span class="time-value" id="minutes">00</span>
                        <span class="time-label">دقيقة</span>
                    </div>
                    <div class="time-separator">:</div>
                    <div class="time-unit">
                        <span class="time-value" id="seconds">00</span>
                        <span class="time-label">ثانية</span>
                    </div>
                </div>
                <div class="countdown-footer">
                    <a href="/subscription-plans/" class="btn btn-sm btn-primary">تجديد الاشتراك</a>
                </div>
            </div>
        `;
    }

    updateDisplay(days, hours, minutes, seconds) {
        const daysEl = document.getElementById('days');
        const hoursEl = document.getElementById('hours');
        const minutesEl = document.getElementById('minutes');
        const secondsEl = document.getElementById('seconds');

        if (daysEl) daysEl.textContent = String(days).padStart(2, '0');
        if (hoursEl) hoursEl.textContent = String(hours).padStart(2, '0');
        if (minutesEl) minutesEl.textContent = String(minutes).padStart(2, '0');
        if (secondsEl) secondsEl.textContent = String(seconds).padStart(2, '0');
    }

    renderExpired() {
        if (!this.container) return;

        this.container.innerHTML = `
            <div class="subscription-countdown expired">
                <div class="countdown-header">
                    <span class="countdown-icon">⚠️</span>
                    <span class="countdown-title">انتهى الاشتراك</span>
                </div>
                <div class="countdown-message">
                    اشتراكك منتهي. يرجى تجديده للمتابعة.
                </div>
                <div class="countdown-footer">
                    <a href="/subscription-plans/" class="btn btn-sm btn-primary">تجديد الاشتراك</a>
                </div>
            </div>
        `;
    }

    showWarning() {
        // Show warning notification
        this.showNotification(
            'تنبيه: اشتراكك ينتهي قريباً',
            'اشتراكك سينتهي خلال أقل من 7 أيام. يرجى تجديده لتجنب انقطاع الخدمة.',
            'warning'
        );
    }

    defaultOnExpire() {
        // Show expired notification
        this.showNotification(
            'انتهى الاشتراك',
            'اشتراكك قد انتهى. يرجى تجديده للمتابعة في استخدام الخدمة.',
            'error'
        );

        // Send notification to server
        this.notifyServer();
    }

    showNotification(title, message, type = 'info') {
        // Check if browser supports notifications
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(title, {
                body: message,
                icon: '/static/images/favicon.svg',
                badge: '/static/images/favicon.svg'
            });
        }

        // Show in-app notification
        const notification = document.createElement('div');
        notification.className = `countdown-notification countdown-${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <span class="notification-icon">${type === 'warning' ? '⚠️' : type === 'error' ? '❌' : 'ℹ️'}</span>
                <div class="notification-text">
                    <strong>${title}</strong>
                    <p>${message}</p>
                </div>
                <button class="notification-close" onclick="this.parentElement.remove()">×</button>
            </div>
        `;

        document.body.appendChild(notification);

        // Auto remove after 5 seconds
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }

    async notifyServer() {
        try {
            const response = await fetch('/api/subscription/expire/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    expired: true,
                    timestamp: new Date().toISOString()
                })
            });

            if (response.ok) {
                console.log('Server notified about subscription expiration');
            }
        } catch (error) {
            console.error('Failed to notify server:', error);
        }
    }

    getCSRFToken() {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        return csrfToken ? csrfToken.value : '';
    }

    destroy() {
        this.stop();
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

// Initialize countdown timers on page load
document.addEventListener('DOMContentLoaded', function() {
    // Check for subscription end date in data attribute
    const countdownElements = document.querySelectorAll('[data-subscription-end]');
    
    countdownElements.forEach(element => {
        const endDate = element.getAttribute('data-subscription-end');
        if (endDate) {
            const countdown = new SubscriptionCountdown({
                endDate: endDate,
                container: element,
                onExpire: () => {
                    // Custom expire handler if needed
                    console.log('Subscription expired');
                }
            });
            countdown.init();
        }
    });

    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SubscriptionCountdown;
}
