#!/usr/bin/env python3
"""
AI endpoints for AI model management and analysis.
"""

import logging
from typing import List
from fastapi import APIRouter, HTTPException

from app.core.config import get_ai_models
from app.models.sync_models import AIModelInfo, AIModel

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/models", response_model=List[AIModelInfo])
async def list_ai_models():
    """
    List available AI models for sync analysis.
    
    This endpoint returns information about all available AI models that can be
    used for enhanced sync detection, including their capabilities and requirements.
    
    ## Example Response
    
    ```json
    [
      {
        "name": "wav2vec2",
        "display_name": "Wav2Vec2",
        "description": "Facebook's self-supervised speech representation model",
        "embedding_dim": 768,
        "sample_rate": 16000,
        "model_size": "~95MB",
        "best_for": ["Speech", "Voice content", "General audio"],
        "is_available": true,
        "load_time": 2.3
      },
      {
        "name": "yamnet",
        "display_name": "YAMNet",
        "description": "Google's audio event detection model",
        "embedding_dim": 1024,
        "sample_rate": 16000,
        "model_size": "~15MB",
        "best_for": ["Audio events", "Sound classification", "Complex audio"],
        "is_available": true,
        "load_time": 1.8
      }
    ]
    ```
    
    ## Curl Example
    
    ```bash
    curl -X GET "http://localhost:8000/api/v1/ai/models"
    ```
    """
    try:
        ai_models = get_ai_models()
        
        # Convert to Pydantic models
        model_list = []
        for model_name, model_info in ai_models.items():
            model_info["name"] = AIModel(model_name)
            model_info["is_available"] = True  # In production, check actual availability
            model_info["load_time"] = None  # In production, measure actual load time
            
            model_list.append(AIModelInfo(**model_info))
        
        return model_list
        
    except Exception as e:
        logger.error(f"Error listing AI models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models/{model_name}", response_model=AIModelInfo)
async def get_ai_model_info(
    model_name: str
):
    """
    Get detailed information about a specific AI model.
    
    ## Example Response
    
    ```json
    {
      "name": "wav2vec2",
      "display_name": "Wav2Vec2",
      "description": "Facebook's self-supervised speech representation model",
      "embedding_dim": 768,
      "sample_rate": 16000,
      "model_size": "~95MB",
      "best_for": ["Speech", "Voice content", "General audio"],
      "is_available": true,
      "load_time": 2.3
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X GET "http://localhost:8000/api/v1/ai/models/wav2vec2"
    ```
    """
    try:
        ai_models = get_ai_models()
        
        if model_name not in ai_models:
            raise HTTPException(status_code=404, detail=f"AI model '{model_name}' not found")
        
        model_info = ai_models[model_name].copy()
        model_info["name"] = AIModel(model_name)
        model_info["is_available"] = True
        model_info["load_time"] = None
        
        return AIModelInfo(**model_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting AI model info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
