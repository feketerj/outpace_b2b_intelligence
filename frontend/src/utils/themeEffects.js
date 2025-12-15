// Visual theme effects for tenant dashboards

export const THEME_PRESETS = {
  default: {
    name: 'Clean Professional',
    description: 'Standard dark theme',
    effects: {}
  },
  brushed_metal: {
    name: 'Brushed Metal',
    description: 'Industrial metallic texture',
    effects: {
      cardBackground: 'linear-gradient(135deg, hsl(220, 15%, 15%) 0%, hsl(220, 15%, 18%) 50%, hsl(220, 15%, 15%) 100%)',
      cardBorder: '1px solid rgba(255, 255, 255, 0.1)',
      textureOverlay: 'repeating-linear-gradient(90deg, transparent, transparent 2px, rgba(255,255,255,0.03) 2px, rgba(255,255,255,0.03) 4px)',
      buttonSheen: 'linear-gradient(180deg, rgba(255,255,255,0.15) 0%, transparent 50%, rgba(0,0,0,0.15) 100%)'
    }
  },
  nvg_green: {
    name: 'NVG Green',
    description: 'Night vision goggle tactical',
    effects: {
      bodyFilter: 'hue-rotate(80deg) saturate(0.6)',
      cardBackground: 'rgba(0, 50, 20, 0.3)',
      cardBorder: '1px solid rgba(0, 255, 100, 0.2)',
      glowColor: '0 0 10px rgba(0, 255, 100, 0.3)',
      textShadow: '0 0 8px rgba(0, 255, 100, 0.5)'
    }
  },
  executive_gloss: {
    name: 'Executive Gloss',
    description: 'Polished high-end finish',
    effects: {
      cardBackground: 'linear-gradient(145deg, hsl(220, 16%, 14%) 0%, hsl(220, 16%, 18%) 100%)',
      cardBorder: '1px solid rgba(255, 255, 255, 0.15)',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.1)',
      buttonGloss: 'linear-gradient(180deg, rgba(255,255,255,0.25) 0%, transparent 60%)',
      backdrop: 'blur(10px) saturate(150%)'
    }
  },
  tactical_dark: {
    name: 'Tactical Dark',
    description: 'Military operations center',
    effects: {
      bodyBackground: 'hsl(0, 0%, 5%)',
      cardBackground: 'rgba(15, 15, 20, 0.9)',
      cardBorder: '1px solid rgba(100, 100, 120, 0.3)',
      accentGlow: '0 0 15px rgba(59, 130, 246, 0.4)',
      gridPattern: 'linear-gradient(rgba(100,100,120,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(100,100,120,0.05) 1px, transparent 1px)',
      gridSize: '20px 20px'
    }
  },
  govt_blue: {
    name: 'Government Blue',
    description: 'Federal official aesthetic',
    effects: {
      cardBackground: 'linear-gradient(145deg, hsl(210, 30%, 10%) 0%, hsl(210, 25%, 15%) 100%)',
      cardBorder: '2px solid hsl(210, 60%, 30%)',
      headerBar: 'linear-gradient(90deg, hsl(210, 80%, 25%) 0%, hsl(210, 70%, 35%) 100%)',
      sealEffect: '0 4px 20px rgba(37, 99, 235, 0.3)',
      textStripe: '2px solid hsl(210, 80%, 45%)'
    }
  },
  high_tech_sheen: {
    name: 'High-Tech Sheen',
    description: 'Futuristic holographic',
    effects: {
      cardBackground: 'linear-gradient(135deg, hsl(220, 15%, 12%) 0%, hsl(240, 20%, 15%) 50%, hsl(220, 15%, 12%) 100%)',
      cardBorder: '1px solid rgba(100, 150, 255, 0.3)',
      holoSheen: 'linear-gradient(45deg, transparent 30%, rgba(100, 150, 255, 0.1) 50%, transparent 70%)',
      glowBorder: '0 0 20px rgba(100, 150, 255, 0.2)',
      scanline: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(100, 150, 255, 0.03) 2px, rgba(100, 150, 255, 0.03) 4px)'
    }
  }
};

export const applyThemeEffects = (theme, brandingConfig) => {
  const preset = THEME_PRESETS[theme] || THEME_PRESETS.default;
  const effects = preset.effects;
  
  // Build CSS string
  let css = '';
  
  if (effects.bodyBackground) {
    css += `body { background: ${effects.bodyBackground} !important; }`;
  }
  
  if (effects.bodyFilter) {
    css += `body { filter: ${effects.bodyFilter}; }`;
  }
  
  if (effects.cardBackground || effects.textureOverlay) {
    css += `.card-professional { 
      background: ${effects.cardBackground || 'hsl(var(--background-secondary))'} !important;
      ${effects.textureOverlay ? `background-image: ${effects.textureOverlay};` : ''}
      background-blend-mode: overlay;
    }`;
  }
  
  if (effects.cardBorder) {
    css += `.card-professional { border: ${effects.cardBorder} !important; }`;
  }
  
  if (effects.boxShadow) {
    css += `.card-professional { box-shadow: ${effects.boxShadow} !important; }`;
  }
  
  if (effects.glowColor || brandingConfig.enable_glow_effects) {
    css += `button:hover { box-shadow: ${effects.glowColor || `0 0 15px var(--primary)`} !important; }`;
  }
  
  if (effects.buttonSheen || brandingConfig.enable_sheen_overlay) {
    css += `button::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 50%;
      background: ${effects.buttonSheen || 'linear-gradient(180deg, rgba(255,255,255,0.2) 0%, transparent 100%)'};
      pointer-events: none;
    }`;
  }
  
  if (effects.gridPattern) {
    css += `body::before {
      content: '';
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background-image: ${effects.gridPattern};
      background-size: ${effects.gridSize || '20px 20px'};
      opacity: 0.3;
      pointer-events: none;
      z-index: 0;
    }`;
  }
  
  if (effects.scanline) {
    css += `body::after {
      content: '';
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: ${effects.scanline};
      pointer-events: none;
      z-index: 1;
      opacity: 0.5;
    }`;
  }
  
  if (brandingConfig.background_image_base64) {
    css += `body {
      background-image: url('${brandingConfig.background_image_base64}');
      background-size: cover;
      background-attachment: fixed;
      background-position: center;
      background-blend-mode: overlay;
    }`;
    css += `body::before {
      content: '';
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.7);
      z-index: -1;
    }`;
  }
  
  return css;
};

export const injectThemeStyles = (theme, brandingConfig) => {
  // Remove existing theme styles
  const existingStyle = document.getElementById('tenant-theme-styles');
  if (existingStyle) {
    existingStyle.remove();
  }
  
  // Inject new styles
  const css = applyThemeEffects(theme, brandingConfig);
  if (css) {
    const style = document.createElement('style');
    style.id = 'tenant-theme-styles';
    style.textContent = css;
    document.head.appendChild(style);
  }
};
