import asyncio
import os
import json
import logging
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from llama_cpp import Llama

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

llm = None
model_semaphore = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global llm, model_semaphore
    # 워커당 2명까지 동시 진입 허용 (나머지는 대기)
    model_semaphore = asyncio.Semaphore(2)
    
    model_path = os.getenv("MODEL_PATH")
    n_gpu_layers = int(os.getenv("N_GPU_LAYERS", "0"))
    
    if not model_path or not os.path.exists(model_path):
        logger.error(f"Model not found: {model_path}")
    else:
        logger.info(f"Loading Model... (Threads: 2)")
        try:
            llm = Llama(
                model_path=model_path,
                n_ctx=2048,
                n_threads=2, # 스레드 2개로 제한 (워커 2개 x 스레드 2개 = 4 vCPU)
                n_batch=512,
                n_gpu_layers=n_gpu_layers,
                verbose=False
            )
            logger.info("Model Loaded.")
        except Exception as e:
            logger.error(f"Load failed: {e}")
    
    yield
    llm = None

app = FastAPI(lifespan=lifespan)

class CompletionRequest(BaseModel):
    prompt: str
    n_predict: int = 256
    temperature: float = 0.1
    stop: List[str] = ["<|im_end|>"]

class ExtractionRequest(BaseModel):
    text: str

@app.post("/completion")
async def completion(req: CompletionRequest):
    if llm is None: raise HTTPException(503, "Model not loaded")
    
    # 세마포어 획득 (최대 2명)
    async with model_semaphore:
        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(None, lambda: llm(
            req.prompt, max_tokens=req.n_predict, stop=req.stop, echo=False, temperature=req.temperature
        ))
        return {"content": output['choices'][0]['text'].strip()}

@app.post("/extract")
async def extract_info(req: ExtractionRequest):
    system_prompt = "당신은 응급 의료 AI입니다. 문장에서 필수 정보 {age, gender, symptoms}를 우선적으로 추출하고, 선택 정보 {is_self, history, special_note}는 확인되는 경우에만 추출하세요."
    prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{req.text}<|im_end|>\n<|im_start|>assistant\n"
    
    # 내부 함수 호출 (CompletionRequest 생성)
    if llm is None: raise HTTPException(503, "Model not loaded")
    
    async with model_semaphore:
        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(None, lambda: llm(
            prompt, max_tokens=256, stop=["<|im_end|>"], echo=False, temperature=0.1
        ))
        response_text = output['choices'][0]['text'].strip()
        
        try:
            cleaned = re.sub(r'```json\s*|```', '', response_text).strip()
            return json.loads(cleaned)
        except:
            return {}
