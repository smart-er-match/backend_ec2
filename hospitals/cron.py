from django_cron import CronJobBase, Schedule
from django.core.management import call_command

class FetchHospitalsCronJob(CronJobBase):
    RUN_EVERY_MINS = 5 # 5분마다 실행

    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'hospitals.fetch_all_data_cron' # 유니크 코드

    def do(self):
        call_command('fetch_all_data')