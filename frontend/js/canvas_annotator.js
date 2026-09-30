/**
 * InspectIQ™ Interactive Canvas Vision Engine.
 * Supports Multi-layer overlays (Bounding boxes, Damage Heatmap, Edge Contours, Zoom/Pan Loupe).
 */

class InspectionCanvasAnnotator {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.currentImage = null;
        this.boundingBoxes = [];

        // Layers
        this.showBoundingBoxes = true;
        this.showLabels = true;
        this.showHeatmap = false;
        this.showGrid = false;

        // Zoom & Pan state
        this.scale = 1.0;
        this.panX = 0;
        this.panY = 0;
        this.isDragging = false;
        this.startX = 0;
        this.startY = 0;

        this.setupInteractions();
    }

    setupInteractions() {
        this.canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const zoomFactor = 1.1;
            if (e.deltaY < 0) {
                this.scale = Math.min(this.scale * zoomFactor, 4.0);
            } else {
                this.scale = Math.max(this.scale / zoomFactor, 1.0);
                if (this.scale === 1.0) {
                    this.panX = 0;
                    this.panY = 0;
                }
            }
            this.render();
        });

        this.canvas.addEventListener('mousedown', (e) => {
            if (this.scale > 1.0) {
                this.isDragging = true;
                this.startX = e.clientX - this.panX;
                this.startY = e.clientY - this.panY;
                this.canvas.style.cursor = 'grabbing';
            }
        });

        window.addEventListener('mousemove', (e) => {
            if (!this.isDragging) return;
            this.panX = e.clientX - this.startX;
            this.panY = e.clientY - this.startY;
            this.render();
        });

        window.addEventListener('mouseup', () => {
            if (this.isDragging) {
                this.isDragging = false;
                this.canvas.style.cursor = 'crosshair';
            }
        });

        this.canvas.style.cursor = 'crosshair';
    }

    loadImage(imageUrl, boundingBoxes = []) {
        this.boundingBoxes = boundingBoxes || [];
        this.scale = 1.0;
        this.panX = 0;
        this.panY = 0;

        const img = new Image();
        img.onload = () => {
            this.currentImage = img;
            this.canvas.width = img.naturalWidth || img.width || 640;
            this.canvas.height = img.naturalHeight || img.height || 480;
            this.render();
        };
        img.onerror = () => {
            console.warn("Failed to load image from:", imageUrl, "Falling back to standard template...");
            if (imageUrl !== "/static/images/scenario_01_correct.png") {
                this.loadImage("/static/images/scenario_01_correct.png", boundingBoxes);
            }
        };
        img.src = imageUrl;
    }

    resetView() {
        this.scale = 1.0;
        this.panX = 0;
        this.panY = 0;
        this.render();
    }

    toggleBoxes(show) {
        this.showBoundingBoxes = show;
        this.render();
    }

    toggleLabels(show) {
        this.showLabels = show;
        this.render();
    }

    toggleHeatmap(show) {
        this.showHeatmap = show;
        this.render();
    }

    toggleGrid(show) {
        this.showGrid = show;
        this.render();
    }

    render() {
        if (!this.currentImage) return;

        const { width, height } = this.canvas;
        this.ctx.save();
        this.ctx.clearRect(0, 0, width, height);

        // Apply Zoom & Pan Transform
        this.ctx.translate(this.panX, this.panY);
        this.ctx.scale(this.scale, this.scale);

        // 1. Base Inbound Photograph
        this.ctx.drawImage(this.currentImage, 0, 0, width, height);

        // 2. Damage Heatmap Overlay (Simulated Corrugated Fluting Strain)
        if (this.showHeatmap) {
            this.renderHeatmapOverlay(width, height);
        }

        // 3. Precision Optical Grid Overlay
        if (this.showGrid) {
            this.renderOpticalGrid(width, height);
        }

        // 4. Bounding Boxes with Sci-Fi Corner Brackets
        if (this.showBoundingBoxes && this.boundingBoxes.length > 0) {
            for (const box of this.boundingBoxes) {
                const bx = (box.x <= 1.0) ? box.x * width : box.x;
                const by = (box.y <= 1.0) ? box.y * height : box.y;
                const bw = (box.width <= 1.0) ? box.width * width : box.width;
                const bh = (box.height <= 1.0) ? box.height * height : box.height;

                const boxColor = box.color || '#00f2fe';

                // Semi-transparent target fill
                this.ctx.fillStyle = this.hexToRgba(boxColor, 0.12);
                this.ctx.fillRect(bx, by, bw, bh);

                // Thin border
                this.ctx.strokeStyle = this.hexToRgba(boxColor, 0.4);
                this.ctx.lineWidth = 1;
                this.ctx.strokeRect(bx, by, bw, bh);

                // Bold HUD Corner Brackets (┌ ┐ └ ┘)
                const bracketLen = Math.min(16, bw / 3, bh / 3);
                this.ctx.strokeStyle = boxColor;
                this.ctx.lineWidth = 3;

                // Top-Left
                this.ctx.beginPath();
                this.ctx.moveTo(bx, by + bracketLen);
                this.ctx.lineTo(bx, by);
                this.ctx.lineTo(bx + bracketLen, by);
                this.ctx.stroke();

                // Top-Right
                this.ctx.beginPath();
                this.ctx.moveTo(bx + bw - bracketLen, by);
                this.ctx.lineTo(bx + bw, by);
                this.ctx.lineTo(bx + bw, by + bracketLen);
                this.ctx.stroke();

                // Bottom-Left
                this.ctx.beginPath();
                this.ctx.moveTo(bx, by + bh - bracketLen);
                this.ctx.lineTo(bx, by + bh);
                this.ctx.lineTo(bx + bracketLen, by + bh);
                this.ctx.stroke();

                // Bottom-Right
                this.ctx.beginPath();
                this.ctx.moveTo(bx + bw - bracketLen, by + bh);
                this.ctx.lineTo(bx + bw, by + bh);
                this.ctx.lineTo(bx + bw, by + bh - bracketLen);
                this.ctx.stroke();

                // Draw Precision Label Badge
                if (this.showLabels && box.label) {
                    this.ctx.font = 'bold 11px "JetBrains Mono", monospace';
                    const confPct = Math.round(box.confidence * 100);
                    const tagText = `${box.label.toUpperCase()} [${confPct}%]`;
                    const textMetrics = this.ctx.measureText(tagText);
                    const tagW = textMetrics.width + 14;
                    const tagH = 20;

                    const tagY = Math.max(2, by - tagH - 3);

                    // Badge pill
                    this.ctx.fillStyle = 'rgba(5, 8, 14, 0.9)';
                    this.ctx.fillRect(bx, tagY, tagW, tagH);
                    this.ctx.strokeStyle = boxColor;
                    this.ctx.lineWidth = 1;
                    this.ctx.strokeRect(bx, tagY, tagW, tagH);

                    // Text
                    this.ctx.fillStyle = boxColor;
                    this.ctx.fillText(tagText, bx + 7, tagY + 14);
                }
            }
        }

        this.ctx.restore();
    }

    renderHeatmapOverlay(width, height) {
        // Render synthetic thermal/stress gradient over bounding boxes
        for (const box of this.boundingBoxes) {
            if (box.label.toLowerCase().includes('crush') || box.label.toLowerCase().includes('water') || box.label.toLowerCase().includes('tear') || box.label.toLowerCase().includes('damage')) {
                const bx = (box.x <= 1.0) ? box.x * width : box.x;
                const by = (box.y <= 1.0) ? box.y * height : box.y;
                const bw = (box.width <= 1.0) ? box.width * width : box.width;
                const bh = (box.height <= 1.0) ? box.height * height : box.height;

                const grad = this.ctx.createRadialGradient(bx + bw / 2, by + bh / 2, 5, bx + bw / 2, by + bh / 2, Math.max(bw, bh));
                grad.addColorStop(0, 'rgba(255, 0, 50, 0.7)');
                grad.addColorStop(0.5, 'rgba(255, 160, 0, 0.45)');
                grad.addColorStop(1, 'rgba(0, 242, 254, 0.0)');

                this.ctx.fillStyle = grad;
                this.ctx.fillRect(bx - 20, by - 20, bw + 40, bh + 40);
            }
        }
    }

    renderOpticalGrid(width, height) {
        this.ctx.strokeStyle = 'rgba(0, 242, 254, 0.12)';
        this.ctx.lineWidth = 0.5;

        for (let x = 0; x < width; x += 40) {
            this.ctx.beginPath();
            this.ctx.moveTo(x, 0);
            this.ctx.lineTo(x, height);
            this.ctx.stroke();
        }
        for (let y = 0; y < height; y += 40) {
            this.ctx.beginPath();
            this.ctx.moveTo(0, y);
            this.ctx.lineTo(width, y);
            this.ctx.stroke();
        }
    }

    hexToRgba(hex, alpha = 0.2) {
        let c;
        if (/^#([A-Fa-f0-9]{3}){1,2}$/.test(hex)) {
            c = hex.substring(1).split('');
            if (c.length === 3) {
                c = [c[0], c[0], c[1], c[1], c[2], c[2]];
            }
            c = '0x' + c.join('');
            return `rgba(${[(c >> 16) & 255, (c >> 8) & 255, c & 255].join(',')},${alpha})`;
        }
        return `rgba(0, 242, 254, ${alpha})`;
    }
}
