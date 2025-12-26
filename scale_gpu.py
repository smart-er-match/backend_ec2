import boto3
import time
import os
import requests
import subprocess
import uuid

# --- [설정 구간] ---
AMI_ID = "ami-0b8be69dbf8c4d3c0" 
INSTANCE_TYPE = "g4dn.xlarge" 
REGION = "ap-northeast-2"
TARGET_SECURITY_GROUP_NAME = "launch-wizard-1" # 사용할 보안 그룹 이름
TAG_ROLE_KEY = "Role"
TAG_ROLE_VALUE = "AI-Worker"

def get_current_instance_info():
    try:
        # EC2 메타데이터 토큰 가져오기
        token = requests.put("http://169.254.169.254/latest/api/token", 
                           headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"}, timeout=1).text
        headers = {"X-aws-ec2-metadata-token": token}
        
        # 현재 인스턴스 ID 및 정보 조회
        instance_id = requests.get("http://169.254.169.254/latest/meta-data/instance-id", headers=headers).text
        ec2 = boto3.resource('ec2', region_name=REGION)
        instance = ec2.Instance(instance_id)
        
        # 보안 그룹 이름으로 ID 조회
        ec2_client = boto3.client('ec2', region_name=REGION)
        sg_res = ec2_client.describe_security_groups(GroupNames=[TARGET_SECURITY_GROUP_NAME])
        target_sg_id = sg_res['SecurityGroups'][0]['GroupId']
        
        print(f"📍 보안 그룹 확인: {TARGET_SECURITY_GROUP_NAME} ({target_sg_id})")
        return instance.subnet_id, [target_sg_id]
    except Exception as e:
        print(f"❌ 설정 조회 실패: {e}")
        return None, None

def check_existing_instance():
    ec2 = boto3.client('ec2', region_name=REGION)
    try:
        response = ec2.describe_instances(
            Filters=[
                {'Name': f'tag:{TAG_ROLE_KEY}', 'Values': [TAG_ROLE_VALUE]},
                {'Name': 'instance-state-name', 'Values': ['pending', 'running']}
            ]
        )
        
        instances = []
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instances.append(instance)
        
        if instances:
            instances.sort(key=lambda x: x['LaunchTime'], reverse=True)
            target = instances[0]
            name = next((t['Value'] for t in target.get('Tags', []) if t['Key'] == 'Name'), "Unknown")
            print(f"🔎 기존 AI 워커 발견! ID: {target['InstanceId']} ({name})")
            return target['InstanceId']
            
        print("🤷‍♂️ 실행 중인 AI 워커가 없습니다.")
        return None
    except Exception as e:
        print(f"❌ 인스턴스 조회 실패: {e}")
        return None

def get_env_mode():
    """ .env 파일에서 MODE 값을 읽어옴 (기본값: SPOT) """
    env_path = "/home/ubuntu/app/.env"
    mode = "SPOT"
    try:
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    if line.strip().startswith("MODE="):
                        mode = line.strip().split("=", 1)[1].strip().upper()
                        break
    except Exception:
        pass
    return mode

def launch_ai_instance(subnet_id, security_groups):
    ec2 = boto3.client('ec2', region_name=REGION)
    unique_name = f"Emergency-AI-GPU-Spot-{uuid.uuid4().hex[:8]}"
    
    # 켜지자마자 실행할 스크립트 (방화벽 해제 + 서버 실행)
    user_data_script = f'''#!/bin/bash
    ufw disable
    iptables -F
    export MODEL_PATH="/home/ubuntu/models/qwen_finetuned.Q8_0.gguf"
    export N_GPU_LAYERS="-1"
    cd /home/ubuntu/ai_server
    /usr/local/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1 > /home/ubuntu/ai_server.log 2>&1 &
    '''

    launch_args = {
        'ImageId': AMI_ID,
        'InstanceType': INSTANCE_TYPE,
        'KeyName': 'yugun__2222',
        'SubnetId': subnet_id,
        'SecurityGroupIds': security_groups,
        'MinCount': 1,
        'MaxCount': 1,
        'UserData': user_data_script,
        'TagSpecifications': [{
            'ResourceType': 'instance',
            'Tags': [
                {'Key': 'Name', 'Value': unique_name},
                {'Key': TAG_ROLE_KEY, 'Value': TAG_ROLE_VALUE}
            ]
        }]
    }
    
    mode = get_env_mode()
    print(f"🔄 인스턴스 생성 모드: {mode}")

    if mode == "ONDEMAND":
        print(f"🚀 온디맨드 인스턴스 요청 중... (Name: {unique_name})")
        try:
            response = ec2.run_instances(**launch_args)
            print("✅ 온디맨드 인스턴스 생성 완료.")
            return response['Instances'][0]['InstanceId']
        except Exception as e:
            print(f"❌ 온디맨드 생성 실패: {e}")
            return None

    print(f"\n🚀 GPU 스팟 인스턴스 요청 중... (Name: {unique_name})")
    try:
        spot_args = launch_args.copy()
        spot_args['InstanceMarketOptions'] = {
            'MarketType': 'spot', 
            'SpotOptions': {
                'SpotInstanceType': 'one-time', 
                'InstanceInterruptionBehavior': 'terminate'
            }
        }
        response = ec2.run_instances(**spot_args)
        print("✅ 스팟 인스턴스 생성 요청 완료.")
        return response['Instances'][0]['InstanceId']
    except Exception as e:
        if "InsufficientInstanceCapacity" in str(e):
            print(f"⚠️ 스팟 재고 부족! 온디맨드로 전환합니다...")
            response = ec2.run_instances(**launch_args)
            print("✅ 온디맨드 인스턴스 생성 완료.")
            return response['Instances'][0]['InstanceId']
        print(f"❌ 생성 실패: {e}")
        return None

def wait_for_ip(instance_id):
    ec2 = boto3.resource('ec2', region_name=REGION)
    instance = ec2.Instance(instance_id)
    print(f"⏳ 인스턴스({instance_id}) 상태 및 IP 확인 중...", end="")
    
    start_time = time.time()
    while time.time() - start_time < 300:
        instance.reload()
        if instance.state['Name'] == 'running':
            if instance.private_ip_address:
                print(f"\n✅ IP 확인 완료: {instance.private_ip_address}")
                return instance.private_ip_address
        print(".", end="", flush=True)
        time.sleep(2)
    return None

def wait_for_ai_server(ip):
    url = f"http://{ip}:8080/completion"
    # AI 서버가 응답할 수 있는 최소한의 페이로드
    payload = {
        "prompt": "<|im_start|>user\ntest<|im_end|>\n<|im_start|>assistant\n", 
        "n_predict": 1, 
        "temperature": 0.1
    }
    print(f"🏥 AI 모델 로딩 대기 중({ip})...", end="")
    for i in range(120): # 최대 10분
        try:
            response = requests.post(url, json=payload, timeout=2)
            if response.status_code == 200:
                print("\n✅ AI 서버 준비 완료!")
                return True
        except: pass
        print(".", end="", flush=True)
        time.sleep(5)
    print("\n❌ 타임아웃.")
    return False

def update_env_file(new_ip):
    env_path = "/home/ubuntu/app/.env"
    if not os.path.exists(env_path): return
    with open(env_path, "r") as f: lines = f.readlines()
    with open(env_path, "w") as f:
        found = False
        for line in lines:
            if line.startswith("GPU_AI_SERVER_URL="):
                f.write(f"GPU_AI_SERVER_URL=http://{new_ip}:8080\n")
                found = True
            else: f.write(line)
        if not found: f.write(f"GPU_AI_SERVER_URL=http://{new_ip}:8080\n")
    print(f"📝 .env 갱신 완료")

def restart_django_with_new_env():
    print("🔄 Django 컨테이너 재생성 (새 설정 적용)...")
    try:
        # docker restart는 env 갱신을 반영하지 못하므로, up -d를 사용해야 함
        # 서비스 이름 'web' 사용
        # cwd를 지정하여 어디서 스크립트를 실행하든 docker-compose.yml을 찾을 수 있게 함
        subprocess.run(["docker-compose", "up", "-d", "web"], check=True, cwd="/home/ubuntu/app")
        print("✨ 모든 설정 완료 및 컨테이너 갱신!")
    except Exception as e:
        print(f"❌ 컨테이너 재생성 실패: {e}")

if __name__ == "__main__":
    subnet, sgs = get_current_instance_info()
    if subnet and sgs:
        instance_id = check_existing_instance() or launch_ai_instance(subnet, sgs)
        if instance_id:
            new_ip = wait_for_ip(instance_id)
            if new_ip:
                if wait_for_ai_server(new_ip):
                    update_env_file(new_ip)
                    restart_django_with_new_env()
