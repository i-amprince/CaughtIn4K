const dashboardCanvas = document.getElementById("flame-canvas");

if (dashboardCanvas) {
    const ctx = dashboardCanvas.getContext("2d");
    const particleCount = 80;
    const particles = [];

    const resizeCanvas = () => {
        dashboardCanvas.width = window.innerWidth;
        dashboardCanvas.height = window.innerHeight;
    };

    class FlameParticle {
        constructor() {
            this.reset();
            this.y = Math.random() * dashboardCanvas.height;
        }

        reset() {
            this.x = Math.random() * dashboardCanvas.width;
            this.y = dashboardCanvas.height + 10;
            this.radius = Math.random() * 3 + 1;
            this.speed = Math.random() * 2 + 0.8;
            this.drift = Math.random() * 1.5 - 0.75;
            this.opacity = Math.random() * 0.6 + 0.2;
            const colorType = Math.random();
            if (colorType < 0.4) {
                this.color = "255, 107, 53";
            } else if (colorType < 0.7) {
                this.color = "255, 56, 56";
            } else {
                this.color = "150, 150, 150";
            }
        }

        update() {
            this.y -= this.speed;
            this.x += this.drift;
            this.opacity -= 0.002;
            if (this.y < -10 || this.opacity <= 0) {
                this.reset();
            }
            if (this.x > dashboardCanvas.width || this.x < 0) {
                this.x = Math.random() * dashboardCanvas.width;
            }
        }

        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
            const gradient = ctx.createRadialGradient(this.x, this.y, 0, this.x, this.y, this.radius * 2);
            gradient.addColorStop(0, `rgba(${this.color}, ${this.opacity})`);
            gradient.addColorStop(1, `rgba(${this.color}, 0)`);
            ctx.fillStyle = gradient;
            ctx.fill();
        }
    }

    const initParticles = () => {
        particles.length = 0;
        for (let i = 0; i < particleCount; i += 1) {
            particles.push(new FlameParticle());
        }
    };

    const animate = () => {
        ctx.clearRect(0, 0, dashboardCanvas.width, dashboardCanvas.height);
        particles.forEach((particle) => {
            particle.update();
            particle.draw();
        });
        window.requestAnimationFrame(animate);
    };

    resizeCanvas();
    initParticles();
    animate();
    window.addEventListener("resize", () => {
        resizeCanvas();
        initParticles();
    });
}

/* ── ML Job Status Polling ───────────────────────────────────────────────── *
 * Polls /inspection_status and /training_status every 4 seconds.
 * Shows a live banner while each job runs, then either reloads the page
 * (on success) or shows an error banner (on failure).
 * ─────────────────────────────────────────────────────────────────────────── */
(function () {
    'use strict';

    // Inject a banner container just below the header if not already in the template
    function getOrCreateBannerHost() {
        var existing = document.getElementById('ml-job-banners');
        if (existing) return existing;
        var host = document.createElement('div');
        host.id = 'ml-job-banners';
        host.style.cssText = 'position:fixed;top:64px;left:0;right:0;z-index:9999;display:flex;flex-direction:column;gap:8px;padding:8px 24px;pointer-events:none;';
        document.body.appendChild(host);
        return host;
    }

    function showBanner(id, message, type) {
        var host = getOrCreateBannerHost();
        var existing = document.getElementById(id);
        if (existing) { existing.remove(); }

        var colors = {
            info:    { bg: 'rgba(59,130,246,0.15)',  border: 'rgba(59,130,246,0.4)',  color: '#93c5fd' },
            success: { bg: 'rgba(16,185,129,0.15)',  border: 'rgba(16,185,129,0.4)',  color: '#6ee7b7' },
            error:   { bg: 'rgba(239,68,68,0.15)',   border: 'rgba(239,68,68,0.4)',   color: '#fca5a5' },
        };
        var c = colors[type] || colors.info;

        var banner = document.createElement('div');
        banner.id = id;
        banner.style.cssText = [
            'display:flex', 'align-items:center', 'gap:12px',
            'padding:12px 20px', 'border-radius:10px',
            'font-size:0.85rem', 'font-family:Outfit,sans-serif',
            'pointer-events:auto',
            'background:' + c.bg,
            'border:1px solid ' + c.border,
            'color:' + c.color,
            'animation:fadeSlideUp 0.3s ease',
        ].join(';');

        var spinner = type === 'info'
            ? '<span style="width:14px;height:14px;border:2px solid rgba(147,197,253,0.3);border-top-color:#93c5fd;border-radius:50%;animation:spin 0.8s linear infinite;flex-shrink:0;display:inline-block;"></span>'
            : (type === 'success' ? '✅' : '❌');

        banner.innerHTML = spinner + '<span>' + message + '</span>';
        host.appendChild(banner);

        if (type !== 'info') {
            setTimeout(function () {
                banner.style.transition = 'opacity 0.5s';
                banner.style.opacity = '0';
                setTimeout(function () { banner.remove(); }, 500);
            }, 7000);
        }
    }

    function removeBanner(id) {
        var el = document.getElementById(id);
        if (el) el.remove();
    }

    // ── Inspection polling ────────────────────────────────────────────────
    var inspectionTimer = null;

    function pollInspection() {
        fetch('/inspection_status', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.running) {
                    showBanner('inspection-banner', '🔍 Inspection running in the background — you can navigate freely.', 'info');
                    inspectionTimer = setTimeout(pollInspection, 4000); // keep polling
                } else if (data.done) {
                    removeBanner('inspection-banner');
                    if (data.success) {
                        showBanner('inspection-result', '✅ Inspection complete! Reloading results…', 'success');
                        setTimeout(function () { window.location.reload(); }, 1500);
                    } else if (data.message) {
                        showBanner('inspection-result', '❌ ' + data.message, 'error');
                    }
                    inspectionTimer = null; // job done, stop polling
                }
                // data.running=false AND data.done=false → idle, don't reschedule
            })
            .catch(function () {
                inspectionTimer = setTimeout(pollInspection, 4000); // retry on network blip
            });
    }

    // ── Training polling ──────────────────────────────────────────────────
    var trainingTimer = null;

    function pollTraining() {
        fetch('/training_status', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.running) {
                    showBanner('training-banner', '🏋️ Model training in progress — this may take several minutes.', 'info');
                    trainingTimer = setTimeout(pollTraining, 4000); // keep polling
                } else if (data.done) {
                    removeBanner('training-banner');
                    if (data.success) {
                        showBanner('training-result', '✅ ' + data.message, 'success');
                    } else if (data.message) {
                        showBanner('training-result', '❌ ' + data.message, 'error');
                    }
                    trainingTimer = null; // job done, stop polling
                }
                // idle → don't reschedule
            })
            .catch(function () {
                trainingTimer = setTimeout(pollTraining, 4000); // retry on network blip
            });
    }

    // ── Trigger polling only when a button is clicked ─────────────────────
    // Watch for inspection/training form submissions and start polling then.
    

    document.addEventListener('submit', function (e) {
    var form = e.target;
    var action = form.action || '';

    // 🔥 Disable submit button immediately
    var btn = form.querySelector('button[type="submit"]');
    if (btn) {
        btn.disabled = true;
        btn.innerText = "Processing...";
    }

    if (action.indexOf('run_inspection') !== -1 && !inspectionTimer) {
        setTimeout(pollInspection, 1500);
    }
    if (action.indexOf('start_training') !== -1 && !trainingTimer) {
        setTimeout(pollTraining, 1500);
    }
});

    // On page load do one silent check — if the server says a job is already
    // running (e.g. page was refreshed mid-job), start polling immediately.
    fetch('/inspection_status', { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (d) { if (d.running || d.done) pollInspection(); })
        .catch(function () {});

    fetch('/training_status', { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (d) { if (d.running || d.done) pollTraining(); })
        .catch(function () {});
})();