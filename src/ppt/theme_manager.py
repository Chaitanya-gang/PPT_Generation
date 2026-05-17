"""
newd2p - PPT Theme Manager
"""

from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN


import os
import yaml
from pathlib import Path
from pptx.dml.color import RGBColor
from src.config import PROJECT_ROOT
from src.utils.logger import get_logger

logger = get_logger("theme_manager")

THEMES = {}

def load_themes():
    global THEMES
    templates_dir = PROJECT_ROOT / "templates"
    
    if not templates_dir.exists():
        logger.warning(f"Templates directory not found at {templates_dir}")
        return
        
    for theme_dir in templates_dir.iterdir():
        if theme_dir.is_dir():
            config_path = theme_dir / "config.yaml"
            if config_path.exists():
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        if data and "theme" in data:
                            theme_data = data["theme"]
                            theme_name = theme_dir.name.lower()
                            
                            # Convert rgb arrays to RGBColor
                            palette = {}
                            for key, val in theme_data.items():
                                if key != "name" and isinstance(val, list) and len(val) == 3:
                                    palette[key] = RGBColor(val[0], val[1], val[2])
                            
                            THEMES[theme_name] = palette
                except Exception as e:
                    logger.error(f"Failed to load theme {theme_dir.name}: {e}")

# Load themes initially
load_themes()

def get_theme(theme_name: str) -> dict:
    # If not found, fallback to 'ocean' or whatever is available
    if not THEMES:
        return {}
    if theme_name in THEMES:
        return THEMES[theme_name]
    # Fallback to first available theme
    return next(iter(THEMES.values()))

