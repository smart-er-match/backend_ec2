import boto3
import requests
import time
import re
import os
from datetime import datetime

# --- [설정] ---
REGION = "ap-northeast-2"
SCALE_SCRIPT_PATH = "scale_gpu.py"

def get_current_instance_id():
    """메타데이터 서비스(IMDSv2)를 통해 현재 인스턴스 ID를 가져옵니다."""
    try:
        # 1. 토큰 발급
        token_url = "http://169.254.169.254/latest/api/token"
        token_headers = {"X-aws-ec2-metadata-token-ttl-seconds": "21600"}
        token = requests.put(token_url, headers=token_headers, timeout=2).text

        # 2. 인스턴스 ID 조회
        id_url = "http://169.254.169.254/latest/meta-data/instance-id"
        id_headers = {"X-aws-ec2-metadata-token": token}
        instance_id = requests.get(id_url, headers=id_headers, timeout=2).text
        
        print(f"📍 현재 인스턴스 식별: {instance_id}")
        return instance_id
    except Exception as e:
        print(f"❌ 인스턴스 정보 조회 실패: {e}")
        return None

def create_ami(instance_id):
    """현재 인스턴스로부터 AMI를 생성합니다."""
    ec2 = boto3.client('ec2', region_name=REGION)
    
    # 이름에 날짜/시간 추가하여 중복 방지
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    image_name = f"Smart-ER-Match-GPU-Image-{timestamp}"
    
    print(f"📸 이미지 생성 요청 중... (Name: {image_name})")
    print("   (서비스 중단을 막기 위해 재부팅 없이 진행합니다)")
    
    try:
        response = ec2.create_image(
            InstanceId=instance_id,
            Name=image_name,
            Description=f"Created from {instance_id} via automation script",
            NoReboot=True, # 서비스 중단 방지
            TagSpecifications=[
                {
                    'ResourceType': 'image',
                    'Tags': [
                        {'Key': 'Project', 'Value': 'Smart-ER-Match'},
                        {'Key': 'AutoCreated', 'Value': 'True'}
                    ]
                }
            ]
        )
        image_id = response['ImageId']
        print(f"✅ 이미지 생성 요청 완료: {image_id}")
        return image_id
    except Exception as e:
        print(f"❌ 이미지 생성 실패: {e}")
        return None

def wait_for_ami_available(image_id):
    """AMI가 사용 가능(available) 상태가 될 때까지 대기합니다."""
    ec2 = boto3.client('ec2', region_name=REGION)
    print(f"⏳ 이미지가 준비될 때까지 대기 중 ({image_id})...")
    
    start_time = time.time()
    while True:
        try:
            response = ec2.describe_images(ImageIds=[image_id])
            state = response['Images'][0]['State']
            
            if state == 'available':
                print(f"\n✨ 이미지 준비 완료! ({time.time() - start_time:.1f}초 소요)")
                return True
            elif state == 'failed':
                print(f"\n❌ 이미지 생성 실패 (State: failed)")
                return False
                
            print(".", end="", flush=True)
            time.sleep(10)
        except Exception as e:
            print(f"\n⚠️ 상태 확인 중 오류: {e}")
            time.sleep(10)

def update_scale_script(new_ami_id):
    """scale_gpu.py 파일의 AMI_ID 값을 갱신합니다."""
    if not os.path.exists(SCALE_SCRIPT_PATH):
        print(f"❌ {SCALE_SCRIPT_PATH} 파일을 찾을 수 없습니다.")
        return

    try:
        with open(SCALE_SCRIPT_PATH, 'r') as f:
            content = f.read()
        
        # 정규식으로 AMI_ID = "ami-..." 패턴 찾아서 교체
        # 예: AMI_ID = "ami-0b8be69dbf8c4d3c0"
        pattern = r'AMI_ID\s*=\s*"ami-[a-zA-Z0-9]+"'
        new_line = f'AMI_ID = "{new_ami_id}"'
        
        if re.search(pattern, content):
            new_content = re.sub(pattern, new_line, content)
            
            with open(SCALE_SCRIPT_PATH, 'w') as f:
                f.write(new_content)
            
            print(f"📝 {SCALE_SCRIPT_PATH} 업데이트 완료: {new_line}")
        else:
            print("⚠️ 파일 내에서 'AMI_ID' 설정 라인을 찾을 수 없습니다.")
            
    except Exception as e:
        print(f"❌ 파일 업데이트 실패: {e}")

if __name__ == "__main__":
    print("=== 🚀 GPU 서버 이미지 갱신 자동화 시작 ===")
    
    # 1. 내 ID 확인
    my_id = get_current_instance_id()
    
    if my_id:
        # 2. 이미지 생성 요청
        new_ami_id = create_ami(my_id)
        
        if new_ami_id:
            # 3. 이미지가 사용 가능해질 때까지 대기 (선택 사항: 바로 업데이트하고 싶으면 이 단계 생략 가능하지만, 안전을 위해 대기)
            # 이미지가 pending 상태여도 ID는 나왔으므로 코드는 고칠 수 있지만,
            # 실제 스케일링 테스트는 이미지가 available 된 후에 해야 함.
            is_ready = wait_for_ami_available(new_ami_id)
            
            if is_ready:
                # 4. 스크립트 파일 갱신
                update_scale_script(new_ami_id)
                print("\n🎉 모든 작업이 완료되었습니다. 이제 scale_gpu.py는 새 이미지를 사용합니다.")
            else:
                print("\n❌ 이미지 생성 대기 중 문제가 발생하여 코드를 업데이트하지 않았습니다.")
