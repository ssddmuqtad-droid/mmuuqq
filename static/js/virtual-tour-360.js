/**
 * Virtual Tour 360° Viewer
 * Supports Equirectangular images, auto-rotation, zoom, fullscreen, and VR
 */

class VirtualTour360 {
    constructor(container, options = {}) {
        this.container = typeof container === 'string' ? document.querySelector(container) : container;
        if (!this.container) {
            console.error('Container not found');
            return;
        }

        this.options = {
            imageUrl: options.imageUrl || null,
            autoRotate: options.autoRotate || false,
            autoRotateSpeed: options.autoRotateSpeed || 1,
            enableZoom: options.enableZoom !== false,
            minZoom: options.minZoom || 0.5,
            maxZoom: options.maxZoom || 3.0,
            enableFullscreen: options.enableFullscreen !== false,
            enableVR: options.enableVR || false,
            initialPitch: options.initialPitch || 0,
            initialYaw: options.initialYaw || 0,
            autoplayDuration: options.autoplayDuration || 10,
            startInAutoplay: options.startInAutoplay || false,
            ...options
        };

        this.viewer = null;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.sphere = null;
        this.isAutoRotating = false;
        this.rotationSpeed = this.options.autoRotateSpeed * 0.001;
        this.currentZoom = 1;
        this.isDragging = false;
        this.previousMousePosition = { x: 0, y: 0 };
        this.autoplayTimer = null;

        this.init();
    }

    init() {
        // Check for Three.js
        if (typeof THREE === 'undefined') {
            console.error('Three.js is required. Please include it before using this viewer.');
            return;
        }

        // Create scene
        this.scene = new THREE.Scene();

        // Create camera
        this.camera = new THREE.PerspectiveCamera(
            75,
            this.container.clientWidth / this.container.clientHeight,
            0.1,
            1000
        );
        this.camera.position.set(0, 0, 0.1);

        // Create renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.container.appendChild(this.renderer.domElement);

        // Create sphere for 360° image
        this.createSphere();

        // Set initial view
        this.camera.rotation.x = THREE.MathUtils.degToRad(this.options.initialPitch);
        this.camera.rotation.y = THREE.MathUtils.degToRad(this.options.initialYaw);

        // Add controls
        this.addControls();

        // Add fullscreen button if enabled
        if (this.options.enableFullscreen) {
            this.addFullscreenButton();
        }

        // Add VR button if enabled
        if (this.options.enableVR) {
            this.addVRButton();
        }

        // Start autoplay if enabled
        if (this.options.startInAutoplay) {
            this.startAutoplay();
        }

        // Start auto-rotation if enabled
        if (this.options.autoRotate) {
            this.startAutoRotate();
        }

        // Handle resize
        window.addEventListener('resize', () => this.onWindowResize());

        // Start animation loop
        this.animate();
    }

    createSphere() {
        const geometry = new THREE.SphereGeometry(500, 60, 40);
        geometry.scale(-1, 1, 1);

        const textureLoader = new THREE.TextureLoader();
        const texture = textureLoader.load(this.options.imageUrl, () => {
            this.renderer.render(this.scene, this.camera);
        });

        const material = new THREE.MeshBasicMaterial({ map: texture });
        this.sphere = new THREE.Mesh(geometry, material);
        this.scene.add(this.sphere);
    }

    addControls() {
        // Mouse controls
        this.container.addEventListener('mousedown', (e) => this.onMouseDown(e));
        this.container.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.container.addEventListener('mouseup', () => this.onMouseUp());
        this.container.addEventListener('mouseleave', () => this.onMouseUp());

        // Touch controls
        this.container.addEventListener('touchstart', (e) => this.onTouchStart(e));
        this.container.addEventListener('touchmove', (e) => this.onTouchMove(e));
        this.container.addEventListener('touchend', () => this.onTouchEnd());

        // Zoom controls
        if (this.options.enableZoom) {
            this.container.addEventListener('wheel', (e) => this.onWheel(e));
        }
    }

    onMouseDown(event) {
        this.isDragging = true;
        this.previousMousePosition = {
            x: event.clientX,
            y: event.clientY
        };
    }

    onMouseMove(event) {
        if (!this.isDragging) return;

        const deltaMove = {
            x: event.clientX - this.previousMousePosition.x,
            y: event.clientY - this.previousMousePosition.y
        };

        this.camera.rotation.y -= deltaMove.x * 0.005;
        this.camera.rotation.x -= deltaMove.y * 0.005;

        // Limit vertical rotation
        this.camera.rotation.x = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, this.camera.rotation.x));

        this.previousMousePosition = {
            x: event.clientX,
            y: event.clientY
        };
    }

    onMouseUp() {
        this.isDragging = false;
    }

    onTouchStart(event) {
        if (event.touches.length === 1) {
            this.isDragging = true;
            this.previousMousePosition = {
                x: event.touches[0].clientX,
                y: event.touches[0].clientY
            };
        }
    }

    onTouchMove(event) {
        if (!this.isDragging || event.touches.length !== 1) return;

        const deltaMove = {
            x: event.touches[0].clientX - this.previousMousePosition.x,
            y: event.touches[0].clientY - this.previousMousePosition.y
        };

        this.camera.rotation.y -= deltaMove.x * 0.005;
        this.camera.rotation.x -= deltaMove.y * 0.005;

        this.camera.rotation.x = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, this.camera.rotation.x));

        this.previousMousePosition = {
            x: event.touches[0].clientX,
            y: event.touches[0].clientY
        };
    }

    onTouchEnd() {
        this.isDragging = false;
    }

    onWheel(event) {
        event.preventDefault();
        const zoomSpeed = 0.001;
        const delta = event.deltaY * zoomSpeed;

        this.currentZoom = Math.max(
            this.options.minZoom,
            Math.min(this.options.maxZoom, this.currentZoom + delta)
        );

        this.camera.fov = 75 / this.currentZoom;
        this.camera.updateProjectionMatrix();
    }

    addFullscreenButton() {
        const button = document.createElement('button');
        button.className = 'vt-fullscreen-btn';
        button.innerHTML = '⛶';
        button.title = 'ملء الشاشة';
        button.style.cssText = `
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(0, 0, 0, 0.5);
            color: white;
            border: none;
            padding: 10px;
            cursor: pointer;
            border-radius: 5px;
            font-size: 20px;
            z-index: 1000;
        `;

        button.addEventListener('click', () => this.toggleFullscreen());
        this.container.appendChild(button);
    }

    toggleFullscreen() {
        if (!document.fullscreenElement) {
            this.container.requestFullscreen().catch(err => {
                console.error('Fullscreen error:', err);
            });
        } else {
            document.exitFullscreen();
        }
    }

    addVRButton() {
        const button = document.createElement('button');
        button.className = 'vt-vr-btn';
        button.innerHTML = '🥽';
        button.title = 'وضع VR';
        button.style.cssText = `
            position: absolute;
            top: 10px;
            right: 50px;
            background: rgba(0, 0, 0, 0.5);
            color: white;
            border: none;
            padding: 10px;
            cursor: pointer;
            border-radius: 5px;
            font-size: 20px;
            z-index: 1000;
        `;

        button.addEventListener('click', () => this.enterVR());
        this.container.appendChild(button);
    }

    enterVR() {
        // VR support would require WebXR API
        alert('وضع VR يتطلب متصفح يدعم WebXR API');
    }

    startAutoRotate() {
        this.isAutoRotating = true;
    }

    stopAutoRotate() {
        this.isAutoRotating = false;
    }

    startAutoplay() {
        this.startAutoRotate();
        this.autoplayTimer = setTimeout(() => {
            this.stopAutoRotate();
        }, this.options.autoplayDuration * 1000);
    }

    stopAutoplay() {
        if (this.autoplayTimer) {
            clearTimeout(this.autoplayTimer);
            this.autoplayTimer = null;
        }
        this.stopAutoRotate();
    }

    onWindowResize() {
        this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    }

    animate() {
        requestAnimationFrame(() => this.animate());

        if (this.isAutoRotating) {
            this.camera.rotation.y += this.rotationSpeed;
        }

        this.renderer.render(this.scene, this.camera);
    }

    destroy() {
        this.stopAutoplay();
        window.removeEventListener('resize', () => this.onWindowResize());
        if (this.renderer) {
            this.renderer.dispose();
        }
        if (this.sphere) {
            this.sphere.geometry.dispose();
            this.sphere.material.dispose();
        }
    }
}

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = VirtualTour360;
}
