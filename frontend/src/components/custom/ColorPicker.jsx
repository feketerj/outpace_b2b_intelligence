import React, { useState, useEffect } from 'react';
import { Input } from '../ui/input';
import { Pipette } from 'lucide-react';

// Convert HSL string to hex
const hslToHex = (hslString) => {
  try {
    // Parse hsl(h, s%, l%) format
    const match = hslString.match(/hsl\((\d+),\s*(\d+)%?,\s*(\d+)%?\)/i);
    if (!match) {
      // Try to parse as hex directly
      if (hslString.startsWith('#')) return hslString;
      return '#3b82f6'; // Default blue
    }
    
    let h = parseInt(match[1]) / 360;
    let s = parseInt(match[2]) / 100;
    let l = parseInt(match[3]) / 100;
    
    let r, g, b;
    
    if (s === 0) {
      r = g = b = l;
    } else {
      const hue2rgb = (p, q, t) => {
        if (t < 0) t += 1;
        if (t > 1) t -= 1;
        if (t < 1/6) return p + (q - p) * 6 * t;
        if (t < 1/2) return q;
        if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
        return p;
      };
      
      const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
      const p = 2 * l - q;
      r = hue2rgb(p, q, h + 1/3);
      g = hue2rgb(p, q, h);
      b = hue2rgb(p, q, h - 1/3);
    }
    
    const toHex = (x) => {
      const hex = Math.round(x * 255).toString(16);
      return hex.length === 1 ? '0' + hex : hex;
    };
    
    return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
  } catch (e) {
    return '#3b82f6';
  }
};

// Convert hex to HSL string
const hexToHsl = (hex) => {
  try {
    // Remove # if present
    hex = hex.replace('#', '');
    
    // Parse hex values
    const r = parseInt(hex.substring(0, 2), 16) / 255;
    const g = parseInt(hex.substring(2, 4), 16) / 255;
    const b = parseInt(hex.substring(4, 6), 16) / 255;
    
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    let h, s, l = (max + min) / 2;
    
    if (max === min) {
      h = s = 0;
    } else {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      
      switch (max) {
        case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
        case g: h = ((b - r) / d + 2) / 6; break;
        case b: h = ((r - g) / d + 4) / 6; break;
        default: h = 0;
      }
    }
    
    return `hsl(${Math.round(h * 360)}, ${Math.round(s * 100)}%, ${Math.round(l * 100)}%)`;
  } catch (e) {
    return 'hsl(210, 85%, 52%)';
  }
};

export const ColorPicker = ({ 
  value, 
  onChange, 
  label,
  description,
  className = ''
}) => {
  const [hexValue, setHexValue] = useState(hslToHex(value));
  const [hslValue, setHslValue] = useState(value);
  const [showEyedropper, setShowEyedropper] = useState(false);
  
  // Check if EyeDropper API is available
  useEffect(() => {
    setShowEyedropper('EyeDropper' in window);
  }, []);
  
  // Sync hex value when HSL value changes externally
  useEffect(() => {
    setHexValue(hslToHex(value));
    setHslValue(value);
  }, [value]);
  
  const handleColorPickerChange = (e) => {
    const hex = e.target.value;
    setHexValue(hex);
    const hsl = hexToHsl(hex);
    setHslValue(hsl);
    onChange(hsl);
  };
  
  const handleHslInputChange = (e) => {
    const hsl = e.target.value;
    setHslValue(hsl);
    setHexValue(hslToHex(hsl));
    onChange(hsl);
  };
  
  const handleEyeDropper = async () => {
    if ('EyeDropper' in window) {
      try {
        const eyeDropper = new window.EyeDropper();
        const result = await eyeDropper.open();
        const hex = result.sRGBHex;
        setHexValue(hex);
        const hsl = hexToHsl(hex);
        setHslValue(hsl);
        onChange(hsl);
      } catch {
        // The browser throws here when the user cancels the picker.
      }
    }
  };
  
  return (
    <div className={`space-y-2 ${className}`}>
      {label && (
        <label className="text-sm font-medium text-[hsl(var(--foreground))]">
          {label}
        </label>
      )}
      
      <div className="flex gap-2 items-center">
        {/* Native color picker - provides palette */}
        <div className="relative">
          <input
            type="color"
            value={hexValue}
            onChange={handleColorPickerChange}
            className="w-12 h-10 rounded border border-[hsl(var(--border))] cursor-pointer bg-transparent"
            style={{ padding: 0 }}
          />
        </div>
        
        {/* Eyedropper button - if supported */}
        {showEyedropper && (
          <button
            type="button"
            onClick={handleEyeDropper}
            className="h-10 w-10 flex items-center justify-center rounded border border-[hsl(var(--border))] bg-[hsl(var(--background-tertiary))] hover:bg-[hsl(var(--background-elevated))] transition-colors"
            title="Pick color from screen"
          >
            <Pipette className="h-4 w-4 text-[hsl(var(--foreground-secondary))]" />
          </button>
        )}
        
        {/* HSL text input */}
        <Input
          placeholder="hsl(210, 85%, 52%)"
          value={hslValue}
          onChange={handleHslInputChange}
          className="flex-1 bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))] font-mono text-xs"
        />
      </div>
      
      {/* Color preview */}
      <div 
        className="h-10 rounded border border-[hsl(var(--border))] transition-colors"
        style={{ background: hslValue }}
      />
      
      {description && (
        <p className="text-xs text-[hsl(var(--foreground-muted))]">{description}</p>
      )}
    </div>
  );
};

export default ColorPicker;
