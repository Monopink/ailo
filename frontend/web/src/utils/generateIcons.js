/**
 * PWA Icon Generator Utility
 * Generates placeholder icons for development and testing purposes
 * Note: For production, use professionally designed static icon files
 */

import { logger } from './logger.js';

// Icon sizes required for PWA
const ICON_SIZES = [
  { size: 72, filename: 'icon-72x72.png' },
  { size: 96, filename: 'icon-96x96.png' },
  { size: 128, filename: 'icon-128x128.png' },
  { size: 144, filename: 'icon-144x144.png' },
  { size: 152, filename: 'icon-152x152.png' },
  { size: 192, filename: 'icon-192x192.png' },
  { size: 384, filename: 'icon-384x384.png' },
  { size: 512, filename: 'icon-512x512.png' },
  { size: 180, filename: 'apple-touch-icon.png' }, // iOS specific
];

// Favicon sizes
const FAVICON_SIZES = [
  { size: 16, filename: 'favicon-16x16.png' },
  { size: 32, filename: 'favicon-32x32.png' },
];

/**
 * Generate a single icon with specified size and colors
 */
function generateIcon(size, primaryColor = '#42db5a', accentColor = '#fdd700', text = 'S') {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  
  canvas.width = size;
  canvas.height = size;
  
  // Background gradient
  const gradient = ctx.createLinearGradient(0, 0, size, size);
  gradient.addColorStop(0, primaryColor);
  gradient.addColorStop(1, accentColor);
  
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  
  // Add rounded corners for larger icons
  if (size >= 192) {
    const radius = size * 0.1;
    ctx.globalCompositeOperation = 'destination-in';
    ctx.beginPath();
    ctx.roundRect(0, 0, size, size, radius);
    ctx.fill();
    ctx.globalCompositeOperation = 'source-over';
  }
  
  // Text
  const fontSize = size * 0.5;
  ctx.fillStyle = '#ffffff';
  ctx.font = `bold ${fontSize}px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  
  // Add text shadow for better visibility
  ctx.shadowColor = 'rgba(0, 0, 0, 0.3)';
  ctx.shadowBlur = size * 0.02;
  ctx.shadowOffsetX = size * 0.01;
  ctx.shadowOffsetY = size * 0.01;
  
  ctx.fillText(text, size / 2, size / 2);
  
  return canvas;
}

/**
 * Download a canvas as PNG file
 */
function downloadCanvas(canvas, filename) {
  return new Promise((resolve) => {
    canvas.toBlob((blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      resolve();
    }, 'image/png');
  });
}

/**
 * Generate and download all PWA icons
 */
export async function generatePWAIcons(options = {}) {
  const {
    primaryColor = '#42db5a',
    accentColor = '#fdd700',
    text = 'S',
    includeFavicons = true,
  } = options;
  
  try {
    logger.info('Starting PWA icon generation', { primaryColor, accentColor, text });
    
    // Generate PWA icons
    for (const { size, filename } of ICON_SIZES) {
      const canvas = generateIcon(size, primaryColor, accentColor, text);
      await downloadCanvas(canvas, filename);
      logger.debug(`Generated ${filename}`, { size });
    }
    
    // Generate favicons if requested
    if (includeFavicons) {
      for (const { size, filename } of FAVICON_SIZES) {
        const canvas = generateIcon(size, primaryColor, accentColor, text);
        await downloadCanvas(canvas, filename);
        logger.debug(`Generated ${filename}`, { size });
      }
    }
    
    logger.info('PWA icon generation completed successfully');
    
    // Show instructions
    console.log(`
🎉 PWA Icons Generated Successfully!

📁 Files downloaded:
${ICON_SIZES.map(icon => `   • ${icon.filename}`).join('\n')}
${includeFavicons ? FAVICON_SIZES.map(icon => `   • ${icon.filename}`).join('\n') : ''}

📋 Next steps:
1. Move PWA icons to: frontend/web/public/icons/
2. Move favicons to: frontend/web/public/
3. For production, consider using professionally designed icons

💡 Tip: You can customize colors and text:
generatePWAIcons({
  primaryColor: '#your-color',
  accentColor: '#your-accent',
  text: 'YourText'
});
    `);
    
  } catch (error) {
    logger.error('Failed to generate PWA icons', error);
    throw error;
  }
}

/**
 * Generate a single custom icon for testing
 */
export function generateCustomIcon(size = 192, options = {}) {
  const {
    primaryColor = '#42db5a',
    accentColor = '#fdd700',
    text = 'S',
    filename = `custom-icon-${size}x${size}.png`
  } = options;
  
  const canvas = generateIcon(size, primaryColor, accentColor, text);
  downloadCanvas(canvas, filename);
  
  logger.info(`Generated custom icon: ${filename}`, { size, primaryColor, accentColor, text });
}

// Make functions available globally in development
if (import.meta.env.DEV) {
  window.generatePWAIcons = generatePWAIcons;
  window.generateCustomIcon = generateCustomIcon;
}
