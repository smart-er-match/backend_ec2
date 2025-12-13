from django_cron import CronJobBase, Schedule
from django.core.management import call_command

class FetchHospitalsCronJob(CronJobBase):
    RUN_EVERY_MINS = 5 # 5분마다 실행

    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'hospitals.fetch_all_data_cron' # 유니크 코드

    def do(self):
        call_command('fetch_all_data')

class UpdateHospitalDescCronJob(CronJobBase):
    RUN_EVERY_MINS = 10080 # 7일 (7 * 24 * 60)

    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'hospitals.update_hospital_desc_cron'

    def do(self):
        call_command('update_hospital_desc')

class ResetApiLimitsCronJob(CronJobBase):
    RUN_AT_TIMES = ['00:00']

    schedule = Schedule(run_at_times=RUN_AT_TIMES)
    code = 'hospitals.reset_api_limits_cron'

    def do(self):
        call_command('reset_api_limits')