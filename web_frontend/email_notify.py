import smtplib
from email.mime.text import MIMEText
from web_frontend import settings
from string import Template
from django.core.urlresolvers import reverse

def send_email(job):
    sender = settings.EMAIL_FROM_ADDRESS

    receiver = job.user.email

    if receiver == None:
        return

    if job.status == 'E':
        messageTextTemplate = Template("""Dear $username,
The job $jobname ($jobtype) running on Condor-Copasi has failed.
Visit $webaddress to see more details.

This is an automated message sent by Condor-Copasi, do not reply.
        """)
    elif job.status == 'C':
        messageTextTemplate = Template("""Dear $username,
The job $jobname ($jobtype) running on Condor-Copasi has completed successfully.
Visit $webaddress to see more details, to view any output, and to download any results.

This is an automated message sent by Condor-Copasi, do not reply.
        """)
    else:
        return
    
    try:
        webaddress = "http://" + settings.SITE_DOMAIN + settings.SITE_SUBFOLDER.rstrip('/') + reverse('job_details', args=[job.name])
        messageText=messageTextTemplate.substitute(username=job.user.username, jobname=job.name, jobtype=job.get_job_type_display(), webaddress=webaddress)
        msg = MIMEText(messageText)
        msg['Subject'] = 'Condor-Copasi Notification: Job ' + job.name
        msg['From'] = sender
        msg['To'] = receiver

        smtpObj = smtplib.SMTP(settings.SMTP_HOST)
        smtpObj.sendmail(sender, [receiver], msg.as_string())         

    except:
        raise
