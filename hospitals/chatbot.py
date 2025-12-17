import os
import json
import re
import requests
import time
import uuid
import threading
import hashlib
from django.core.cache import cache
from .models import ChatSession

class InferenceEngine:
    _instance = None
    
    # GBNF Grammar for JSON extraction (AI가 이 문법에 맞는 JSON만 생성하도록 강제)
    JSON_GRAMMAR = r'''
    root ::= "{" ws object "}"
    object ::=
      "\"age\":" ws string-or-null "," ws
      "\"gender\":" ws string-or-null "," ws
      "\"symptoms\":" ws string-list "," ws
      "\"is_self\":" ws boolean "," ws
      "\"history\":" ws string-or-null "," ws
      "\"special_note\":" ws string-or-null
    string ::= "\"" ([^"\\] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F]))* "\""
    string-list ::= "[" ws (string ("," ws string)*)? ws "]"
    boolean ::= "true" | "false"
    string-or-null ::= string | "null"
    ws ::= [ \t\n]*
    '''

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # 환경 변수 로드
        self.api_url = os.getenv("AI_SERVER_URL", "http://ai_server:8080")
        self.gpu_api_url = os.getenv("GPU_AI_SERVER_URL")
        self.mode = os.getenv("AI_SERVICE_MODE", "ONLY_CPU").upper()
        
        print(f"InferenceEngine initialized. Mode: {self.mode}")
        print(f" - Local URL: {self.api_url}")
        print(f" - GPU URL: {self.gpu_api_url}")

    def generate(self, messages, max_tokens=256):
        prompt = ""
        for msg in messages:
            prompt += f"<|im_start|>{msg['role']}\n{msg['content']}<|im_end|>\n"
        prompt += "<|im_start|>assistant\n"
        content, _ = self._call_llama_server(prompt, max_tokens) # generate는 내용만 필요
        return content

    def extract_info(self, text):
        """학습된 모델을 사용하여 JSON 정보 추출"""
        # 0. 단순 인사말/무의미한 텍스트 필터링 (비용 절감 및 환각 방지)
        greetings = ['안녕', '하이', 'ㅎㅇ', '반가워', '누구', '시작', 'test', '테스트', 'hello', 'hi']
        if len(text.strip()) < 10 and any(word in text for word in greetings):
            print(f"[Filter] Greeting detected: {text}")
            return {"age": None, "gender": None, "symptoms": [], "is_self": True, "history": None, "special_note": None}, "NONE"

        system_prompt = "당신은 응급 의료 AI입니다. 문장에서 필수 정보 {age, gender, symptoms}를 우선적으로 추출하고, 선택 정보 {is_self, history, special_note}는 확인되는 경우에만 추출하세요."
        # ChatML 형식 준수
        prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{text}<|im_end|>\n<|im_start|>assistant\n"
        
        # 1. AI 서버 호출 (응답 내용과 사용된 모델을 나눠서 받음)
        response_content, used_model = self._call_llama_server(prompt, max_tokens=256, temperature=0.1)
        
        # 디버깅을 위한 로우 응답 출력
        print(f"[AI Raw Response]: {response_content} (Model: {used_model})")

        try:
            # 2. Grammar 덕분에 순수 JSON이 오지만, 혹시 모를 공백 제거
            cleaned = response_content.strip()
            
            # 3. 바로 파싱 및 결과 반환 (모델 정보 포함)
            return json.loads(cleaned), used_model
        except Exception as e:
            print(f"❌ JSON Parsing Error: {e} | Raw Content: {response_content}")
            return {}, used_model

    def _call_llama_server(self, prompt, max_tokens=256, temperature=0.7):
        payload = {
            "prompt": prompt,
            "temperature": temperature,
            "n_predict": max_tokens,
            "stream": False,
            "stop": ["<|im_end|>", "###"],
            "grammar": self.JSON_GRAMMAR # Grammar 적용!
        }
        
        # 1. ONLY_GPU 모드
        if self.mode == 'ONLY_GPU':
            if not self.gpu_api_url:
                return "AI 서버 설정 오류 (GPU URL 없음)", "ERROR"
            try:
                base_url = self.gpu_api_url.rstrip('/')
                url = f"{base_url}/completion" if not base_url.endswith('/completion') else base_url
                response = requests.post(url, json=payload, timeout=10)
                response.raise_for_status()
                return response.json().get("content", ""), "GPU"
            except Exception as e:
                print(f"❌ GPU Server Error (ONLY_GPU): {e}")
                return "죄송합니다. AI 서비스 연결이 원활하지 않습니다.", "ERROR"

        # 2. ONLY_CPU 모드
        elif self.mode == 'ONLY_CPU':
            try:
                response = requests.post(f"{self.api_url}/completion", json=payload, timeout=20)
                response.raise_for_status()
                return response.json().get("content", ""), "CPU"
            except Exception as e:
                print(f"❌ Local AI Server Error (ONLY_CPU): {e}")
                return "죄송합니다. AI 서비스 연결이 원활하지 않습니다.", "ERROR"

        # 3. HYBRID_SPOT 모드
        elif self.mode == 'HYBRID_SPOT':
            try:
                response = requests.post(f"{self.api_url}/completion", json=payload, timeout=5)
                if response.status_code == 503:
                    raise requests.exceptions.RequestException("Local Server Busy")
                response.raise_for_status()
                return response.json().get("content", ""), "CPU"
            except Exception as e:
                if self.gpu_api_url:
                    print(f"⚠️ Failover to GPU: {e}")
                    try:
                        base_url = self.gpu_api_url.rstrip('/')
                        url = f"{base_url}/completion" if not base_url.endswith('/completion') else base_url
                        response = requests.post(url, json=payload, timeout=5)
                        response.raise_for_status()
                        return response.json().get("content", ""), "GPU"
                    except Exception as gpu_e:
                        print(f"❌ GPU Server Error: {gpu_e}")
                
                return "죄송합니다. 서비스 연결이 원활하지 않습니다.", "ERROR"
        
        else:
            # Fallback (기존 로직)
            try:
                response = requests.post(f"{self.api_url}/completion", json=payload, timeout=20)
                response.raise_for_status()
                return response.json().get("content", ""), "CPU"
            except:
                return "Error", "ERROR"

class ChatbotService:
    def __init__(self):
        self.engine = InferenceEngine.get_instance()

    def process_message(self, session_id, user_message, user=None, location_data=None):
        if session_id:
            try:
                session = ChatSession.objects.get(session_id=session_id)
                if not session.user and user:
                    session.user = user
                    session.save()
            except ChatSession.DoesNotExist:
                session = self._create_new_session(user)
        else:
            session = self._create_new_session(user)

        response_text = ""
        next_state = session.state
        collected = session.collected_data
        if 'status' not in collected: collected['status'] = {}
        find_loc = False
        
        # 모델 사용 기록 (기본값)
        used_model = "NONE"

        self._update_location(collected, user, location_data)

        # --- 상태 머신 ---
        
        if session.state in ['INIT', 'COLLECT_BASIC_INFO']:
            # 1) 정보 추출 시도
            extracted, used_model = self.engine.extract_info(user_message)
            self._merge_extracted_data(collected, extracted)
            
            # 2) 필수 정보 확인 (나이, 성별, 증상)
            missing = self._get_missing_fields(collected)
            
            # (중요) 인사말만 있거나 정보가 아예 없는 경우 방어 로직
            # symptoms가 비어있으면 아직 제대로 된 의료 정보를 못 받은 것으로 간주
            has_symptoms = collected.get('symptoms') and len(collected.get('symptoms')) > 0
            
            if not missing and has_symptoms:
                # 필수 정보가 다 모임 -> 다음 단계로
                symptoms_str = ', '.join(collected.get('symptoms'))
                response_text = (
                    f"기본 정보가 확인되었습니다.\n"
                    f"- 환자: {collected.get('age')} {collected.get('gender')}\n"
                    f"- 증상: {symptoms_str}\n\n"
                    "혹시 **기저질환(고혈압, 당뇨 등)**이나 **특이사항(임신, 음주, 수술이력)**이 있으신가요?"
                )
                next_state = 'CHECK_HISTORY'
            else:
                # 정보 부족 -> 되묻기
                has_any_info = collected.get('age') or collected.get('gender') or has_symptoms
                
                if has_any_info:
                    missing_str = ', '.join(missing)
                    if not has_symptoms and '증상' not in missing:
                         missing.append('증상') # 증상이 없으면 무조건 물어봐야 함
                    
                    response_text = f"네, 알겠습니다. 정확한 안내를 위해 **{', '.join(missing)}** 정보를 더 말씀해 주시겠어요?"
                    next_state = 'COLLECT_BASIC_INFO'
                else:
                    response_text = (
                        "안녕하세요! 응급 의료 챗봇입니다.\n"
                        "빠른 안내를 위해 **환자분의 나이, 성별, 그리고 구체적인 증상**을 자세히 말씀해 주세요.\n"
                        "(예: 30대 남성이고 배가 쥐어짜듯이 아파요)"
                    )
                    next_state = 'COLLECT_BASIC_INFO'

        elif session.state == 'CHECK_HISTORY':
            # 부정적인 의미의 키워드 보강 (기저질환 없음으로 간주)
            if any(word in user_message for word in ['없어', '아니', 'ㄴㄴ', '괜찮', '없음', '몰라', '아냐', '노노', '업서', '안해', '없구만', '업음']):
                pass 
            else:
                extracted, used_model = self.engine.extract_info(user_message)
                self._merge_extracted_data(collected, extracted)
                
                if not extracted.get('history') and len(user_message) > 5:
                     if user_message.strip() not in ['네', '응', 'ㅇㅇ', '어', '예']:
                        collected['history'] = user_message

            # 위치 정보 갱신 (DB에서 최신 정보 가져오기)
            if user:
                user.refresh_from_db()
                if user.location:
                    collected['location'] = user.location
                    collected['latitude'] = user.latitude
                    collected['longitude'] = user.longitude

            loc = collected.get('location', '위치 정보 없음')
            response_text = f"정보를 모두 수집했습니다.\n현재 위치가 **'{loc}'** 맞으신가요?"
            next_state = 'CHECK_LOCATION'

        elif session.state == 'CHECK_LOCATION':
            # DB에서 최신 위치 한 번 더 확인
            if user:
                user.refresh_from_db()
                if user.location and user.location != collected.get('location'):
                    collected['location'] = user.location
                    collected['latitude'] = user.latitude
                    collected['longitude'] = user.longitude
            
            # 긍정적인 의미의 키워드 보강
            if any(word in user_message for word in ['응', '네', '맞아', 'ㅇㅇ', '예', '그래', '어', '어어', '웅', '당연', '확인', '마즘', '마자', '조아', '좋아']) or 'location' in str(location_data):
                symptoms_str = ', '.join(collected.get('symptoms', []))
                history_str = collected.get('history', '없음')
                note_str = collected.get('special_note', '없음')
                
                summary = (
                    f"- 환자: {collected.get('age')} {collected.get('gender')}\n"
                    f"- 증상: {symptoms_str}\n"
                    f"- 위치: {collected.get('location')}\n"
                    f"- 병력/특이사항: {history_str} / {note_str}"
                )
                response_text = f"모든 정보를 확인했습니다.\n\n{summary}\n\n이대로 응급실 검색을 시작할까요?"
                next_state = 'CONFIRM'
            else:
                # 긍정이 아니면(아니, 틀려, 위치 바꿀래 등) 모두 위치 찾기로 유도
                find_loc = True
                response_text = "지도에서 정확한 위치를 선택해 주세요."
                next_state = 'CHECK_LOCATION' 

        elif session.state == 'CONFIRM':
            # 검색 시작 긍정 키워드 보강
            if any(word in user_message for word in ['응', '네', '찾아', '검색', 'ㅇㅇ', '해줘', '고', 'ㄱㄱ', '웅', '어', '스타트', '시작', '출발']):
                response_text = "최적의 응급실을 찾는 중입니다. 잠시만 기다려 주세요..."
                next_state = 'DONE'
            else:
                response_text = "검색하시려면 '네'라고 말씀해 주세요."

        session.state = next_state
        session.collected_data = collected
        session.history.append({"role": "user", "content": user_message})
        session.history.append({"role": "assistant", "content": response_text})
        
        # GPU 사용 여부 저장
        if used_model != "NONE":
            session.ai_model_used = used_model
            
        session.save()
        
        final_payload = None
        is_finished = (next_state == 'DONE')
        if is_finished:
            final_payload = {
                "symptom": collected.get('symptoms', []),
                "gender": 'M' if collected.get('gender') in ['남성', '남', '남자', 'M', 'male'] else 'F',
                "age": collected.get('age'),
                "latitude": collected.get('latitude'),
                "longitude": collected.get('longitude'),
                "is_self": collected.get('is_self', True),
                "history": collected.get('history'),
                "special_note": collected.get('special_note')
            }

        return self._build_response(session, response_text, is_finished, find_loc, final_payload)

    def _create_new_session(self, user):
        from django.utils import timezone
        from datetime import timedelta

        if user:
            session = ChatSession.objects.filter(user=user).exclude(state='DONE').order_by('-updated_at').first()
            if session:
                # 5분(300초) 이상 지났는지 확인
                if timezone.now() - session.updated_at > timedelta(minutes=5):
                    session.state = 'DONE'
                    session.save()
                    # 타임아웃 되었으므로 새 세션 생성
                    session = ChatSession.objects.create(user=user)
            else:
                session = ChatSession.objects.create(user=user)
        else:
            session = ChatSession.objects.create(user=user)
        return session

    def _get_missing_fields(self, collected):
        missing = []
        if not collected.get('age'): missing.append("나이")
        if not collected.get('gender'): missing.append("성별")
        if not collected.get('symptoms'): missing.append("증상")
        return missing

    def _merge_extracted_data(self, collected, extracted):
        if not extracted: return
        if extracted.get('age'): collected['age'] = extracted['age']
        if extracted.get('gender'): collected['gender'] = extracted['gender']
        new_symptoms = extracted.get('symptoms', [])
        if new_symptoms:
            if isinstance(new_symptoms, str): new_symptoms = [new_symptoms]
            current_symptoms = collected.get('symptoms', [])
            merged = list(set(current_symptoms + new_symptoms))
            collected['symptoms'] = merged
        if extracted.get('is_self') is not None: collected['is_self'] = extracted['is_self']
        if extracted.get('history') and extracted['history'] != "특이사항 없음":
            collected['history'] = extracted['history']
        if extracted.get('special_note'): collected['special_note'] = extracted['special_note']

    def _update_location(self, collected, user, location_data):
        if location_data and location_data.get('latitude'):
            collected['location'] = location_data.get('location', '설정된 위치')
            collected['latitude'] = location_data.get('latitude')
            collected['longitude'] = location_data.get('longitude')
        elif not collected.get('location'):
            if user and user.latitude:
                collected['latitude'] = user.latitude
                collected['longitude'] = user.longitude
                collected['location'] = user.location if user.location else "기본 위치"

    def _build_response(self, session, message, is_finished, find_loc=False, final_data=None):
        return {
            "session_id": str(session.session_id), 
            "message": message, 
            "state": session.state, 
            "is_finished": is_finished, 
            "find_loc": find_loc, 
            "final_data": final_data,
            "ai_model": session.ai_model_used  # 클라이언트 확인용
        }