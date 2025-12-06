import requests
import os
from django.db import transaction
from django.core.management.base import BaseCommand
from hospitals.models import Hospital, HospitalRealtimeStatus, HospitalSevereMessage, UpdateLog

class Command(BaseCommand):
    help = '실시간 응급실 병상 정보와 중증질환 메시지를 갱신합니다.'

    def handle(self, *args, **options):
        KEY = os.getenv("NMC_API_KEY")
        if not KEY:
            self.stdout.write(self.style.ERROR("NMC_API_KEY 환경변수 없음"))
            return

        self.fetch_realtime_beds(KEY)
        self.fetch_severe_messages(KEY)
        
        self.stdout.write(self.style.SUCCESS("실시간 데이터(병상, 메시지) 갱신 완료"))

    def fetch_realtime_beds(self, key):
        url = "http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire"
        params = {'serviceKey': key, 'numOfRows': 5000, 'pageNo': 1, '_type': 'json'}
        
        try:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()
            items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if isinstance(items, dict): items = [items]

            count = 0
            for item in items:
                hpid = item.get('hpid')
                if not hpid: continue
                
                if not Hospital.objects.filter(hpid=hpid).exists():
                    continue

                def to_int(val):
                    try: return int(val)
                    except (ValueError, TypeError): return 0

                defaults = {
                    'hv10': item.get('hv10'), 'hv11': item.get('hv11'),
                    'hv13': to_int(item.get('hv13')), 'hv14': to_int(item.get('hv14')), 'hv18': to_int(item.get('hv18')),
                    'hv2': to_int(item.get('hv2')), 'hv24': to_int(item.get('hv24')), 'hv25': to_int(item.get('hv25')),
                    'hv27': to_int(item.get('hv27')), 'hv28': to_int(item.get('hv28')), 'hv29': to_int(item.get('hv29')),
                    'hv3': to_int(item.get('hv3')), 'hv30': to_int(item.get('hv30')), 'hv31': to_int(item.get('hv31')),
                    'hv34': to_int(item.get('hv34')), 'hv35': to_int(item.get('hv35')), 'hv36': to_int(item.get('hv36')),
                    'hv38': to_int(item.get('hv38')), 'hv40': to_int(item.get('hv40')), 'hv41': to_int(item.get('hv41')),
                    'hv42': item.get('hv42'), 'hv5': item.get('hv5'), 'hv7': item.get('hv7'),
                    'hvamyn': item.get('hvamyn'), 'hvangioayn': item.get('hvangioayn'), 'hvcrrtayn': item.get('hvcrrtayn'),
                    'hvctayn': item.get('hvctayn'), 'hvec': to_int(item.get('hvec')), 'hvecmoayn': item.get('hvecmoayn'),
                    'hvgc': to_int(item.get('hvgc')), 'hvhypoayn': item.get('hvhypoayn'), 'hvidate': item.get('hvidate'),
                    'hvincuayn': item.get('hvincuayn'), 'hvmriayn': item.get('hvmriayn'),
                    'hvncc': to_int(item.get('hvncc')), 'hvoc': to_int(item.get('hvoc')), 'hvoxyayn': item.get('hvoxyayn'),
                    'hvs01': to_int(item.get('hvs01')), 'hvs02': to_int(item.get('hvs02')), 'hvs03': to_int(item.get('hvs03')),
                    'hvs04': to_int(item.get('hvs04')), 'hvs05': to_int(item.get('hvs05')), 'hvs06': to_int(item.get('hvs06')),
                    'hvs07': to_int(item.get('hvs07')), 'hvs08': to_int(item.get('hvs08')), 'hvs15': to_int(item.get('hvs15')),
                    'hvs18': to_int(item.get('hvs18')), 'hvs19': to_int(item.get('hvs19')), 'hvs21': to_int(item.get('hvs21')),
                    'hvs22': to_int(item.get('hvs22')), 'hvs24': to_int(item.get('hvs24')), 'hvs25': to_int(item.get('hvs25')),
                    'hvs26': to_int(item.get('hvs26')), 'hvs27': to_int(item.get('hvs27')), 'hvs28': to_int(item.get('hvs28')),
                    'hvs29': to_int(item.get('hvs29')), 'hvs30': to_int(item.get('hvs30')), 'hvs31': to_int(item.get('hvs31')),
                    'hvs32': to_int(item.get('hvs32')), 'hvs33': to_int(item.get('hvs33')), 'hvs34': to_int(item.get('hvs34')),
                    'hvs35': to_int(item.get('hvs35')), 'hvs38': to_int(item.get('hvs38')), 'hvs46': to_int(item.get('hvs46')),
                    'hvs47': to_int(item.get('hvs47')), 'hvs51': to_int(item.get('hvs51')), 'hvs56': to_int(item.get('hvs56')),
                    'hvs57': to_int(item.get('hvs57')), 'hvs59': to_int(item.get('hvs59')),
                    'hvventiayn': item.get('hvventiayn'), 'hvventisoayn': item.get('hvventisoayn'),
                }

                HospitalRealtimeStatus.objects.update_or_create(hospital_id=hpid, defaults=defaults)
                count += 1
            
            UpdateLog.objects.update_or_create(update_key='realtime', defaults={})
            self.stdout.write(f"실시간 병상: {count}개 갱신")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"실시간 병상 갱신 실패: {e}"))

    def fetch_severe_messages(self, key):
        url = "http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmSrsillDissMsgInqire"
        params = {'serviceKey': key, 'numOfRows': 5000, 'pageNo': 1, '_type': 'json'}
        
        try:
            response = requests.get(url, params=params, timeout=30)
            try:
                data = response.json()
            except:
                self.stdout.write(self.style.ERROR("중증질환 메시지 JSON 파싱 실패"))
                return

            items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if isinstance(items, dict): items = [items]

            with transaction.atomic():
                # 전체 삭제 후 재생성
                HospitalSevereMessage.objects.all().delete()
                
                msg_objects = []
                for item in items:
                    hpid = item.get('hpid')
                    if not hpid: continue
                    
                    if not Hospital.objects.filter(hpid=hpid).exists():
                        continue

                    msg = HospitalSevereMessage(
                        hospital_id=hpid,
                        message=item.get('symBlkMsg'),
                        message_type=item.get('symBlkMsgTyp'),
                        severe_code=item.get('symTypCod'),
                        severe_name=item.get('symTypCodMag'),
                        display_yn=item.get('symOutDspYon'),
                        display_method=item.get('symOutDspMth'),
                        start_time=item.get('symBlkSttDtm'),
                        end_time=item.get('symBlkEndDtm')
                    )
                    msg_objects.append(msg)
                
                HospitalSevereMessage.objects.bulk_create(msg_objects)
                
            UpdateLog.objects.update_or_create(update_key='severe_msg', defaults={})
            self.stdout.write(f"중증질환 메시지: {len(msg_objects)}개 갱신")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"중증질환 메시지 갱신 실패: {e}"))