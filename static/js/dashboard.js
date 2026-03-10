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
