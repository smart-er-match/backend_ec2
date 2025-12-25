import aiohttp
import asyncio
import json
import os
import random
import re
from datetime import datetime

# --- [설정] ---
API_KEY = "S14P02AR07-4c958e60-790d-49bd-9400-9fc7ccfe5776"
API_URL = "https://gms.ssafy.io/gmsapi/api.openai.com/v1/chat/completions"
OUTPUT_FILE = "qwen_0.5b_essential_data.jsonl"

# 목표: 3000개
TOTAL_TARGET_DATA = 1500
BATCH_SIZE = 10
CONCURRENT_REQUESTS = 5
MODEL_NAME = "gpt-4o"

def get_system_prompt(mode_index):
    """
    필수 정보(나이, 성별, 증상) 위주의 데이터 생성 프롬프트
    """
    scenarios = [
        # [Case 1] 완벽한 정보: 필수 정보가 다 있는 경우
        {
            "mode": "COMPLETE_INFO",
            "desc": "환자가 자신의 나이, 성별, 증상을 명확하게 말하는 상황.",
            "prompt_guide": "모든 필수 필드(age, gender, symptoms)가 채워지도록 생성하세요."
        },
        # [Case 2] 정보 누락: 증상만 말하는 경우 (가장 흔함)
        {
            "mode": "SYMPTOM_ONLY",
            "desc": "환자가 너무 급해서 증상만 말하고 나이/성별을 빼먹은 상황.",
            "prompt_guide": "age와 gender는 반드시 null로 두고, symptoms만 구체적으로 생성하세요."
        },
        # [Case 3] 보호자 신고: 주어가 '우리 아이', '아빠' 등인 경우
        {
            "mode": "CAREGIVER",
            "desc": "보호자가 대신 신고하는 상황. 대상의 나이/성별을 유추하거나 언급함.",
            "prompt_guide": "is_self를 false로 설정하고, 대상의 나이대와 성별을 추출하세요."
        },
        # [Case 4] 선택 정보 포함: 히스토리나 특이사항이 있는 경우
        {
            "mode": "WITH_OPTIONAL",
            "desc": "기저질환(당뇨 등)이나 특이사항(임신, 음주)을 함께 말하는 상황.",
            "prompt_guide": "history나 special_note 필드를 채우세요."
        }
    ]
    
    current = scenarios[mode_index % 4]
    
    base_prompt = f"""
    당신은 응급 의료 AI 학습 데이터 생성기입니다.
    현재 시나리오: **{current['mode']}** ({current['desc']})
    생성 지침: {current['prompt_guide']}

    [★ 데이터 추출 규칙 (Strict Rules) ★]

    1. **필수 필드 (Mandatory Fields)**
       - **age**: 아래 구간 중 하나로 매핑 (정보 없으면 null)
         ["0-5", "5-10", "10-19", "20-30", "30-40", "40-50", "50-60", "60-70", "70-99"]
       - **gender**: "남성", "여성" (정보 없으면 null)
       - **symptoms**: ["부위 증상"] 형식의 리스트 (필수!)
         * 포맷: "아픈부위 구체적증상" (띄어쓰기 필수)
         * 예: "배가 찢어질 듯 아파" -> ["배 극심한통증"]
         * 예: "가슴이 답답하고 숨이 안 쉬어져" -> ["가슴 답답함", "호흡기 호흡곤란"]
         * 예: "머리가 핑 돌아" -> ["머리 어지러움"]

    2. **선택 필드 (Optional Fields)**
       - **is_self**: true(본인), false(타인). (언급 없으면 기본 true)
       - **history**: 고혈압, 당뇨 등 기저질환. (없으면 "특이사항 없음")
       - **special_note**: 임신, 음주, 약물, 최근수술 등. (없으면 null)

    [출력 형식]
    잡담 없이 아래 JSON 리스트만 출력하세요.
    [
      {{
        "text": "생성된 발화 문장",
        "extraction": {{
          "age": "20-30",
          "gender": "남성",
          "symptoms": ["머리 두통", "위장 구토"],
          "is_self": true,
          "history": "특이사항 없음",
          "special_note": "음주 상태"
        }}
      }}
    ]

    위 규칙에 맞춰 데이터 {BATCH_SIZE}개를 생성하세요.
    """
    return base_prompt

async def fetch_batch(session, semaphore, mode_index):
    async with semaphore:
        prompt = get_system_prompt(mode_index)
        
        # 다양한 응급 키워드 랜덤 주입
        keywords = ["복통", "흉통", "두통", "골절", "열상(베임)", "화상", "고열", "호흡곤란", "알레르기", "약물중독"]
        keyword = random.choice(keywords)

        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"키워드: '{keyword}'. 리얼한 구어체로 생성해."}
            ],
            "temperature": 0.95
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }

        try:
            async with session.post(API_URL, json=payload, headers=headers, ssl=False) as response:
                if response.status != 200:
                    print(f"⚠️ Error {response.status}")
                    return []
                
                result = await response.json()
                content = result['choices'][0]['message']['content']
                
                cleaned = re.sub(r'^```json\s*', '', content, flags=re.MULTILINE)
                cleaned = re.sub(r'^```\s*', '', cleaned, flags=re.MULTILINE)
                cleaned = cleaned.replace("```", "").strip()
                
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    return []
        except Exception:
            return []

def save_to_jsonl(data_buffer):
    if not data_buffer: return

    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        for item in data_buffer:
            # 0.5B 모델 학습을 위한 최종 포맷
            # 시스템 메시지에 '필수'와 '선택'의 뉘앙스를 심어줍니다.
            entry = {
                "messages": [
                    {
                        "role": "system", 
                        "content": "당신은 응급 의료 AI입니다. 문장에서 필수 정보 {age, gender, symptoms}를 우선적으로 추출하고, 선택 정보 {is_self, history, special_note}는 확인되는 경우에만 추출하세요."
                    },
                    {
                        "role": "user", 
                        "content": item['text']
                    },
                    {
                        "role": "assistant", 
                        "content": json.dumps(item['extraction'], ensure_ascii=False)
                    }
                ]
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"💾 {len(data_buffer)}개 저장 완료.")

async def main():
    print(f"🚀 Essential Data Generation Started (Target: {TOTAL_TARGET_DATA})")
    print(f"Mandatory: Age(Range), Gender, Symptoms(Body+State)")
    print(f"Optional: Is_self, History, Special_note")
    
    if not os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f: pass

    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        loops = TOTAL_TARGET_DATA // BATCH_SIZE
        
        for i in range(loops):
            tasks.append(fetch_batch(session, semaphore, i % 4))
        
        total_saved = 0
        buffer = []
        
        for future in asyncio.as_completed(tasks):
            batch_data = await future
            if batch_data:
                buffer.extend(batch_data)
                
                if len(buffer) >= 50:
                    save_to_jsonl(buffer)
                    total_saved += len(buffer)
                    buffer = []
                    print(f"   (진행률: {total_saved}/{TOTAL_TARGET_DATA})")
        
        if buffer:
            save_to_jsonl(buffer)
            total_saved += len(buffer)

    print(f"\n🎉 작업 끝! {OUTPUT_FILE} 생성 완료.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 중단됨.")