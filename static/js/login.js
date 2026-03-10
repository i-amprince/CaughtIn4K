const loginCanvas = document.getElementById("snow-canvas");

if (loginCanvas) {
    const ctx = loginCanvas.getContext("2d");
    const particleCount = 100;
    const particles = [];

    const resizeCanvas = () => {
        loginCanvas.width = window.innerWidth;
        loginCanvas.height = window.innerHeight;
    };

    class Particle {
        constructor() {
            this.reset();
            this.y = Math.random() * loginCanvas.height;
        }

        reset() {
            this.x = Math.random() * loginCanvas.width;
            this.y = -10;
            this.radius = Math.random() * 2.5 + 1;
            this.speed = Math.random() * 1.5 + 0.5;
            this.drift = Math.random() * 0.5 - 0.25;
            this.opacity = Math.random() * 0.5 + 0.3;
        }

        update() {
            this.y += this.speed;
            this.x += this.drift;
            if (this.y > loginCanvas.height) {
                this.reset();
            }
            if (this.x > loginCanvas.width || this.x < 0) {
                this.x = Math.random() * loginCanvas.width;
            }
        }

        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(255, 255, 255, ${this.opacity})`;
            ctx.fill();
        }
    }

    const initParticles = () => {
        particles.length = 0;
        for (let i = 0; i < particleCount; i += 1) {
            particles.push(new Particle());
        }
    };

    const animate = () => {
        ctx.clearRect(0, 0, loginCanvas.width, loginCanvas.height);
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
