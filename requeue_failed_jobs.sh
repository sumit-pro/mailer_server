#!/bin/bash
source /home/serafeim/mailer_server/venv/bin/activate && python /home/serafeim/mailer_server/mailer_server/manage.py requeue_failed_jobs > /tmp/"requeue_failed_jobs`date +"_%Y-%m-%d"`.log"

