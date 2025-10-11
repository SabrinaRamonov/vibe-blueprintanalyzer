from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import base64
import io
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
from pdf2image import convert_from_bytes
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
import tempfile
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

class DimensionData(BaseModel):
    dimensions: List[dict]
    scale_info: Optional[str] = None
    analysis_notes: str

class BlueprintAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    analysis_data: dict
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Blueprint Digital Measure API"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    return status_checks

async def analyze_blueprint_with_ai(image_bytes: bytes, filename: str) -> dict:
    """Use AI vision to analyze blueprint and extract dimensions"""
    try:
        # Encode image as base64
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Initialize AI chat with vision (using Claude with base64 encoding)
        api_key = os.environ.get('EMERGENT_LLM_KEY', '')
        chat = LlmChat(
            api_key=api_key,
            session_id=f"blueprint-{uuid.uuid4()}",
            system_message="You are an expert construction blueprint analyzer. Analyze blueprints to detect dimensions, scales, and measurements with precision."
        ).with_model("anthropic", "claude-sonnet-4-20250514")
        
        # Create message with base64 encoded image
        image_content = ImageContent(
            image_base64=image_b64
        )
        
        prompt = """Analyze this construction blueprint image and provide detailed measurement information:

1. Identify ALL visible dimensions and measurements on the blueprint
2. Detect the scale (e.g., 1/4" = 1', 1:100, etc.) - look for scale notation or infer from existing measurements
3. For any unmarked distances, estimate dimensions based on the detected scale
4. List each dimension with:
   - Location description (e.g., "north wall length", "room width", etc.)
   - Measured/detected value
   - Whether it's an existing measurement or estimated
   - Confidence level (high/medium/low)

Provide your response in JSON format:
{
  "scale": "detected or assumed scale",
  "scale_confidence": "high/medium/low",
  "dimensions": [
    {
      "label": "description of what is measured",
      "value": "measurement with units",
      "type": "detected" or "estimated",
      "confidence": "high/medium/low",
      "notes": "any relevant notes"
    }
  ],
  "notes": "general observations about the blueprint"
}"""
        
        user_message = UserMessage(
            text=prompt,
            file_contents=[image_content]
        )
        
        # Get AI response
        response = await chat.send_message(user_message)
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        # Parse JSON response
        try:
            # Try to extract JSON from response
            response_text = response.strip()
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()
            
            analysis_data = json.loads(response_text)
            return analysis_data
        except json.JSONDecodeError:
            # If JSON parsing fails, return structured data
            return {
                "scale": "Unable to detect",
                "scale_confidence": "low",
                "dimensions": [],
                "notes": response,
                "raw_response": response
            }
    
    except Exception as e:
        logger.error(f"Error analyzing blueprint: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

def draw_dimensions_on_image(image_bytes: bytes, analysis_data: dict) -> bytes:
    """Draw dimension annotations on the blueprint image"""
    try:
        # Load image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Create drawing context
        draw = ImageDraw.Draw(image)
        
        # Try to load a font, fall back to default if not available
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        except:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        # Draw scale information at top
        scale_text = f"Scale: {analysis_data.get('scale', 'Unknown')}"
        draw.rectangle([(10, 10), (400, 50)], fill=(0, 120, 215, 230))
        draw.text((20, 20), scale_text, fill=(255, 255, 255), font=font)
        
        # Draw dimensions
        dimensions = analysis_data.get('dimensions', [])
        y_offset = 70
        
        for idx, dim in enumerate(dimensions[:15]):  # Limit to first 15 dimensions
            label = dim.get('label', f'Dimension {idx+1}')
            value = dim.get('value', 'N/A')
            dim_type = dim.get('type', 'unknown')
            confidence = dim.get('confidence', 'unknown')
            
            # Color code by type
            if dim_type == 'detected':
                color = (34, 197, 94)  # Green for detected
            else:
                color = (251, 191, 36)  # Yellow/orange for estimated
            
            # Draw background box
            text = f"{label}: {value}"
            bbox = draw.textbbox((0, 0), text, font=small_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            draw.rectangle(
                [(10, y_offset), (text_width + 40, y_offset + text_height + 10)],
                fill=color
            )
            draw.text((20, y_offset + 5), text, fill=(0, 0, 0), font=small_font)
            
            y_offset += text_height + 15
        
        # Add summary at bottom
        total_dims = len(dimensions)
        detected = sum(1 for d in dimensions if d.get('type') == 'detected')
        estimated = total_dims - detected
        
        summary_y = image.height - 60
        draw.rectangle([(10, summary_y), (500, image.height - 10)], fill=(71, 85, 105, 230))
        summary_text = f"Total: {total_dims} dimensions | Detected: {detected} | Estimated: {estimated}"
        draw.text((20, summary_y + 10), summary_text, fill=(255, 255, 255), font=font)
        
        # Convert back to bytes
        output = io.BytesIO()
        image.save(output, format='PNG')
        return output.getvalue()
    
    except Exception as e:
        logger.error(f"Error drawing dimensions: {e}")
        return image_bytes  # Return original if drawing fails

@api_router.post("/analyze-blueprint")
async def analyze_blueprint(file: UploadFile = File(...)):
    """Upload and analyze a blueprint PDF or image"""
    try:
        # Read file
        contents = await file.read()
        
        # Convert to image if PDF
        if file.filename.lower().endswith('.pdf'):
            images = convert_from_bytes(contents, dpi=300, fmt='png')
            if not images:
                raise HTTPException(status_code=400, detail="Could not convert PDF to image")
            
            # Use first page
            img_byte_arr = io.BytesIO()
            images[0].save(img_byte_arr, format='PNG')
            image_bytes = img_byte_arr.getvalue()
        else:
            # Already an image
            image_bytes = contents
        
        # Analyze with AI
        analysis_data = await analyze_blueprint_with_ai(image_bytes, file.filename)
        
        # Draw annotations on image
        annotated_image_bytes = draw_dimensions_on_image(image_bytes, analysis_data)
        
        # Encode images to base64
        original_b64 = base64.b64encode(image_bytes).decode('utf-8')
        annotated_b64 = base64.b64encode(annotated_image_bytes).decode('utf-8')
        
        # Store in database
        analysis_obj = BlueprintAnalysis(
            filename=file.filename,
            analysis_data=analysis_data
        )
        doc = analysis_obj.model_dump()
        doc['timestamp'] = doc['timestamp'].isoformat()
        await db.blueprint_analyses.insert_one(doc)
        
        return {
            "success": True,
            "filename": file.filename,
            "analysis": analysis_data,
            "original_image": f"data:image/png;base64,{original_b64}",
            "annotated_image": f"data:image/png;base64,{annotated_b64}"
        }
    
    except Exception as e:
        logger.error(f"Error processing blueprint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/analyses", response_model=List[BlueprintAnalysis])
async def get_analyses():
    """Get all blueprint analyses"""
    analyses = await db.blueprint_analyses.find({}, {"_id": 0}).to_list(100)
    for analysis in analyses:
        if isinstance(analysis['timestamp'], str):
            analysis['timestamp'] = datetime.fromisoformat(analysis['timestamp'])
    return analyses

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
