/**
 * Utility to generate PWA icons
 * This is just a placeholder implementation - in a production app,
 * you'd want to use properly designed icons
 */

// Function to generate a simple icon with the text "S" in the middle
function generateIcon(size, backgroundColor = '#007aff', textColor = '#ffffff') {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  
  // Draw background
  ctx.fillStyle = backgroundColor;
  ctx.fillRect(0, 0, size, size);
  
  // Draw text
  ctx.fillStyle = textColor;
  ctx.font = `bold ${Math.floor(size * 0.6)}px sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText('S', size / 2, size / 2);
  
  return canvas.toDataURL('image/png');
}

// Generate icons of different sizes
export function generatePWAIcons() {
  const sizes = [72, 96, 128, 144, 192, 384, 512];
  const icons = {};
  
  sizes.forEach(size => {
    icons[`icon-${size}x${size}`] = generateIcon(size);
  });
  
  return icons;
}

// Function to download all icons (for development purposes)
export function downloadIcons() {
  const icons = generatePWAIcons();
  
  Object.entries(icons).forEach(([name, dataUrl]) => {
    const link = document.createElement('a');
    link.download = `${name}.png`;
    link.href = dataUrl;
    link.click();
  });
} 